WITH trade_signals AS (
	SELECT * FROM (VALUES 
		%(trade_signals)s
	) AS ts(signal_id, strategy_ref, the_date, instrument, direction, entry_price, take_profit_difference, stop_loss_difference, duration)
),
min_date AS (
	SELECT MIN(the_date) AS start_date FROM trade_signals 
),
max_date AS (
	SELECT MAX(the_date + (duration || ' minutes')::INTERVAL) AS end_date FROM trade_signals
),
instruments AS (
	SELECT array_agg(instrument) AS instruments FROM trade_signals
),
selected_candles AS (
	SELECT evt.full_name AS instrument,
	evt.open_price,
	evt.high_price,
	evt.low_price,
	evt.close_price,
	TO_TIMESTAMP (FLOOR(( EXTRACT ('EPOCH' FROM (evt.the_date )) ) / (60*15) ) * (60*15)) AT TIME ZONE 'UTC' AS the_date
	FROM exchange_value_tick evt, min_date, max_date, instruments 
	WHERE evt.the_date >= min_date.start_date 
	AND evt.the_date  < max_date.end_date 
	AND evt.full_name = ANY(instruments.instruments)
),
trade_tracks_differences AS (
	SELECT ts.signal_id,
	ts.instrument,
	ts.direction,
	ts.entry_price::DOUBLE PRECISION AS entry_price, --incase all are null
	ts.take_profit_difference,
	ts.stop_loss_difference,
	sc.open_price,
	sc.high_price,
	sc.low_price,
	sc.close_price,
	sc.the_date,
	ROW_NUMBER() OVER (PARTITION BY ts.signal_id ORDER BY sc.the_date) AS candle_index
	FROM selected_candles sc 
	JOIN trade_signals ts ON sc.instrument = ts.instrument
	AND sc.the_date >= ts.the_date AND sc.the_date < ts.the_date + (ts.duration || ' minutes')::INTERVAL
),
typical_starts AS (
	SELECT signal_id, 
	CASE WHEN entry_price  IS NULL THEN (high_price + low_price + close_price) / 3.0 ELSE entry_price END AS start_price
	FROM trade_tracks_differences
	WHERE candle_index = 1 
),
trade_tracks AS (
	SELECT tt.signal_id,
	tt.instrument,
	tt.direction,
	tt.entry_price,
	ts.start_price + tt.take_profit_difference*(CASE WHEN tt.direction = 'SELL' THEN -1 ELSE 1 END) AS take_profit_price,
	ts.start_price + tt.stop_loss_difference*(CASE WHEN tt.direction = 'SELL' THEN 1 ELSE -1 END) AS stop_loss_price, 
	tt.open_price,
	tt.high_price,
	tt.low_price,
	tt.close_price,
	tt.the_date,
	tt.candle_index
	FROM trade_tracks_differences tt 
	JOIN typical_starts ts ON tt.signal_id = ts.signal_id 
),
status_points AS (
	SELECT *,
	CASE WHEN entry_price <=  high_price AND entry_price >= low_price THEN 0 
		WHEN low_price > entry_price THEN 1 
		WHEN high_price < entry_price THEN -1 
		WHEN entry_price IS NULL THEN 0
		ELSE NULL
	END AS entry_state,
	CASE WHEN take_profit_price <=  high_price AND take_profit_price >= low_price THEN 0 
		WHEN low_price > take_profit_price THEN 1 
		WHEN high_price < take_profit_price THEN -1 
		ELSE NULL
	END AS take_profit_state,
		CASE WHEN stop_loss_price <=  high_price AND stop_loss_price >= low_price THEN 0 
		WHEN low_price > stop_loss_price THEN 1 
		WHEN high_price < stop_loss_price THEN -1 
		ELSE NULL
	END AS stop_loss_state
	FROM trade_tracks tt
),
crossed_entry AS (
	SELECT sp.*, entry_state AS current_entry_state, LAG(entry_state) OVER (PARTITION BY signal_id ORDER BY candle_index ASC) AS last_entry_state
	FROM status_points sp
),
---here we need a mechanism to penalise 10pm candles - the spread goes wild here so it is more likely to hit the stop loss
outcomes AS (
	SELECT *,
	(direction = 'BUY' AND take_profit_state >= 0) OR (direction = 'SELL' AND take_profit_state <= 0) AS won,
	(direction = 'BUY' AND stop_loss_state <= 0) OR (direction = 'SELL' AND stop_loss_state >= 0) AS lost
	FROM crossed_entry 
),
earliest_entries_calc AS (
	SELECT DISTINCT ON (sp.signal_id) sp.*,
	CASE WHEN entry_price IS NULL THEN (high_price + low_price + close_price) / 3 ELSE entry_price END AS typical_starting_price, --parameter 
	(take_profit_state = stop_loss_state AND entry_price IS NULL)
	OR (direction = 'BUY' AND take_profit_price < stop_loss_price) 
	OR (direction = 'SELL' AND take_profit_price > stop_loss_price)	
	AS unfit  --SOME OF the non-entry_price signals might start outside OF their bounds. if they do then thery're unfit
	FROM outcomes sp WHERE entry_state = 0 OR last_entry_state <> current_entry_state--what about -1 TO 1 OR vice versa?
	ORDER BY sp.signal_id, sp.candle_index ASC
),
earliest_exits AS (
	SELECT DISTINCT ON (o.signal_id) o.*,
	o.take_profit_price AS typical_ending_price
	FROM outcomes o 
	JOIN earliest_entries_calc ee ON o.signal_id = ee.signal_id 
	WHERE (o.won OR o.lost)--what about -1 TO 1 OR vice versa?
	AND o.candle_index >= ee.candle_index 
	ORDER BY o.signal_id, o.candle_index ASC
),
ending_exits AS (
	--fill the blanks where there was no exit candle
	SELECT DISTINCT ON (o.signal_id) o.*,
	(o.high_price + o.low_price + o.close_price) / 3 AS typical_ending_price  --parameter "optimistic, typical or pesimistic" here 
	FROM outcomes o
	WHERE NOT EXISTS (SELECT 1 FROM earliest_exits ee WHERE o.signal_id = ee.signal_id)
	ORDER BY o.signal_id, o.candle_index DESC --GET LAST candle
),
exit_candles AS (
	SELECT * FROM earliest_exits 
	UNION 
	SELECT * FROM ending_exits 
),
profit_path_prices AS (
	SELECT o.signal_id,
	o.candle_index,
	(o.high_price + o.low_price + o.close_price) / 3.0 AS typical_price_path,
	CASE WHEN o.direction = 'BUY' THEN o.high_price 
		WHEN o.direction = 'SELL' THEN o.low_price 
	ELSE NULL END AS optimistic_price_path,
	CASE WHEN o.direction = 'BUY' THEN o.low_price 
		WHEN o.direction = 'SELL' THEN o.high_price 
	ELSE NULL END AS pessimistic_price_path,
	ee.typical_starting_price AS path_start_price,  
	GREATEST(ABS(ee.typical_starting_price - ee.take_profit_price),ABS(ee.typical_starting_price - ee.stop_loss_price)) AS path_scale 
	--need to work out normalising value? 
	FROM outcomes o 
	JOIN earliest_entries_calc ee ON ee.signal_id = o.signal_id 
),
results AS (
	SELECT ts.signal_id, 
	sc.the_date AS start_date, 
	sc.typical_starting_price AS starting_price,
	sc.candle_index AS start_candle,
	CASE WHEN sc.the_date IS NULL THEN NULL ELSE ec.the_date END AS end_date,
	CASE WHEN sc.the_date IS NULL THEN NULL ELSE ec.typical_ending_price END AS ending_price,
	CASE WHEN sc.the_date IS NULL THEN NULL ELSE ec.candle_index END AS end_candle,
	CASE 
		WHEN ts.direction = 'BUY' THEN ec.typical_ending_price - sc.typical_starting_price 
		WHEN ts.direction = 'SELL' THEN sc.typical_starting_price  - ec.typical_ending_price 
		ELSE NULL 
	END AS movement, --movement is positive if we made money and negative if we lost money
	CASE 
		WHEN sc.typical_starting_price IS NULL THEN 'STAGNATED' --trade never started 
		WHEN sc.unfit OR ts.direction = 'VOID' THEN 'INVALID' --trade was not taken since it was invalid in some way
		WHEN ec.lost THEN 'LOST' 
		WHEN ec.won THEN 'WON' 
		WHEN ec.won AND ec.lost THEN 'LOST'
		WHEN NOT (ec.won OR ec.lost) THEN 
		CASE 
			WHEN ts.direction = 'BUY' AND ec.typical_ending_price > sc.typical_starting_price THEN 'WINNING'
			WHEN ts.direction = 'BUY' AND ec.typical_ending_price <= sc.typical_starting_price THEN 'LOSING'
			WHEN ts.direction = 'SELL' AND ec.typical_ending_price < sc.typical_starting_price THEN 'WINNING'
			WHEN ts.direction = 'SELL' AND ec.typical_ending_price >= sc.typical_starting_price THEN 'LOSING'
			WHEN ts.direction = 'VOID' THEN 'INVALID'
			ELSE 'BUG' --should never happen! 
		END
	END AS status
	FROM trade_signals ts 
	LEFT JOIN earliest_entries_calc sc ON sc.signal_id = ts.signal_id  --starting candle
	LEFT JOIN exit_candles ec ON ec.signal_id = ts.signal_id --ending candle
),
results_percent AS (
	SELECT r.*,
	(r.movement / r.starting_price) * 100 AS percent_move
	FROM results r 
),
profit_paths AS (
	SELECT ppp.signal_id, 
	ARRAY_AGG((ppp.typical_price_path - path_start_price) / path_scale ORDER BY ppp.candle_index ASC ) AS typical_path, 
	ARRAY_AGG((ppp.optimistic_price_path - path_start_price) / path_scale ORDER BY ppp.candle_index ASC ) AS optimistic_path, 
	ARRAY_AGG((ppp.pessimistic_price_path - path_start_price) / path_scale ORDER BY ppp.candle_index ASC ) AS pessimistic_path,
	MAX(path_scale) AS path_scale, --ALL same FOR this COLUMN 
	MAX(path_start_price) AS path_start_price --ALL same FOR this COLUMN 
	FROM profit_path_prices ppp
	JOIN results_percent rp ON ppp.signal_id = rp.signal_id 
	WHERE ppp.candle_index >= rp.start_candle AND ppp.candle_index <= rp.end_candle 
	GROUP BY ppp.signal_id
) --build json rows as results 
SELECT 
JSON_BUILD_OBJECT(
	'signal_id',rp.signal_id,
	'entry_date',rp.start_date,
	'entry_price',rp.starting_price,
	'entry_candle',rp.start_candle,
	'exit_date',rp.end_date, 
	'exit_price',rp.ending_price, 
	'exit_candle',rp.end_candle,
	'result_movement',rp.movement,
	'result_percent',rp.percent_move,
	'result_status',rp.status 
),
JSON_BUILD_OBJECT(
	'typical',pp.typical_path,
	'optimistic',pp.optimistic_path,
	'pessimistic',pp.pessimistic_path 
)
FROM results_percent rp
LEFT JOIN profit_paths pp ON pp.signal_id = rp.signal_id 


--SELECT * FROM status_points ORDER BY instrument,the_date   

















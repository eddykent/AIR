WITH trade_signals AS (
	SELECT * FROM (VALUES 
		('6be540c1-9a87-430b-aff1-180ae0d998eb','2022-07-05T10:00:00'::timestamp,'AUD/NZD','SELL',(1.10153),(NULL),(120),0.0037327500000003235,0.002488500000000216,1440),('693c2d84-7390-4f15-9206-702a66b8ba92','2022-06-16T01:15:00'::timestamp,'NZD/CHF','BUY',NULL,(0.62594),(120),0.0058432499999999865,0.003895499999999991,1440),('e9997e27-b72b-4e01-903f-1685241d4f38','2022-06-28T03:00:00'::timestamp,'NZD/JPY','SELL',(85.044),(85.21),(120),0.26144999999999496,0.17429999999999665,1440),('59b8d39e-b5fb-4708-a851-dc9a42f4c60d','2022-07-07T23:00:00'::timestamp,'GBP/USD','BUY',(1.20333),(1.2017),(120),0.0022522500000000667,0.0015015000000000445,1440),('0abcca23-0f6f-4903-9e81-3529778d6793','2022-06-24T04:15:00'::timestamp,'GBP/AUD','BUY',(1.77994),(1.77729),(120),0.0041737500000000646,0.002782500000000043,1440),('f690bea3-e6bd-4f94-aaf7-55faa5b9841a','2022-06-29T14:45:00'::timestamp,'NZD/JPY','BUY',(85.22),(85.00040522295251),(120),0.2819250000000032,0.18795000000000214,1440),('44774bf2-1512-47bd-8b8a-248ab30049c5','2022-06-09T11:30:00'::timestamp,'NZD/JPY','SELL',(85.958),(86.151),(120),0.24570000000000933,0.16380000000000622,1440),('051f8c79-d3bf-4639-b0ff-b2d237887be0','2022-07-15T04:00:00'::timestamp,'EUR/JPY','BUY',(139.477),(139.29),(120),0.24727500000001684,0.16485000000001124,1440),('95fe83e3-7a35-4e4e-8431-df30188c4bc8','2022-07-04T14:00:00'::timestamp,'EUR/GBP','SELL',(0.8594),(0.86051),(120),0.0017482499999999122,0.0011654999999999415,1440),('16e399f8-9b1f-4a5f-866a-41ff7e2971e5','2022-06-28T09:00:00'::timestamp,'USD/JPY','BUY',(135.834),(135.61),(120),0.35279999999998357,0.23519999999998903,1440)
	) AS ts(signal_id, the_date, instrument, direction, entry_price, entry_cutoff, entry_expiry, take_profit_difference, stop_loss_difference, duration)
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
	ts.entry_price::DOUBLE PRECISION AS entry_price, --incase all are NULL
	ts.entry_cutoff::DOUBLE PRECISION AS entry_cutoff,
	CASE WHEN ts.entry_expiry IS NULL THEN NULL ELSE ts.the_date + (ts.entry_expiry || ' minutes')::INTERVAL END AS entry_expiry,
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
	tt.entry_cutoff,
	tt.entry_expiry,
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
	CASE WHEN entry_cutoff <=  high_price AND entry_cutoff >= low_price THEN 0 
		WHEN low_price > entry_cutoff THEN 1 
		WHEN high_price < entry_cutoff THEN -1 
		WHEN entry_cutoff IS NULL THEN 2 --use a different value since we are ignoring the entry cutoff here
		ELSE NULL
	END AS cutoff_state,
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
earliest_cutoffs_values AS (
	SELECT DISTINCT ON (o.signal_id) o.*--,   
	--CASE WHEN o.entry_expiry IS NULL THEN FALSE ELSE o.the_date > o.entry_expiry END AS entry_expired
	FROM outcomes o WHERE cutoff_state = 0
	ORDER BY o.signal_id, o.candle_index ASC 
),
earliest_cutoffs_nulls AS (
	SELECT DISTINCT ON (o.signal_id) o.*--,   
	--FALSE AS entry_expired   --ADD back the never expired entries 
	FROM outcomes o WHERE cutoff_state = 2
	ORDER BY o.signal_id, o.candle_index DESC
),
earliest_cutoffs  AS (
	SELECT * FROM earliest_cutoffs_values 
	UNION 
	SELECT * FROM earliest_cutoffs_nulls 
),
earliest_entries_calc AS (
	SELECT DISTINCT ON (sp.signal_id) sp.*,
	CASE WHEN sp.entry_price IS NULL THEN (sp.high_price + sp.low_price + sp.close_price) / 3 ELSE sp.entry_price END AS typical_starting_price, --parameter 
	
	--erroneous trades 
	(sp.take_profit_state = sp.stop_loss_state AND sp.entry_price IS NULL)
	OR (sp.direction = 'BUY' AND sp.take_profit_price < sp.stop_loss_price) 
	OR (sp.direction = 'SELL' AND sp.take_profit_price > sp.stop_loss_price)	
	AS unfit,  --SOME OF the non-entry_price signals might start outside OF their bounds. if they do then thery're unfit  
	
	--void calcuation here  --how to add entry expiry date? 
	ec.candle_index < sp.candle_index OR sp.the_date > sp.entry_expiry AS isvoid
	
	FROM outcomes sp 
	JOIN earliest_cutoffs ec ON sp.signal_id = ec.signal_id 
	WHERE sp.entry_state = 0 OR sp.last_entry_state <> sp.current_entry_state--what about -1 TO 1 OR vice versa?
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
		WHEN sc.isvoid THEN 'VOID' --expired 
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

















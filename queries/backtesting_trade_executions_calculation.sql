WITH trade_signals AS (
	SELECT * FROM (VALUES 
		('75da431e-bab7-4c66-a251-3eae87f5bd40','2022-03-17T07:22:00'::timestamp,'EUR/JPY','SELL',131.17,130.9,131.56,1440),('a541aee5-a34b-409c-afd2-39127cf517a6','2022-03-17T07:22:00'::timestamp,'EUR/USD','SELL',1.104,1.1016,1.1072,1440),('7b32bac0-72a0-46bd-868c-9720274d639b','2022-03-16T07:08:00'::timestamp,'USD/CAD','SELL',1.274,1.2723,1.2766,1440),('8abdbf98-b475-493b-a21b-028690915ec0','2022-03-16T07:08:00'::timestamp,'EUR/USD','BUY',1.0967,1.0981,1.0947,1440),('2252c776-74ec-4142-ae34-f8539f5b5c9e','2022-03-15T07:51:00'::timestamp,'GBP/USD','BUY',1.3033,1.3053,1.3013,1440),('9e5ebce2-49a4-4c79-8a48-dd40451ca765','2022-03-15T07:51:00'::timestamp,'AUD/USD','BUY',0.7184,0.7209,0.7169,1440),('3cde853e-0bf3-4273-8a75-73535112c51c','2022-03-15T07:51:00'::timestamp,'NZD/USD','BUY',0.6739,0.6764,0.6724,1440),('e0a44343-d21c-4f0a-8303-30c469356a3c','2022-03-14T07:20:00'::timestamp,'USD/CAD','BUY',1.2782,1.2809,1.2761,1440),('77ac9174-3a72-40fd-8544-130821498095','2022-03-15T07:35:00'::timestamp,'USD/JPY','BUY',117.75,117.96,117.59,1440),('6a8e4950-a1dc-426e-8bae-b34a810c9fc6','2022-03-15T08:48:00'::timestamp,'AUD/USD','SELL',0.7258,0.7235,0.7273,1440),('6740f52f-7e5b-4af7-a4c6-5d514d1c9391','2022-03-15T09:14:00'::timestamp,'EUR/USD','BUY',1.0961,1.1012,1.0922,1440),('6409ac29-ed6f-4913-9398-0539b5d36f22','2022-03-15T11:58:00'::timestamp,'NZD/USD','BUY',0.6788,0.6812,0.6769,1440),('049d94b6-fa9d-4d56-814d-e9700c58fb5f','2022-03-10T07:10:00'::timestamp,'USD/CHF','BUY',0.927,0.9287,0.9251,1440),('475d4e0a-2c13-4c8f-9581-eddfbc6a868e','2022-03-10T07:13:00'::timestamp,'GBP/CHF','SELL',1.2216,1.2195,1.2232,1440),('46e50815-1e82-481c-ab04-1fd1f5300036','2022-03-10T07:50:00'::timestamp,'EUR/AUD','SELL',1.5034,1.4913,1.5179,1440),('8ab9ec9a-10bb-4bcf-9b2f-1e44d06379b1','2022-03-08T07:09:00'::timestamp,'EUR/USD','SELL',1.0862,1.0826,1.0883,1440),('5f1351cb-640b-44a5-a54d-caee282ba15d','2022-03-08T08:38:00'::timestamp,'EUR/JPY','BUY',125.99,126.4,125.73,1440),('7bccdb26-d513-4085-9e31-c9b9dc9a3c82','2022-03-08T09:09:00'::timestamp,'GBP/CHF','SELL',1.2158,1.2129,1.2181,1440),('34b3f809-9991-43d1-9d1f-ddd546f91bf4','2022-03-08T12:30:00'::timestamp,'USD/CHF','BUY',0.9259,0.9284,0.9242,1440),('86137cb3-2a68-4dc8-b087-91ed97243bce','2022-03-08T13:19:00'::timestamp,'NZD/USD','SELL',0.6826,0.6808,0.6848,1440)
	) AS ts(signal_id, the_date, instrument, direction, entry_price, take_profit_price, stop_loss_price, duration)
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
trade_tracks AS (
	SELECT ts.signal_id,
	ts.instrument,
	ts.direction,
	ts.entry_price,
	ts.take_profit_price,
	ts.stop_loss_price,
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
	FROM outcomes sp WHERE (entry_state = 0 OR last_entry_state <> current_entry_state) AND candle_index > 1
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
)
SELECT rp.*,
pp.typical_path,
pp.optimistic_path,
pp.pessimistic_path 
FROM results_percent rp
LEFT JOIN profit_paths pp ON pp.signal_id = rp.signal_id 


--SELECT * FROM status_points ORDER BY instrument,the_date   

















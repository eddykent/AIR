WITH trade_signals AS (
	SELECT * FROM (VALUES 
		--('test1','14 Feb 2022 12:30'::timestamp,'GBP/JPY','BUY',154.9,157.1,153.5,1440),
		--('test2','15 Feb 2022 12:30'::timestamp,'EUR/USD','BUY',1.09,1.1,1.085,1440)
		%(trade_signals)s
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
	--ts.entry_price,
	--ts.take_profit_price,
	--ts.stop_loss_price,
	sc.open_price,
	sc.high_price,
	sc.low_price,
	sc.close_price,
	sc.the_date,
	ROW_NUMBER() OVER (PARTITION BY ts.signal_id ORDER BY sc.the_date) AS candle_index
	FROM selected_candles sc 
	JOIN trade_signals ts ON sc.instrument = ts.instrument 
	AND sc.the_date >= ts.the_date AND sc.the_date < ts.the_date + (ts.duration || ' minutes')::INTERVAL
)
SELECT * FROM trade_tracks ORDER BY instrument,the_date   

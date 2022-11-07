

DROP TABLE IF EXISTS backtest_parameters;
CREATE TEMPORARY TABLE backtest_parameters 
AS SELECT 
%(profit_lock_activation)s AS profit_lock_activation, 
%(profit_lock_adjustment)s AS profit_lock_adjustment, 
%(profit_lock_extra)s AS profit_lock_extra
;

DROP TABLE IF EXISTS trade_signals; 
CREATE TEMPORARY TABLE trade_signals 
AS SELECT * FROM (VALUES
	%(trade_signals)s
) AS ts(signal_id, strategy_ref, the_date, instrument, direction, entry_price, entry_cutoff, entry_expiry, take_profit_difference, stop_loss_difference, duration);


DROP TABLE IF EXISTS trade_exits;
CREATE TEMPORARY TABLE trade_exits 
AS SELECT * FROM (VALUES  
	 %(exit_signals)s
) AS te(signal_d, strategy_ref, the_date, instrument, direction);

DROP TABLE IF EXISTS candle_selection;
CREATE TEMPORARY TABLE candle_selection 
AS SELECT * FROM (
	WITH trades AS (
		SELECT 
		ts.signal_id,
		ts.the_date AS start_date, 
		ts.the_date +(ts.duration || ' minutes')::INTERVAL AS end_date,
		ts.instrument
		FROM trade_signals ts
	)
	--sort weekend here
	SELECT 
	signal_id,
	instrument, 
	tsrange(start_date,end_date,'[)') AS the_range
FROM trades 
) ts; 

CREATE INDEX IF NOT EXISTS candle_selection_the_range_idx ON candle_selection USING gist(the_range);
CREATE INDEX IF NOT EXISTS candle_selection_instrument_idx ON candle_selection USING btree(instrument);

DROP TABLE IF EXISTS trade_reels; 
CREATE TEMPORARY TABLE trade_reels 
AS SELECT 
cs.signal_id, 
evt.open_price,
evt.high_price,
evt.low_price,
evt.close_price,
ROW_NUMBER() OVER (PARTITION BY cs.signal_id ORDER BY evt.the_date ASC) AS candle_number
FROM candle_selection cs 
JOIN exchange_value_tick evt ON evt.full_name = cs.instrument 
WHERE cs.the_range @> evt.the_date;

SELECT * FROM trade_reels LIMIT 100


SELECT RANDOM() 



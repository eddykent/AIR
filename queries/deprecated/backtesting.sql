WITH trade_signals AS (
	SELECT * FROM (VALUES 
		('test1','14 Feb 2022 12:30'::timestamp,'GBP/JPY','BUY',154.9,157.1,153.5,1440),
		('test1','14 Feb 2022 12:30'::timestamp,'EUR/USD','BUY',1.09,1.1,1.085,1440)
	) AS ts(signal_id, the_date, instrument, direction, entry_price, take_profit_price, stop_loss_price, duration)
)
SELECT * FROM exchange_value_tick evt 
JOIN trade_signals ts ON evt.full_name = ts.instrument 
AND evt.the_date >= ts.the_date AND evt.the_date <= ts.the_date + (ts.duration || ' minutes')::INTERVAL

SELECT '14 Feb 2022 12:30'::timestamp
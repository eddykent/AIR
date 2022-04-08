
WITH trades AS (
	SELECT ROW_NUMBER() OVER () AS trade_id, * FROM (VALUES 
('USD/JPY','SELL', NULL),
('CAD/JPY','SELL', NULL),
('AUD/JPY','SELL', NULL),
('EUR/JPY','SELL', NULL),
('GBP/JPY','SELL', NULL),
('GBP/CHF','SELL', NULL),
('USD/CHF','SELL', NULL),
('EUR/CHF','SELL', NULL),
('CHF/JPY','SELL', NULL),
('NZD/JPY','SELL', NULL),
('EUR/CAD','BUY', NULL),
('AUD/NZD','SELL', NULL),
('GBP/USD','SELL', NULL),
('CAD/CHF','SELL', NULL),
('EUR/USD','BUY', NULL),
('GBP/AUD','BUY', NULL),
('AUD/CAD','SELL', NULL),
('EUR/NZD','SELL', NULL),
('GBP/CAD','BUY', NULL),
('USD/CAD','BUY', NULL),
('NZD/USD','BUY', NULL),
('AUD/USD','SELL', NULL),
('NZD/CHF','BUY', NULL),
('AUD/CHF','BUY', NULL),
('EUR/GBP','BUY', NULL),
('EUR/AUD','SELL', NULL),
('NZD/CAD','SELL', NULL),
('GBP/NZD','SELL', NULL)
	) AS t(instrument,direction,entry_point)
),
true_ranges AS ( 
	SELECT from_currency, to_currency,
	GREATEST(high_price - low_price, ABS(high_price - LAG(close_price) OVER w),ABS(low_price - LAG(close_price) OVER w)) AS true_range,
	the_date
	FROM exchange_value_tick evt  
	WHERE  from_currency || '/' || to_currency IN (SELECT instrument FROM trades)--from_currency  = ANY(SELECT currency FROM tmp_currencies) AND to_currency = ANY(SELECT currency FROM tmp_currencies)
	AND the_date < (DATE '19 Jan 2022' + INTERVAL '12 hours') --PARAMETER datetime
	AND the_date >= (DATE '19 Jan 2022' + INTERVAL '12 hours'  - INTERVAL '100 days') --PARAMETER look ahead dist (atr)
	WINDOW w AS (PARTITION BY from_currency,to_currency ORDER BY the_date ASC)
),
average_movements AS (
	SELECT from_currency, to_currency, 
	AVG(true_range) / 2.0 AS average_movement 
	FROM true_ranges
	GROUP BY from_currency, to_currency
)
--SELECT from_currency || to_currency, 10* average_movement , 7 * average_movement  FROM average_movements 
,
ranked_by_time AS ( 
	SELECT from_currency, to_currency,
	ROW_NUMBER() OVER w AS candle_number,
	open_price,
	high_price,
	low_price,
	close_price,
	the_date
	FROM exchange_value_tick evt 
	WHERE from_currency || '/' || to_currency IN (SELECT instrument FROM trades)
	AND the_date >= (DATE '19 Jan 2022' + INTERVAL '12 hours')
	AND the_date <= (DATE '19 Jan 2022' + INTERVAL '12 hours' + INTERVAL '1 day') --PARAMETER trade length
	WINDOW w AS (PARTITION BY from_currency, to_currency ORDER BY the_date ASC) 
),
starts AS (
	SELECT
	from_currency, 
	to_currency,
	open_price
	FROM ranked_by_time
	WHERE candle_number = 2 --PARAMETER starting candle (slippage due to calculating)
),
max_candle AS (
	SELECT max(candle_number) AS end_candle FROM ranked_by_time
),
ends AS (
	SELECT 
	from_currency, 
	to_currency,
	close_price
	FROM ranked_by_time, max_candle 
	WHERE candle_number = end_candle
),
find_hits AS (
	SELECT 
	t.trade_id,
	rbt.candle_number, 
	rbt.from_currency, rbt.to_currency, 
	CASE WHEN t.direction = 'BUY' THEN 
		s.open_price  +  am.average_movement * 10 < rbt.high_price
	WHEN t.direction = 'SELL' THEN 
		s.open_price - am.average_movement * 10 > rbt.low_price 
	ELSE FALSE END AS hit_win, 
	CASE WHEN t.direction = 'BUY' THEN 
		s.open_price - am.average_movement * 7 > rbt.low_price 
	WHEN t.direction = 'SELL' THEN 
		s.open_price + am.average_movement * 7 < rbt.high_price 
	ELSE FALSE END AS hit_lose
	FROM ranked_by_time rbt 
	JOIN trades t ON rbt.from_currency || '/' || rbt.to_currency = t.instrument
	JOIN starts s ON s.from_currency = rbt.from_currency AND s.to_currency = rbt.to_currency
	JOIN average_movements am ON am.from_currency = rbt.from_currency AND am.to_currency = rbt.to_currency	
	WHERE candle_number > 2
),
earliest_wins AS (
	SELECT trade_id, 
	MIN(candle_number) AS win_candle
	FROM find_hits
	WHERE hit_win
	GROUP BY trade_id
),
earliest_loses AS (
	SELECT trade_id, 
	MIN(candle_number) AS lose_candle
	FROM find_hits 
	WHERE hit_lose
	GROUP BY trade_id
),
--eod AS (
--	SELECT 
--	starts.from_currency,
--	starts.to_currency,
--	close_price - open_price AS end_period_result
--	FROM starts 
--	JOIN ends ON starts.from_currency = ends.from_currency  AND starts.to_currency  = ends.to_currency 
--),
determine AS (
	SELECT td.trade_id, 
	COALESCE(wins.win_candle,999999) AS win_candle, --I wonder what christmas in the year 3000 would be like... 
	COALESCE(loses.lose_candle, 999999) AS lose_candle, --a radiation fallout mess or a floating christmas tree? 
	wins.win_candle IS NULL AND loses.lose_candle IS NULL AS stagnated,
	--eod.end_period_result
	FROM trades td
	--JOIN eod ON td.from_currency = eod.from_currency  AND td.to_currency = eod.to_currency 
	LEFT JOIN earliest_wins wins ON wins.trade_id = td.trade_id
	LEFT JOIN earliest_loses loses ON loses.trade_id = td.trade_id
)
SELECT 
t.trade_id,
t.instrument, 
t.direction, 
CASE WHEN d.stagnated THEN 'STAGNENT' --if it is large enough it might have won though :) 
	--CASE WHEN t.direction = 'BUY' THEN 
	--	CASE WHEN t.end_period_result > 0.01 THEN 'UP' 
	--		WHEN t.end_period_result  < -0.01 THEN 'DOWN'
	--		ELSE 'STAGNENT'
	--	END
	--WHEN t.direction = 'SELL' THEN
	--	CASE WHEN t.end_period_result < -0.01 THEN 'UP'
	--		WHEN t.end_period_result > 0.01 THEN 'DOWN'
	--		ELSE 'STAGNENT'
	--	END
	--END
	WHEN d.win_candle < d.lose_candle  THEN 'WON'
	ELSE 'LOST'
END AS dice,
CASE WHEN d.stagnated THEN NULL --if it is large enough it might have won though :) 
	WHEN d.win_candle < d.lose_candle  THEN d.win_candle
	ELSE d.lose_candle
END AS candle_index
FROM 
determine d 
JOIN trades t ON t.trade_id  = d.trade_id










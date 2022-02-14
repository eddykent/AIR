-- SQL for calculating the RSI of all currency pairs
DROP TABLE IF EXISTS tmp_currencies; 
DROP TABLE IF EXISTS tmp_all_rates_of_change; 

CREATE OR REPLACE FUNCTION _ema_func(state DOUBLE PRECISION, inval DOUBLE PRECISION, alpha DOUBLE PRECISION)
  RETURNS DOUBLE PRECISION
  LANGUAGE plpgsql AS $$
BEGIN
  RETURN CASE
         WHEN state IS NULL THEN inval
         ELSE alpha * inval + (1-alpha) * state
         END;
END
$$;

CREATE OR REPLACE AGGREGATE EMA(DOUBLE PRECISION, DOUBLE PRECISION) (sfunc = _ema_func, stype = DOUBLE PRECISION);


WITH ccs AS (
	SELECT UNNEST(ARRAY['AUD','CAD','CHF','EUR','GBP','NZD','JPY','USD']) AS currency
)
SELECT currency INTO TEMPORARY TABLE tmp_currencies FROM ccs;



WITH rates_of_change AS (
	SELECT from_currency, to_currency,
	(close_price - LAG(close_price,1) OVER w)  AS rate_of_change,
	close_price,
	the_date 
	FROM exchange_value_tick evt 
	WHERE from_currency  = ANY(SELECT currency FROM tmp_currencies) AND to_currency = ANY(SELECT currency FROM tmp_currencies)
	AND the_date < (DATE '07 Feb 2022' + INTERVAL '21 hours')
	AND the_date >= (DATE '07 Feb 2022' - INTERVAL '20 days' + INTERVAL '21 hours')
	WINDOW w AS (PARTITION BY from_currency, to_currency ORDER BY the_date ASC)	
),
all_dates AS (
	SELECT DISTINCT the_date FROM rates_of_change
),
time_indexs AS (
	SELECT the_date, ROW_NUMBER() OVER (ORDER BY the_date) AS time_index
	FROM all_dates 
),
time_indexed_candles AS (
	SELECT c.from_currency,
	c.to_currency,
	c.rate_of_change,
	c.close_price,
	c.the_date,
	t.time_index 
	FROM rates_of_change c 
	JOIN time_indexs t ON c.the_date = t.the_date
)
SELECT from_currency, to_currency, close_price, rate_of_change, the_date, time_index INTO TEMPORARY TABLE tmp_all_rates_of_change FROM time_indexed_candles;

WITH up_down_moves AS (
	SELECT from_currency, to_currency,
	SUM(GREATEST(rate_of_change,0)) OVER w AS up_moves,
	SUM(ABS(LEAST(rate_of_change,0))) OVER w AS down_moves,
	GREATEST(rate_of_change,0) AS up_move,
	ABS(LEAST(rate_of_change,0)) AS down_move,
	the_date,
	time_index
	FROM tmp_all_rates_of_change taroc 
	WINDOW w AS (PARTITION BY from_currency, to_currency ORDER BY the_date ASC ROWS BETWEEN (14-1) PRECEDING AND CURRENT ROW)	
),
avg_moves AS (
	SELECT from_currency, to_currency,
	up_moves,
	down_moves,
	EMA(CASE WHEN time_index < 14 THEN up_moves ELSE up_move END, CASE WHEN time_index < 14 THEN 1.0 ELSE 1.0 / 14.0 END ) OVER w AS avg_moves_up,
	EMA(CASE WHEN time_index < 14 THEN down_moves ELSE down_move END, CASE WHEN time_index < 14 THEN 1.0 ELSE 1.0 / 14.0 END ) OVER w AS avg_moves_down,
	the_date,
	time_index
	FROM up_down_moves 
	WINDOW w AS (PARTITION BY from_currency, to_currency ORDER BY the_date)	
),
rs_calc AS ( 
	SELECT from_currency, to_currency, 
	CASE WHEN avg_moves_down = 0 THEN 1.0 ELSE 1.0 - (1.0 / (1.0 + (avg_moves_up / avg_moves_down)) ) END  AS rsi,
	--CASE WHEN down_moves = 0 THEN 1.0 ELSE 1.0 - (1.0 / (1.0 + (up_moves / down_moves)) ) END  AS rsi2, --WRONG
	the_date,
	time_index
	FROM avg_moves
)
SELECT * FROM rs_calc 
WHERE from_currency = 'EUR' AND to_currency = 'USD'
ORDER BY the_date ASC


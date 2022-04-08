
-- Calculate the MACD for each currency


DROP TABLE IF EXISTS tmp_currencies;

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

WITH close_prices AS (
	SELECT from_currency, to_currency,
	close_price,
	the_date
	FROM exchange_value_tick evt  
	WHERE from_currency  = ANY(SELECT currency FROM tmp_currencies) AND to_currency = ANY(SELECT currency FROM tmp_currencies)
	AND the_date < (DATE '06 Jan 2022' + INTERVAL '12 hours')
	AND the_date >= (DATE '06 Jan 2022' - INTERVAL '10 days' + INTERVAL '12 hours')
),
moving_averages AS (
	SELECT from_currency, to_currency, 
	EMA(close_price, 1.0 / 26.0) OVER w AS slow_price,
	EMA(close_price, 1.0 / 12.0) OVER w AS fast_price,
	the_date 
	FROM close_prices 
	WINDOW w AS (PARTITION BY from_currency, to_currency ORDER BY the_date ASC)
),
macd_calculation AS (
	SELECT from_currency, to_currency, 
	slow_price - fast_price AS macd_line,
	EMA(slow_price - fast_price, 1.0 / 8.0) OVER w AS signal_line,
	the_date 
	FROM moving_averages
	WINDOW w AS (PARTITION BY from_currency, to_currency ORDER BY the_date ASC)
) --SCALE? 
SELECT * FROM macd_calculation 
WHERE from_currency = 'EUR' AND to_currency = 'USD'
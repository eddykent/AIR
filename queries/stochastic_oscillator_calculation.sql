
--Stochastic oscillator calculation 

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

WITH periods AS (
	SELECT from_currency, to_currency,
	MAX(high_price) OVER w AS high_price,
	MIN(low_price) OVER w AS low_price,
	close_price,
	the_date
	FROM exchange_value_tick evt  
	WHERE from_currency  = ANY(SELECT currency FROM tmp_currencies) AND to_currency = ANY(SELECT currency FROM tmp_currencies)
	AND the_date < (DATE '15 Dec 2021' + INTERVAL '12 hours')
	AND the_date >= (DATE '15 Dec 2021' - INTERVAL '400 days' + INTERVAL '12 hours')
	WINDOW w AS (PARTITION BY from_currency,to_currency ORDER BY the_date ASC ROWS BETWEEN (14-1) PRECEDING AND CURRENT ROW)
),
calc_k AS (
	SELECT from_currency, to_currency,
	(close_price - low_price) / (high_price - low_price) AS k,
	the_date
	FROM periods
),
calc_d AS (
	SELECT from_currency, to_currency,
	k,
	EMA(k,1.0 / 3.0) OVER w AS d, --incorrect? use SMA
	the_date
	FROM calc_k
	WINDOW w AS (PARTITION BY from_currency, to_currency ORDER BY the_date ASC)
)
SELECT from_currency, to_currency,k, d, the_date FROM calc_d
--slow d? 
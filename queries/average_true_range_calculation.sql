

--query that calcualtes the average true range of a set of candles

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

WITH true_ranges AS (
	SELECT from_currency, to_currency,
	GREATEST(high_price - low_price, ABS(high_price - LAG(close_price) OVER w),ABS(low_price - LAG(close_price) OVER w)) AS true_range,
	the_date
	FROM exchange_value_tick evt  
	WHERE from_currency  = ANY(SELECT currency FROM tmp_currencies) AND to_currency = ANY(SELECT currency FROM tmp_currencies)
	AND the_date < (DATE '15 Dec 2021' + INTERVAL '12 hours')
	AND the_date >= (DATE '15 Dec 2021' - INTERVAL '400 days' + INTERVAL '12 hours')
	WINDOW w AS (PARTITION BY from_currency,to_currency ORDER BY the_date ASC)
), 
max_true_ranges AS (
	SELECT from_currency, to_currency, MAX(true_range) OVER w AS max_true_range,
	the_date
	FROM true_ranges 
	WINDOW w AS (PARTITION BY from_currency, to_currency ORDER BY the_date ASC ROWS BETWEEN (200-1) PRECEDING AND CURRENT ROW)
	--GROUP BY from_currency, to_currency
),
scaled_true_ranges AS (
	SELECT tr.from_currency, tr.to_currency, 
	tr.true_range / mtr.max_true_range AS scaled_true_range,
	tr.the_date 
	FROM true_ranges tr 
	JOIN max_true_ranges mtr 
	ON tr.from_currency = mtr.from_currency AND tr.to_currency = mtr.to_currency AND tr.the_date = mtr.the_date
),
average_true_ranges AS (
	SELECT from_currency, to_currency,
	EMA(scaled_true_range,1.0 / 14.0) OVER w AS average_true_range,
	the_date
	FROM scaled_true_ranges
	WINDOW w AS (PARTITION BY from_currency, to_currency ORDER BY the_date ASC)
)
SELECT from_currency, to_currency, average_true_range, the_date
FROM average_true_ranges


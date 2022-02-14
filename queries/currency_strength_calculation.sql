--Query for selecting currency strength movements
DROP TABLE IF EXISTS tmp_currencies; 
DROP TABLE IF EXISTS tmp_candles; 
DROP TABLE IF EXISTS tmp_all_rates_of_change; 
DROP TABLE IF EXISTS tmp_friends;
DROP TABLE IF EXISTS tmp_enemies;
DROP TABLE IF EXISTS tmp_all_movements;


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

WITH candle_indexs AS (
	SELECT from_currency, to_currency,
	open_price,
	high_price,
	low_price,
	close_price,
	the_date, 
	the_date::DATE AS date_day,
	(EXTRACT(MINUTE FROM the_date) + 60 * EXTRACT (HOUR FROM the_date))::INT / 60 AS candle_index 
	FROM exchange_value_tick evt 
	WHERE from_currency  = ANY(SELECT currency FROM tmp_currencies) AND to_currency = ANY(SELECT currency FROM tmp_currencies)
	AND the_date < (DATE '15 Dec 2021' + INTERVAL '12 hours')
	AND the_date >= (DATE '15 Dec 2021' - INTERVAL '400 days' + INTERVAL '12 hours')
),
candles_start_end AS (
	SELECT from_currency,
	to_currency, 
	FIRST_VALUE(open_price) OVER (PARTITION BY from_currency, to_currency, date_day, candle_index ORDER BY the_date ASC) AS open_price,
	high_price AS high_price, 
	low_price AS low_price, 
	FIRST_VALUE(close_price) OVER (PARTITION BY from_currency, to_currency, date_day, candle_index ORDER BY the_date DESC) AS close_price, 
	the_date AS the_date,
	date_day, 
	candle_index 
	FROM candle_indexs
),
candles AS (
	SELECT from_currency, 
	to_currency, 
	AVG(open_price) AS open_price, 
	MAX(high_price) AS high_price,
	MIN(low_price) AS low_price,
	AVG(close_price) AS close_price,
	MIN(the_date) AS the_date
	FROM candles_start_end
	GROUP BY from_currency, to_currency, date_day, candle_index
),
all_dates AS (
	SELECT DISTINCT the_date FROM candles
),
time_indexs AS (
	SELECT the_date, ROW_NUMBER() OVER (ORDER BY the_date) AS time_index
	FROM all_dates 
),
time_indexed_candles AS (
	SELECT c.from_currency,
	c.to_currency,
	c.open_price,
	c.high_price,
	c.low_price,
	c.close_price,
	c.the_date,
	t.time_index 
	FROM candles c 
	JOIN time_indexs t ON c.the_date = t.the_date
)
SELECT * INTO TEMPORARY TABLE tmp_candles FROM time_indexed_candles;

WITH rates_of_change AS (
	SELECT from_currency, to_currency,
	((close_price - LAG(close_price,16) OVER w) / close_price) * 100  AS percent_changed,
	the_date 
	FROM tmp_candles
	WINDOW w AS (PARTITION BY from_currency, to_currency ORDER BY the_date ASC)	
)
SELECT from_currency, to_currency, percent_changed, the_date INTO TEMPORARY TABLE tmp_all_rates_of_change FROM rates_of_change;

SELECT cs.currency, roc.percent_changed, roc.the_date 
INTO TEMPORARY TABLE tmp_friends
FROM tmp_all_rates_of_change roc
JOIN tmp_currencies cs ON roc.from_currency = cs.currency;

SELECT cs.currency, roc.percent_changed, roc.the_date 
INTO TEMPORARY TABLE tmp_enemies
FROM tmp_all_rates_of_change roc
JOIN tmp_currencies cs ON roc.to_currency = cs.currency;

CREATE INDEX tmp_friends_currency_idx ON tmp_friends USING btree(currency);
CREATE INDEX tmp_friends_the_date_idx ON tmp_friends USING btree(the_date);

CREATE INDEX tmp_enemies_currency_idx ON tmp_enemies USING btree(currency);
CREATE INDEX tmp_enemies_the_date_idx ON tmp_enemies USING btree(the_date);

WITH all_dates_pairs AS (
	SELECT DISTINCT the_date, currency FROM tmp_all_rates_of_change, tmp_currencies ORDER BY the_date
),
all_movements AS (
	SELECT c.currency, 
	c.the_date AS the_date,
	f.percent_changed
	FROM all_dates_pairs c
	JOIN tmp_friends f ON c.currency = f.currency AND c.the_date = f.the_date
	UNION 
	SELECT c.currency,
	c.the_date AS the_date,
	-e.percent_changed
	FROM all_dates_pairs c
	JOIN tmp_enemies e ON c.currency = e.currency AND c.the_date = e.the_date
),
movements AS (
	SELECT currency, 
	the_date,
	SUM(percent_changed) AS movement
	FROM all_movements 
	GROUP BY currency, the_date
),
ranked_movements AS (
	SELECT m.currency, 
	m.movement, 
	m.the_date,
	RANK() OVER (PARTITION BY m.the_date ORDER BY m.movement ASC) AS ranked
	FROM movements m
),
average_movements AS (
	SELECT rm.currency, 
	rm.movement,
	rm.ranked,
	EMA(rm.movement,(1.0/3.0)::DOUBLE PRECISION) OVER w AS average_movement,
	EMA(rm.ranked, (1.0/3.0)::DOUBLE PRECISION) OVER w AS average_rank,
	rm.the_date
	FROM ranked_movements rm
	WHERE NULLIF(rm.movement,0) IS NOT NULL
	WINDOW w AS (PARTITION BY rm.currency ORDER BY rm.the_date ASC)
),
ranked_averages AS (
	SELECT am.currency, 
	am.movement, 
	am.ranked,
	am.the_date,
	am.average_movement,
	am.average_rank,
	RANK() OVER (PARTITION BY am.the_date ORDER BY am.average_movement) AS ranked_average
	FROM average_movements am
)
SELECT the_date, currency, movement, average_movement, ranked, average_rank, ranked_average INTO TEMPORARY TABLE tmp_all_movements FROM ranked_averages;

SELECT the_date,
json_object_agg(currency, 
	json_build_object(
		'movement',movement,
		'average_movement',average_movement,
		'rank',ranked,
		'average_rank',average_rank,
		'ranked_average',ranked_average
	)
)
FROM tmp_all_movements
--AND currency = 'EUR'
GROUP BY the_date
HAVING SUM(1) = (SELECT ARRAY_LENGTH(ARRAY[1,2,3,4,5,6,7,8],1))
ORDER BY the_date 


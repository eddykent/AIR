--query for finding all correlations between  each currency pair that we are interested in. 
--these correlations are then given as a time series which can be used in a clustering
--method for diversifications, and for grouping highly correlated things together

DROP TABLE IF EXISTS tmp_currencies; 
DROP TABLE IF EXISTS tmp_candles; --everything


WITH ccs AS (
	SELECT UNNEST(%(currencies)s) AS currency
)
SELECT currency INTO TEMPORARY TABLE tmp_currencies FROM ccs;

--build candles of our chosen chart size 
WITH candle_indexs AS (
	SELECT from_currency, to_currency,
	open_price,
	high_price,
	low_price,
	close_price,
	TO_TIMESTAMP (FLOOR(( EXTRACT ('EPOCH' FROM (the_date )) ) / (60*15) ) * (60*15)) AT TIME ZONE 'UTC' AS the_date,
	the_date::DATE AS date_day, --day_index ? 
	--ROW_NUMBER() OVER (PARTITION BY from_currency, to_currency ORDER BY DATE(the_date)) AS day_index, --doesnt work :( needs to be done in separate cte
	(EXTRACT(MINUTE FROM the_date) + 60 * EXTRACT (HOUR FROM the_date))::INT / %(chart_resolution)s::INT AS candle_index 
	FROM exchange_value_tick evt 
	WHERE from_currency  = ANY(SELECT currency FROM tmp_currencies) AND to_currency = ANY(SELECT currency FROM tmp_currencies)
	AND the_date < (DATE %(the_date)s + INTERVAL '%(hour)s hours') --what about IF we want TO START ON 45 mins?
	AND the_date >= (DATE %(the_date)s - INTERVAL '%(days_back)s days' + INTERVAL '%(hour)s hours') --600 = 400 + 200 (days_back + normalisation_window)
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
candles_bad_dates AS (
	SELECT from_currency, 
	to_currency, 
	AVG(open_price) AS open_price, 
	MAX(high_price) AS high_price,
	MIN(low_price) AS low_price,
	AVG(close_price) AS close_price,
	MIN(the_date) AS the_date  --nicely cleans up slightly off-15 candles 
	FROM candles_start_end
	GROUP BY from_currency, to_currency, date_day, candle_index
),
candles AS (
	SELECT from_currency,
	to_currency,
	open_price,
	high_price,
	low_price,
	close_price,
	TO_TIMESTAMP (FLOOR(( EXTRACT ('EPOCH' FROM (the_date )) ) / (60*%(chart_resolution)s::INT) ) * (60*%(chart_resolution)s::INT)) AT TIME ZONE 'UTC' AS the_date --round down the offset candles 
	FROM candles_bad_dates
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

WITH close_prices AS (
	SELECT 
	the_date,
	from_currency, 
	to_currency, 
	close_price
	FROM tmp_candles
),
correlations AS (
	SELECT c1.the_date, 
	c1.from_currency AS candle1_from_currency,
	c1.to_currency AS candle1_to_currency,
	c2.from_currency AS candle2_from_currency,
	c2.to_currency AS candle2_to_currency, 
	CORR(c1.close_price,c2.close_price) OVER w AS correlation,
	REGR_SLOPE(c1.close_price,c2.close_price) OVER w AS slope
	FROM tmp_candles c1 
	JOIN tmp_candles c2 ON c1.the_date = c2.the_date 
	WINDOW w AS (
		PARTITION BY c1.from_currency,c1.to_currency,c2.from_currency,c2.to_currency 
		ORDER BY c1.the_date ASC
		ROWS BETWEEN (%(correlation_window)s::INT - 1) PRECEDING AND CURRENT ROW
	)
),
build_json_rows AS (
	SELECT the_date,
	count(1) AS m,
	candle1_from_currency, 
	candle1_to_currency,
	json_object_agg( 
		candle2_from_currency || '/' || candle2_to_currency,
		json_build_object(
			'correlation',correlation,
			'slope',slope,
			'distance',1.0-abs(correlation) --put highly correlated stuff together
		)
	) AS correlation_rows
	FROM correlations
	GROUP BY the_date,candle1_from_currency,candle1_to_currency 
)
SELECT the_date, count(1) AS n,
json_object_agg(
	candle1_from_currency || '/' || candle1_to_currency,
	json_build_object(
		'with',correlation_rows,
		'm',m
	) 
) AS correlation_matrix
FROM build_json_rows
GROUP BY the_date 
ORDER BY the_date DESC































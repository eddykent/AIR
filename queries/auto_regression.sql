--query for finding all correlations between  each currency pair that we are interested in. 

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

--use the correlations to find hints of price movement? this can then be fed into the NN 
--pluralise with more lag times to predict more future candles?
--pluralise to create one prediction per day ready for a NN 
--reduce to 1h chart instead -- breaks! use 4h chart
WITH prev_prices AS (
	SELECT 
	the_date,
	from_currency, 
	to_currency, 
	open_price, 
	high_price,
	low_price,
	close_price, 
	LAG(close_price,1) OVER w AS previous_close_price 
	FROM tmp_candles
	WINDOW w AS (PARTITION BY from_currency, to_currency ORDER BY the_date ASC)
),
percent_changes AS (
	SELECT the_date, 
	from_currency, 
	to_currency, 
	open_price,
	high_price,
	low_price,
	close_price, 
	previous_close_price,
	close_price - previous_close_price AS diff_close_price,
	((close_price - previous_close_price) / previous_close_price)* 100 AS percent_change
	FROM prev_prices 
),
look_backs AS (
	SELECT generate_series(1,%(correlation_lags)s::INT,1) AS lag_index
),
lagged_candles AS (
	SELECT the_date,
	from_currency, 
	to_currency, 
	open_price,
	high_price,
	low_price,
	close_price, 
	previous_close_price,
	diff_close_price, 
	percent_change,
	lag_index,
	LAG(percent_change,lag_index) OVER (PARTITION BY from_currency,to_currency,lag_index ORDER BY the_date) AS lag_percent_change
	FROM percent_changes, look_backs
),
all_changes AS (
	SELECT candle1.the_date,
	candle1.from_currency AS candle1_from_currency, candle1.to_currency AS candle1_to_currency, 
	candle2.from_currency AS candle2_from_currency, candle2.to_currency AS candle2_to_currency,
	candle1.percent_change AS candle1_percent_change, 
	candle2.percent_change AS candle2_percent_change,--need for calculating the candle2_lead_lag
	candle2.lag_percent_change AS candle2_lag_percent_change,
	candle2.lag_index
	FROM lagged_candles candle1
	JOIN lagged_candles candle2 ON candle1.the_date = candle2.the_date
	WHERE candle1.lag_index = 1 --dont select all the other lags of candle 1 as they are not needed 
	ORDER BY candle1.the_date ASC
),
correlations AS (
	SELECT the_date,
	candle1_from_currency, candle1_to_currency, candle2_from_currency, candle2_to_currency,
	candle1_percent_change,
	candle2_percent_change, 
	candle2_lag_percent_change,
	CORR(candle1_percent_change,candle2_lag_percent_change) OVER w AS correlation, --correlates with the next percent CHANGE
	REGR_SLOPE(candle1_percent_change, candle2_lag_percent_change) OVER w AS slope,
	REGR_INTERCEPT(candle1_percent_change, candle2_lag_percent_change) OVER w AS intercept,
	lag_index 
	FROM all_changes
	WINDOW w AS (
		PARTITION BY candle1_from_currency, candle1_to_currency, candle2_from_currency, candle2_to_currency, lag_index
		ORDER BY the_date ASC ROWS BETWEEN (%(correlation_window)s::INT -1) PRECEDING AND CURRENT ROW --correlate last 8 entries - works well with low correlations on 12 Jan 2022 AT 12pm.. so does high correl! 
	)
--	GROUP BY candle1_from_currency, candle1_to_currency, candle2_from_currency, candle2_to_currency
),
candle2_lead_lag AS ( --this IS confusing, but it needs TO have the current SET OF candles TO predict the NEXT one NOT the previous ones 
	SELECT *,
	CASE WHEN lag_index = 1 THEN candle2_percent_change ELSE LAG(candle2_lag_percent_change,1) OVER w END AS candle2_leadlag
	FROM correlations
	WINDOW w AS (
		PARTITION BY candle1_from_currency, candle1_to_currency, candle2_from_currency, candle2_to_currency, lag_index
		ORDER BY the_date ASC
	)
)
--SELECT the_date, candle2_percent_change, candle2_lag_percent_change, candle2_leadlag, lag_index FROM candle2_lead_lag WHERE candle1_from_currency = 'EUR' AND candle1_to_currency = 'USD' AND candle2_from_currency = 'USD' AND candle2_to_currency ='JPY'
--ORDER BY the_date ASC, lag_index DESC 
,
collected_percent_changes AS (
	SELECT 
	the_date,
	candle1_from_currency AS from_currency,
	candle1_to_currency AS to_currency, 
	--lag_index, --intercept causes issues
	SUM(CASE WHEN ABS(correlation) > %(correlation_threshold)s::DOUBLE PRECISION THEN (slope*candle2_leadlag) ELSE 0 END) AS next_percent_changes,
	SUM(CASE WHEN ABS(correlation) > %(correlation_threshold)s::DOUBLE PRECISION THEN (slope*candle2_leadlag)*(slope*candle2_leadlag) ELSE 0 END) AS next_percent_changes_squared,
	SUM(CASE WHEN ABS(correlation) > %(correlation_threshold)s::DOUBLE PRECISION THEN 1 ELSE 0 END) AS n_percent_changes
	FROM candle2_lead_lag 
	GROUP BY the_date, candle1_from_currency, candle1_to_currency--, candle2_lead_percent_change
),
average_percent_changes AS (
	SELECT the_date, 
	from_currency,
	to_currency, 
	CASE WHEN n_percent_changes = 0 THEN 0 ELSE next_percent_changes / n_percent_changes END AS predicted_percent_change,
	CASE WHEN n_percent_changes = 0 THEN 1 ELSE 
		(next_percent_changes_squared / n_percent_changes) - ((next_percent_changes / n_percent_changes)*(next_percent_changes / n_percent_changes))
	END AS percent_change_variance,
	n_percent_changes
	FROM collected_percent_changes 
)
SELECT 
the_date, COUNT(1) AS n,
json_object_agg(
	from_currency || '/' || to_currency, JSON_BUILD_OBJECT(
		'delta',predicted_percent_change,
		'delta_variance',percent_change_variance,
		'delta_n',n_percent_changes,
		'instrument',from_currency || '/' || to_currency,
		'the_date',the_date
	)
) AS correlation_hints
FROM average_percent_changes
GROUP BY the_date 
ORDER BY the_date DESC




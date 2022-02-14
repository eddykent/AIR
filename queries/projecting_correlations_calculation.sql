--query for finding all correlations between  each currency pair that we are interested in. 

DROP TABLE IF EXISTS tmp_currencies; 
DROP TABLE IF EXISTS tmp_candles; --everything


WITH ccs AS (
	SELECT UNNEST(ARRAY['AUD','CAD','CHF','EUR','GBP','NZD','JPY','USD']) AS currency
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
	(EXTRACT(MINUTE FROM the_date) + 60 * EXTRACT (HOUR FROM the_date))::INT / 240::INT AS candle_index 
	FROM exchange_value_tick evt 
	WHERE from_currency  = ANY(SELECT currency FROM tmp_currencies) AND to_currency = ANY(SELECT currency FROM tmp_currencies)
	AND the_date < (DATE '24 Jan 2022' + INTERVAL '8 hours') --what about IF we want TO START ON 45 mins?
	AND the_date >= (DATE '24 Jan 2022' - INTERVAL '200 days' - INTERVAL '20 days' + INTERVAL '8 hours') --600 = 400 + 200 (days_back + normalisation_window)
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
	TO_TIMESTAMP (FLOOR(( EXTRACT ('EPOCH' FROM (the_date )) ) / (60*240::INT) ) * (60*240::INT)) AT TIME ZONE 'UTC' AS the_date --round down the offset candles 
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
look_aheads AS (
	SELECT generate_series(1,4,1) AS lead_index
),
leading_candles AS (
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
	lead_index,
	LEAD(percent_change,lead_index) OVER (PARTITION BY from_currency, to_currency, lead_index ORDER BY the_date ASC ) AS lead_percent_change
	FROM percent_changes, look_aheads
),
all_changes AS (
	SELECT candle1.the_date,
	candle1.from_currency AS candle1_from_currency, candle1.to_currency AS candle1_to_currency, 
	candle2.from_currency AS candle2_from_currency, candle2.to_currency AS candle2_to_currency,
	candle1.percent_change AS candle1_percent_change, 
	candle2.percent_change AS candle2_percent_change, 
	candle2.lead_index,
	--lag or lead?
	candle1.lead_percent_change AS candle1_lead_percent_change,
	candle2.lead_percent_change AS candle2_lead_percent_change
	FROM leading_candles candle1
	JOIN leading_candles candle2 ON candle1.the_date = candle2.the_date
	WHERE candle1.lead_index = 1
	ORDER BY candle1.the_date ASC
),
correlations AS (
	SELECT the_date,
	candle1_from_currency, candle1_to_currency, candle2_from_currency, candle2_to_currency,
	candle1_percent_change,
	candle2_percent_change,
	candle1_lead_percent_change,
	candle2_lead_percent_change,
	CORR(candle1_percent_change,candle2_lead_percent_change) OVER w AS correlation, --correlates with the next percent change
	lead_index 
	FROM all_changes
	WINDOW w AS (
		PARTITION BY candle1_from_currency, candle1_to_currency, candle2_from_currency, candle2_to_currency, lead_index
		ORDER BY the_date ASC ROWS BETWEEN 19 PRECEDING AND CURRENT ROW --correlate LAST 20 entries
	)
--	GROUP BY candle1_from_currency, candle1_to_currency, candle2_from_currency, candle2_to_currency
),
predicted_percent_changes AS (
	SELECT 
	the_date,
	candle2_from_currency AS from_currency,
	candle2_to_currency AS to_currency, 
	lead_index,
	AVG(CASE WHEN ABS(correlation) > 0.30 THEN candle1_percent_change * correlation ELSE 0 END) AS predicted_percent_change--,
	--ARRAY_AGG(candle1_from_currency || '/' || candle1_to_currency ORDER BY candle1_from_currency,candle1_to_currency) AS other_currency,
	--ARRAY_AGG(candle1_percent_change ORDER BY candle1_from_currency,candle1_to_currency) AS percent_changes,
	--ARRAY_AGG(correlation ORDER BY candle1_from_currency,candle1_to_currency) AS correlations_to_lead_candle2
	--candle2_lead_percent_change AS actual_percent_change
	FROM correlations 
	GROUP BY the_date, candle2_from_currency, candle2_to_currency, lead_index--, candle2_lead_percent_change
),
total_percent_changes AS (
	SELECT the_date, 
	from_currency,
	to_currency, 
	SUM(predicted_percent_change) AS predicted_percent_change
	FROM predicted_percent_changes 
	GROUP BY the_date, from_currency, to_currency
)
--SELECT 
--the_date, COUNT(1) AS n,
--json_object_agg(
--	from_currency || '/' || to_currency, JSON_BUILD_OBJECT(
--		'predicted_percent_change',predicted_percent_change,
--		'the_date',the_date
--) AS correlation_hints
--FROM total_percent_changes
--GROUP BY the_date 
--ORDER BY the_date DESC

--use the following to get a trading plan instead 
SELECT 
the_date,
from_currency,
to_currency, 
predicted_percent_change,
'(''' || from_currency || '/' || to_currency || ''',''' || CASE WHEN predicted_percent_change > 0 THEN 'BUY' ELSE 'SELL' END || ''', NULL),' AS the_tuple
FROM total_percent_changes
WHERE the_date = '2022-01-24 04:00:00.000'
ORDER BY ABS(predicted_percent_change) DESC





--SELECT * FROM exchange_value_tick evt  WHERE from_currency = 'USD' AND to_currency = 'JPY' AND the_date > '2022-01-20 12:00:00.000'
 






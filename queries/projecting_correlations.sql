--query for finding all correlations between  each currency pair that we are interested in. 

DROP TABLE IF EXISTS tmp_currencies; 
DROP TABLE IF EXISTS tmp_candles; --everything


WITH ccs AS (
	SELECT UNNEST(%(currencies)s) AS currency
)
SELECT currency INTO TEMPORARY TABLE tmp_currencies FROM ccs;

--build candles of our chosen chart size - SUGGEST 4H FOR THIS
WITH selected_candles AS (
	SELECT from_currency, to_currency,
	open_price,
	high_price,
	low_price,
	close_price, 
	the_date - INTERVAL '%(candle_offset)s mins' AS the_date
	FROM exchange_value_tick evt 
	WHERE from_currency  = ANY(SELECT currency FROM tmp_currencies) AND to_currency = ANY(SELECT currency FROM tmp_currencies)
	AND the_date < (DATE %(the_date)s + INTERVAL '%(hour)s hours')
	AND the_date >= (DATE %(the_date)s - INTERVAL '%(days_back)s days' + INTERVAL '%(hour)s hours') --600 = 400 + 200 (days_back + normalisation_window)
), 
candle_indexs AS (
	SELECT from_currency, to_currency,
	open_price,
	high_price,
	low_price,
	close_price,
	TO_TIMESTAMP (FLOOR(( EXTRACT ('EPOCH' FROM (the_date )) ) / (60*15) ) * (60*15)) AT TIME ZONE 'UTC' AS the_date,
	the_date::DATE AS date_day, --day_index ? 
	--the_date,
	(EXTRACT(MINUTE FROM the_date) + 60 * EXTRACT (HOUR FROM the_date))::INT / %(chart_resolution)s::INT AS candle_index
	FROM selected_candles
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
	c.the_date + INTERVAL '%(candle_offset)s mins' AS the_date,
	t.time_index 
	FROM candles c 
	JOIN time_indexs t ON c.the_date = t.the_date
)
SELECT * INTO TEMPORARY TABLE tmp_candles FROM time_indexed_candles;

--use the correlations to find hints of price movement? this can then be fed into the NN 
--pluralise with more lag times to predict more future candles -- unsure?
--pluralise to create one prediction per day ready for a NN - done
--reduce to 1h chart instead --done (testing reveals it seems to only work for 4h and up)
WITH percent_changes AS (
	SELECT the_date, 
	from_currency, 
	to_currency, 
	open_price,
	high_price,
	low_price,
	close_price, 
	close_price - LAG(close_price,1) OVER w AS diff_close_price,
	((close_price - LAG(close_price,1) OVER w) / LAG(close_price,1) OVER w)* 100 AS percent_change
	FROM tmp_candles 
	WINDOW w AS (PARTITION BY from_currency, to_currency ORDER BY the_date ASC)
),
look_aheads AS (
	SELECT generate_series(1,%(correlation_lags)s::INT,1) AS lead_index --ONLY USE A FEW LEAD CANDLES (further away candles will be less accurate) 
),
all_changes AS (
	SELECT candle1.the_date,
	candle1.from_currency AS candle1_from_currency, candle1.to_currency AS candle1_to_currency, 
	candle2.from_currency AS candle2_from_currency, candle2.to_currency AS candle2_to_currency,
	candle1.percent_change AS candle1_percent_change, 
	--candle2.percent_change AS candle2_percent_change, 
	look_aheads.lead_index,
	--lag or lead?
	--LEAD(candle1.percent_change,look_aheads.lead_index) OVER (PARTITION BY candle1.from_currency, candle1.to_currency ORDER BY candle1.the_date ASC ) AS candle1_lead_percent_change,
	LEAD(candle2.percent_change,look_aheads.lead_index) OVER (PARTITION BY candle2.from_currency, candle2.to_currency ORDER BY candle2.the_date ASC ) AS candle2_lead_percent_change
	FROM percent_changes candle1
	JOIN percent_changes candle2 ON candle1.the_date = candle2.the_date,
	look_aheads
	ORDER BY candle1.the_date ASC
),
correlations AS (
	SELECT the_date,
	candle1_from_currency, candle1_to_currency, candle2_from_currency, candle2_to_currency,
	candle1_percent_change,
	--candle2_percent_change,
	--candle1_lead_percent_change,
	candle2_lead_percent_change,
	CORR(candle1_percent_change,candle2_lead_percent_change) OVER w AS correlation, --correlates with the next percent change
	lead_index 
	FROM all_changes
	WINDOW w AS (
		PARTITION BY candle1_from_currency, candle1_to_currency, candle2_from_currency, candle2_to_currency 
		ORDER BY the_date ASC ROWS BETWEEN (%(correlation_window)s::INT - 1) PRECEDING AND CURRENT ROW --correlate LAST 20 entries
	)
--	GROUP BY candle1_from_currency, candle1_to_currency, candle2_from_currency, candle2_to_currency
),
predicted_percent_changes AS (
	SELECT 
	the_date, --+ INTERVAL '%(chart_resolution)s minutes' AS the_date, --this is actually the previous date! -- we are looking AT candle2 which IS LEADING. So we must move the date forwards
	--Actually, the selection process only selects candles that are completely behind the current date! Therefore we need this to remain as the "date in which the data was calculated from"
	candle2_from_currency AS from_currency,
	candle2_to_currency AS to_currency, 
	lead_index,
	--if candle1_percent_change correlates highly with candle2s new percent change then lets note the percent change of candle 1 in the prediction for candle 2
	AVG(CASE WHEN ABS(correlation) > %(correlation_threshold)s::DOUBLE PRECISION THEN candle1_percent_change * correlation ELSE 0 END) AS predicted_percent_change--,
	--ARRAY_AGG(candle1_from_currency || '/' || candle1_to_currency ORDER BY candle1_from_currency,candle1_to_currency) AS other_currency,
	--ARRAY_AGG(candle1_percent_change ORDER BY candle1_from_currency,candle1_to_currency) AS percent_changes,
	--ARRAY_AGG(correlation ORDER BY candle1_from_currency,candle1_to_currency) AS correlations_to_lead_candle2
	--candle2_lead_percent_change AS actual_percent_change
	FROM correlations 
	GROUP BY the_date, candle2_from_currency, candle2_to_currency, lead_index--, candle2_lead_percent_change
),
total_percent_changes AS ( --this IS ONLY predicting the NEXT candle AND NOT the FOLLOWING candles AFTER that...
	SELECT the_date, 
	from_currency,
	to_currency, 
	SUM(predicted_percent_change) AS predicted_percent_change
	FROM predicted_percent_changes 
	GROUP BY the_date, from_currency, to_currency
)
SELECT 
the_date, COUNT(1) AS n,
json_object_agg(
	from_currency || '/' || to_currency, JSON_BUILD_OBJECT(
		'delta',predicted_percent_change,
		'instrument',from_currency || '/' || to_currency,
		'the_date',the_date
	)
) AS correlation_hints
FROM total_percent_changes
GROUP BY the_date
ORDER BY the_date DESC
 








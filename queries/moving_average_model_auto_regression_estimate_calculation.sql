

--sample query that will grab candles AND condense them into actual candles of the correct size (quarts,halfs,hours,quads)
--quarts are 15m, halfs are 30m and quads are 4h candles 
DROP TABLE IF EXISTS tmp_currencies;
DROP TABLE IF EXISTS tmp_candles;
DROP TABLE IF EXISTS tmp_cross_correlations;


WITH ccs AS (
	SELECT UNNEST(ARRAY['AUD','CAD','CHF','EUR','GBP','NZD','JPY','USD']) AS currency
)
SELECT currency INTO TEMPORARY TABLE tmp_currencies FROM ccs;

--build candles of our chosen chart size 
WITH selected_candles AS (
	SELECT from_currency, to_currency,
	open_price,
	high_price,
	low_price,
	close_price, 
	the_date - INTERVAL '120 mins' AS the_date
	FROM exchange_value_tick evt 
	WHERE from_currency  = ANY(SELECT currency FROM tmp_currencies) AND to_currency = ANY(SELECT currency FROM tmp_currencies)
	AND the_date < (DATE '24 Feb 2022' + INTERVAL '12 hours')
	AND the_date >= (DATE '24 Feb 2022' - INTERVAL '100 days' + INTERVAL '12 hours') --600 = 400 + 200 (days_back + normalisation_window)
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
	(EXTRACT(MINUTE FROM the_date) + 60 * EXTRACT (HOUR FROM the_date))::INT / 240::INT AS candle_index
	FROM selected_candles
),
candles_start_end AS (
	SELECT from_currency,
	to_currency, 
	FIRST_VALUE(open_price) OVER (PARTITION BY from_currency, to_currency, date_day, candle_index ORDER BY the_date ASC) AS open_price,
	high_price AS high_price, 
	low_price AS low_price, 
	FIRST_VALUE(close_price) OVER (PARTITION BY from_currency, to_currency, date_day, candle_index ORDER BY the_date DESC) AS close_price, 
	the_date,
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
	c.the_date + INTERVAL '120 mins' AS the_date,
	t.time_index 
	FROM candles c 
	JOIN time_indexs t ON c.the_date = t.the_date
)
SELECT * INTO TEMPORARY TABLE tmp_candles FROM time_indexed_candles;

--firstly, get everything into percentages to ensure we are nicely normalised 
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
--calculate SMA moving average for X steps - EMA might not be suitable? With SMA it may be more stable for smaller datasets ---MAYBE??
--lets call it a solid average - the average we think it is across the whole series when really it is just a large moving average
solid_averages AS (
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
	AVG(percent_change) OVER w AS anchor_mean--we can get the percentage change back using percentage_change = mean + epsilon
	FROM percent_changes
	--using a large window size w, we can assume that anchor_mean(n-1) = anchor_mean(n) or that the mean is basically constant
	WINDOW w AS (PARTITION BY from_currency, to_currency ORDER BY the_date ASC ROWS BETWEEN 100 PRECEDING AND CURRENT ROW)
),
--generate our list of lag indexs - this is our n (eg calculating b1 to bn)
look_backs AS (
	SELECT generate_series(1,5,1) AS lag_index
),
epsilons AS ( --errors from the mean 
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
	anchor_mean, 
	anchor_mean - percent_change AS current_epsilon,
	lag_index,
	LAG(anchor_mean,lag_index) OVER w - LAG(percent_change,lag_index) OVER w AS epsilon --we want to calculate current epsilon based on these and from other currency pairs 
	FROM solid_averages, look_backs 	--this doesnt work as expected... 
	WINDOW w AS (PARTITION BY from_currency, to_currency, lag_index ORDER BY the_date ASC)
),
---epsilon_t0 = b1*epsilon_t1 + b2*epsilon_t2....   bn*epsilon_tn   --for SINGLE VARIATE case. might need more bs for multiple currency exchanges!
--example thing? 
gather_for_calc AS (
	SELECT this_candle.the_date,
	this_candle.from_currency AS this_candle_from_currency, 
	this_candle.to_currency AS this_candle_to_currency, 
	other_candles.from_currency AS other_candle_from_currency,
	other_candles.to_currency AS other_candle_to_currency,
	this_candle.current_epsilon,
	other_candles.current_epsilon AS new_current_epsilon,
	this_candle.anchor_mean, --is the epsilon of other currencies useful? IF NOT THEN JOIN ON 
	other_candles.epsilon AS prev_epsilon,
	other_candles.lag_index
	FROM epsilons this_candle 
	JOIN epsilons other_candles ON this_candle.the_date = other_candles.the_date --we want to do this calc for each date 
	--AND this_candle.from_currency = other_candles.from_currency AND this_candle.to_currency = other_candles.to_currency --comment out if we wanna do mix of currencies per current_epsilon 
	WHERE this_candle.lag_index = 1 --dont join on all the different lag indexs for this candle
),
--from here we use regression again to calculate the slope as b.
correlations AS ( 
	SELECT the_date,
	this_candle_from_currency, this_candle_to_currency, other_candle_from_currency, other_candle_to_currency,
	new_current_epsilon,
	CORR(current_epsilon,prev_epsilon) OVER w AS correlation, --correlates with the next percent CHANGE
	REGR_SLOPE(current_epsilon, prev_epsilon) OVER w AS slope,
	REGR_INTERCEPT(current_epsilon, prev_epsilon) OVER w AS intercept, --this actually causes problems. but we are working with percent change so should be 0 
	prev_epsilon,
	lag_index 
	FROM gather_for_calc
	WINDOW w AS (
		PARTITION BY this_candle_from_currency, this_candle_to_currency, other_candle_from_currency, other_candle_to_currency, lag_index
		ORDER BY the_date ASC ROWS BETWEEN 14 PRECEDING AND CURRENT ROW --correlate last 8 entries - works well with low correlations on 12 Jan 2022 AT 12pm.. so does high correl! 
	)
)
SELECT * INTO tmp_cross_correlations FROM correlations;


WITH other_candle_lead_lag AS ( --this IS confusing, but it needs TO have the current SET OF candles TO predict the NEXT one NOT the previous ones 
	SELECT *,
	CASE WHEN lag_index = 1 THEN new_current_epsilon  ELSE LAG(prev_epsilon,1) OVER w END AS next_prev_epsilon
	FROM tmp_cross_correlations
	WINDOW w AS (
		PARTITION BY this_candle_from_currency, this_candle_to_currency, other_candle_from_currency, other_candle_to_currency, lag_index
		ORDER BY the_date ASC
	)
),
total_errors AS (
	SELECT 
	the_date,
	this_candle_from_currency AS from_currency,
	this_candle_to_currency AS to_currency, 
	lag_index, --intercept causes issues 
	SUM(CASE WHEN ABS(correlation) > 0.3 THEN (slope*next_prev_epsilon) ELSE 0 END) AS total_epsilons,
	SUM(CASE WHEN ABS(correlation) > 0.3 THEN 1 ELSE 0 END) AS n 
	FROM other_candle_lead_lag 
	GROUP BY the_date, this_candle_from_currency, this_candle_to_currency, lag_index--, candle2_lead_percent_change
),
average_errors AS (
	SELECT the_date, 
	from_currency,
	to_currency, 
	lag_index, 
	CASE WHEN n = 0 THEN 0 ELSE total_epsilons / n END AS average_new_epsilon
	FROM total_errors
),
total_errors_across_lags AS (
	SELECT the_date, 
	from_currency,
	to_currency, 
	SUM(average_new_epsilon) AS predicted_epsilon
	FROM average_errors 
	GROUP BY the_date, from_currency, to_currency
)
SELECT 
the_date,
from_currency,
to_currency, 
predicted_epsilon,
'(''' || from_currency || '/' || to_currency || ''',''' || CASE WHEN predicted_epsilon > 0 THEN 'BUY' ELSE 'SELL' END || ''', NULL),' AS the_tuple
FROM total_errors_across_lags
WHERE the_date = '2022-01-24 08:00:00.000'
ORDER BY ABS(predicted_epsilon) DESC







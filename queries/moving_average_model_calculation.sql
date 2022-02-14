

--sample query that will grab candles AND condense them into actual candles of the correct size (quarts,halfs,hours,quads)
--quarts are 15m, halfs are 30m and quads are 4h candles 
DROP TABLE IF EXISTS tmp_currencies;
DROP TABLE IF EXISTS tmp_candles;

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
	--the_date,
	(EXTRACT(MINUTE FROM the_date) + 60 * EXTRACT (HOUR FROM the_date))::INT / 240::INT AS candle_index
	FROM exchange_value_tick evt 
	WHERE from_currency  = ANY(SELECT currency FROM tmp_currencies) AND to_currency = ANY(SELECT currency FROM tmp_currencies)
	AND the_date < (DATE '19 Jan 2022' + INTERVAL '2 hours')
	AND the_date >= (DATE '19 Jan 2022' - INTERVAL '200 days' + INTERVAL '2 hours') --600 = 400 + 200 (days_back + normalisation_window)
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
	c.the_date,
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
gather_for_b_calc AS (
	SELECT this_candle.the_date,
	this_candle.from_currency AS this_candle_from_currency, 
	this_candle.to_currency AS this_candle_to_currency, 
	other_candles.from_currency AS other_candle_from_currency,
	other_candles.to_currency AS other_candle_to_currency,
	this_candle.current_epsilon,
	this_candle.anchor_mean, --is the epsilon of other currencies useful? IF NOT THEN JOIN ON 
	other_candles.epsilon AS prev_epsilon,
	other_candles.lag_index
	FROM epsilons this_candle 
	JOIN epsilons other_candles ON this_candle.the_date = other_candles.the_date --we want to do this calc for each date 
	--AND this_candle.from_currency = other_candles.from_currency AND this_candle.to_currency = other_candles.to_currency --comment out if we wanna do mix of currencies per current_epsilon 
	WHERE this_candle.lag_index = 1 --dont join on all the different lag indexs for this candle
),
--from here we need to work out how to calculate the bs... correlation again might help with least squares? regr_slope uses a least squares approach 
collect_x_i_together AS (
	SELECT 
	the_date,
	this_candle_from_currency AS from_currency, 
	this_candle_to_currency AS to_currency,
	current_epsilon,--target
	anchor_mean, --needs to persist for the estimations later
	ARRAY_AGG(prev_epsilon) AS x_i,--variables, 
	ARRAY_AGG(lag_index) AS lags,
	COUNT(1) AS x_size
	FROM gather_for_b_calc 
	GROUP BY the_date, this_candle_from_currency, this_candle_to_currency, current_epsilon, anchor_mean
),
collect_rows_together AS (
	SELECT the_date, --each row of this is going to be a large matrix calculation... 
	from_currency, 
	to_currency, 
	ARRAY_AGG(current_epsilon) OVER w AS Y, 
	ARRAY_AGG(x_i) OVER w AS X
	FROM collect_x_i_together
	WINDOW w AS (PARTITION BY from_currency, to_currency ORDER BY the_date DESC ROWS BETWEEN 150 PRECEDING AND CURRENT ROW)
)
--to get the Bs we need to do (X^T . X )^-1 . X^T . Y
SELECT * FROM collect_rows_together

--SELECT count(1) FROM collect_rows_together-- WHERE from_currency = 'EUR' AND to_currency = 'USD' ORDER BY the_date DESC 
--this is probably infeasible for the time frame we have - many matrix calculations are required! 28 * candles * 5 ops. And we may have 1000s of candles!
--this calculation includes inverting matrices of order over 100 each! so this is definitely not going to work :(















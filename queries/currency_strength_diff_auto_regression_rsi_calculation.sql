--query for finding all correlations between  each currency pair that we are interested in. 

DROP TABLE IF EXISTS tmp_currencies; 
DROP TABLE IF EXISTS tmp_candles; --everything
DROP TABLE IF EXISTS tmp_all_rates_of_change; 
DROP TABLE IF EXISTS tmp_all_rsi; 
DROP TABLE IF EXISTS tmp_friends;
DROP TABLE IF EXISTS tmp_enemies;
DROP TABLE IF EXISTS tmp_all_strengths;
DROP TABLE IF EXISTS tmp_all_movements;
DROP TABLE IF EXISTS tmp_all_ranks;


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
	AND the_date < (DATE '04 Feb 2022' + INTERVAL '16 hours') --what about IF we want TO START ON 45 mins?
	AND the_date >= (DATE '04 Feb 2022' - INTERVAL '180 days' + INTERVAL '16 hours') --600 = 400 + 200 (days_back + normalisation_window)
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
	MIN(the_date) AS the_date--nicely cleans up slightly off-15 candles 
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


WITH rates_of_change AS (
	SELECT from_currency, to_currency,
	(close_price - LAG(close_price,1) OVER w)  AS rate_of_change,
	close_price,
	the_date,
	time_index
	FROM tmp_candles
	WINDOW w AS (PARTITION BY from_currency, to_currency ORDER BY the_date ASC)	
)
SELECT from_currency, to_currency, close_price, rate_of_change, the_date, time_index INTO TEMPORARY TABLE tmp_all_rates_of_change FROM rates_of_change;

WITH up_down_moves AS (
	SELECT from_currency, to_currency,
	SUM(GREATEST(rate_of_change,0)) OVER w AS up_moves,
	SUM(ABS(LEAST(rate_of_change,0))) OVER w AS down_moves,
	GREATEST(rate_of_change,0) AS up_move,
	ABS(LEAST(rate_of_change,0)) AS down_move,
	the_date,
	time_index
	FROM tmp_all_rates_of_change taroc 
	WINDOW w AS (PARTITION BY from_currency, to_currency ORDER BY the_date ASC ROWS BETWEEN (14::INT-1) PRECEDING AND CURRENT ROW)	
),
avg_moves AS (
	SELECT from_currency, to_currency,
	up_moves,
	down_moves,
	EMA(
		CASE WHEN time_index <= 14::INT THEN up_moves / time_index::DOUBLE PRECISION ELSE up_move END, 
		CASE WHEN time_index <= 14::INT THEN 1.0 ELSE 1.0 / 14::DOUBLE PRECISION END 
	) OVER w AS avg_moves_up,
	EMA(
		CASE WHEN time_index <= 14::INT THEN down_moves / time_index::DOUBLE PRECISION ELSE down_move END, 
		CASE WHEN time_index <= 14::INT THEN 1.0 ELSE 1.0 / 14::DOUBLE PRECISION END 
	) OVER w AS avg_moves_down,
	the_date,
	time_index
	FROM up_down_moves 
	WINDOW w AS (PARTITION BY from_currency, to_currency ORDER BY the_date)	
),
rs_calc AS ( 
	SELECT from_currency, to_currency, 
	CASE WHEN avg_moves_down = 0 THEN 1.0 ELSE 1.0 - (1.0 / (1.0 + (avg_moves_up / avg_moves_down)) ) END  AS rsi,
	--CASE WHEN down_moves = 0 THEN 1.0 ELSE 1.0 - (1.0 / (1.0 + (up_moves / down_moves)) ) END  AS rsi2, --WRONG
	the_date,
	time_index
	FROM avg_moves
),
rsi_rescaled AS (
	SELECT from_currency, to_currency, 
	(2.0*rsi) - 1.0 AS rsi, --put rsi FROM [0,1] TO [-1,1]
	the_date 
	FROM rs_calc
)
SELECT * INTO TEMPORARY TABLE tmp_all_rsi FROM rsi_rescaled;


SELECT cs.currency, rsi.rsi, rsi.the_date 
INTO TEMPORARY TABLE tmp_friends
FROM tmp_all_rsi rsi
JOIN tmp_currencies cs ON rsi.from_currency = cs.currency;

SELECT cs.currency, rsi.rsi, rsi.the_date 
INTO TEMPORARY TABLE tmp_enemies
FROM tmp_all_rsi rsi
JOIN tmp_currencies cs ON rsi.to_currency = cs.currency;

CREATE INDEX tmp_friends_currency_idx ON tmp_friends USING btree(currency);
CREATE INDEX tmp_friends_the_date_idx ON tmp_friends USING btree(the_date);

CREATE INDEX tmp_enemies_currency_idx ON tmp_enemies USING btree(currency);
CREATE INDEX tmp_enemies_the_date_idx ON tmp_enemies USING btree(the_date);

WITH all_dates_pairs AS (
	SELECT DISTINCT the_date, currency FROM tmp_all_rates_of_change, tmp_currencies ORDER BY the_date
),
all_rsis AS (
	SELECT c.currency, 
	c.the_date AS the_date,
	f.rsi
	FROM all_dates_pairs c
	JOIN tmp_friends f ON c.currency = f.currency AND c.the_date = f.the_date
	UNION 
	SELECT c.currency,
	c.the_date AS the_date,
	-e.rsi
	FROM all_dates_pairs c
	JOIN tmp_enemies e ON c.currency = e.currency AND c.the_date = e.the_date
),
rsi_strengths AS (
	SELECT currency, 
	the_date,
	SUM(rsi) AS strength 
	FROM all_rsis
	GROUP BY currency, the_date
)
SELECT * INTO TEMPORARY TABLE tmp_all_strengths FROM rsi_strengths;

--SELECT min(strength), max(strength) FROM tmp_all_strengths
--use the correlations to find hints of strength movement? this can then be fed into the NN 
--we may actually just want to correlate on the strengths directly - not on their differences
WITH prev_strengths AS (
	SELECT 
	the_date,
	currency,
	strength,
	LAG(strength,1) OVER w AS previous_strength 
	FROM tmp_all_strengths
	WINDOW w AS (PARTITION BY currency ORDER BY the_date ASC)
),
strength_changes AS (
	SELECT the_date, 
	currency,
	strength,
	previous_strength,
	strength - previous_strength AS strength_difference
	FROM prev_strengths 
),
look_backs AS (
	SELECT generate_series(1,12,1) AS lag_index
),
lagged_strengths AS (
	SELECT the_date,
	currency,
	strength,
	previous_strength,
	strength_difference,
	lag_index,
	LAG(strength_difference,lag_index) OVER (PARTITION BY currency, lag_index ORDER BY the_date) AS lag_strength_difference
	FROM strength_changes, look_backs
),
all_changes AS (
	SELECT strength1.the_date,
	strength1.strength AS strength1strength,
	strength1.currency AS strength1_currency,
	strength2.currency AS strength2_currency,
	strength1.strength_difference AS strength1_strength_difference, 
	strength2.strength_difference AS strength2_strength_difference,--need for calculating the strength2_lead_lag
	strength2.lag_strength_difference AS strength2_lag_strength_difference,
	strength2.lag_index
	FROM lagged_strengths strength1
	JOIN lagged_strengths strength2 ON strength1.the_date = strength2.the_date
	WHERE strength1.lag_index = 1 --dont select all the other lags of candle 1 as they are not needed 
	ORDER BY strength1.the_date ASC
),
correlations AS (
	SELECT the_date,
	strength1strength,
	strength1_currency, strength2_currency,
	strength1_strength_difference,
	strength2_strength_difference, 
	strength2_lag_strength_difference,
	CORR(strength1_strength_difference,strength2_lag_strength_difference) OVER w AS correlation, --correlates with the next difference
	REGR_SLOPE(strength1_strength_difference, strength2_lag_strength_difference) OVER w AS slope,
	REGR_INTERCEPT(strength1_strength_difference, strength2_lag_strength_difference) OVER w AS intercept, 
	lag_index 
	FROM all_changes
	WINDOW w AS (
		PARTITION BY strength1_currency, strength2_currency, lag_index
		ORDER BY the_date ASC ROWS BETWEEN 49 PRECEDING AND CURRENT ROW --correlate last 8 entries - works well with low correlations on 12 Jan 2022 AT 12pm.. so does high correl! 
	)
--	GROUP BY candle1_from_currency, candle1_to_currency, candle2_from_currency, candle2_to_currency
),
strength2_lead_lag AS ( --this IS confusing, but it needs TO have the current SET OF candles TO predict the NEXT one NOT the previous ones 
	SELECT *,
	CASE WHEN lag_index = 1 THEN strength2_strength_difference ELSE LAG(strength2_lag_strength_difference,1) OVER w END AS strength2_leadlag
	FROM correlations
	WINDOW w AS (
		PARTITION BY strength1_currency, strength2_currency, lag_index
		ORDER BY the_date ASC
	)
)
--SELECT the_date, candle2_percent_change, candle2_lag_percent_change, candle2_leadlag, lag_index FROM candle2_lead_lag WHERE candle1_from_currency = 'EUR' AND candle1_to_currency = 'USD' AND candle2_from_currency = 'USD' AND candle2_to_currency ='JPY'
--ORDER BY the_date ASC, lag_index DESC 
,
collected_strength_differences AS (
	SELECT 
	the_date,
	strength1_currency AS currency,
	strength1strength AS strength,
	--lag_index, --intercept causes issues
	SUM(CASE WHEN ABS(correlation) > 0.25 THEN (slope*strength2_leadlag+intercept) ELSE 0 END) AS sum_next_strength_differences,
	SUM(CASE WHEN ABS(correlation) > 0.25 THEN (slope*strength2_leadlag+intercept)*(slope*strength2_leadlag+intercept) ELSE 0 END) AS sum_squared_next_strength_differences,
	SUM(CASE WHEN ABS(correlation) > 0.25 THEN 1 ELSE 0 END) AS n_next_strength_differences
	FROM strength2_lead_lag 
	GROUP BY the_date, currency, strength1strength
),
average_strength_differences AS (
	SELECT the_date, 
	currency,
	strength,
	CASE WHEN n_next_strength_differences = 0 THEN 0 ELSE sum_next_strength_differences / n_next_strength_differences END AS average_next_strength_difference,
	CASE WHEN n_next_strength_differences = 0 THEN 0 ELSE 
		(sum_squared_next_strength_differences / n_next_strength_differences) - ((sum_next_strength_differences / n_next_strength_differences)*(sum_next_strength_differences / n_next_strength_differences))
	END AS next_strength_difference_variance,
	n_next_strength_differences 
	FROM collected_strength_differences 
),
next_strengths AS (
	SELECT 
	ps.the_date,
	ps.currency, 
	COALESCE(asd.next_strength_difference_variance,0) AS next_strength_difference_variance,
	COALESCE(asd.average_next_strength_difference,0) AS average_next_strength_difference,
	COALESCE(asd.n_next_strength_differences,0) AS n_next_strength_differences,
	ps.strength,
	ps.strength + COALESCE(asd.next_strength_difference_variance,0) AS next_strength
	FROM prev_strengths ps
	LEFT JOIN average_strength_differences asd ON ps.the_date = asd.the_date AND ps.currency = asd.currency
)
SELECT * INTO TEMPORARY TABLE tmp_all_movements FROM next_strengths;

WITH ranked_movements AS (
	SELECT m.currency, 
	m.next_strength AS movement, 
	m.the_date,
	RANK() OVER (PARTITION BY m.the_date ORDER BY m.next_strength ASC) AS ranked
	FROM tmp_all_movements m
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
SELECT the_date, currency, movement, average_movement, ranked, average_rank, ranked_average INTO TEMPORARY TABLE tmp_all_ranks FROM ranked_averages;

SELECT the_date, COUNT(1) AS n,
json_object_agg(currency, 
	json_build_object(
		'movement',movement,
		'average_movement',average_movement,
		'rank',ranked,
		'average_rank',average_rank,
		'ranked_average',ranked_average
	)
)
FROM tmp_all_ranks
--AND currency = 'EUR'
GROUP BY the_date
HAVING SUM(1) = (SELECT ARRAY_LENGTH(ARRAY[1,2,3,4,5,6,7,8],1))
ORDER BY the_date 



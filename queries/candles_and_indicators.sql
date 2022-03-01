--query for selecting candles and all the associated indicator values 
DROP TABLE IF EXISTS tmp_currencies; 
DROP TABLE IF EXISTS tmp_candles; --everything
DROP TABLE IF EXISTS tmp_average_true_ranges;--atr
DROP TABLE IF EXISTS tmp_rsis; 
DROP TABLE IF EXISTS tmp_stochastic_oscillators;
DROP TABLE IF EXISTS tmp_macds;
DROP TABLE IF EXISTS tmp_bollinger_bands;
DROP TABLE IF EXISTS tmp_candles_with_indicators; 


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
	SELECT UNNEST(%(currencies)s) AS currency
)
SELECT currency INTO TEMPORARY TABLE tmp_currencies FROM ccs;

--build candles of our chosen chart size 
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

--CREATE INDEX IF NOT EXISTS tmp_candles_from_currency_idx ON tmp_candles USING btree(from_currency);
--CREATE INDEX IF NOT EXISTS tmp_candles_to_currency_idx ON tmp_candles USING btree(to_currency);
--CREATE INDEX IF NOT EXISTS tmp_candles_from_to_currency_idx ON tmp_candles USING btree(from_currency,to_currency);
--CREATE INDEX IF NOT EXISTS tmp_candles_the_date_idx ON tmp_candles USING btree(the_date);

--===Average True Range===
--compute average true range. scale it to between 0 and 1 using a scaling window 
WITH true_ranges AS (
	SELECT from_currency, to_currency,
	GREATEST(high_price - low_price, ABS(high_price - LAG(close_price) OVER w),ABS(low_price - LAG(close_price) OVER w)) AS true_range,
	the_date
	FROM tmp_candles tc
	WINDOW w AS (PARTITION BY from_currency,to_currency ORDER BY the_date ASC)
), 
max_true_ranges AS (
	SELECT from_currency, to_currency, 
	true_range,
	MAX(true_range) OVER w AS max_true_range,
	the_date
	FROM true_ranges 
	WINDOW w AS (PARTITION BY from_currency, to_currency ORDER BY the_date ASC ROWS BETWEEN (%(normalisation_window)s::INT-1) PRECEDING AND CURRENT ROW)
),
scaled_true_ranges AS (
	SELECT mtr.from_currency, mtr.to_currency, 
	mtr.true_range / mtr.max_true_range AS scaled_true_range,
	mtr.the_date 
	FROM max_true_ranges mtr 
),
average_true_ranges AS (
	SELECT from_currency, to_currency,
	EMA(scaled_true_range,1.0 / %(average_true_range_period)s::DOUBLE PRECISION) OVER w AS average_true_range,
	the_date
	FROM scaled_true_ranges
	WINDOW w AS (PARTITION BY from_currency, to_currency ORDER BY the_date ASC)
)
SELECT * INTO TEMPORARY TABLE tmp_average_true_ranges
FROM average_true_ranges;

--CREATE INDEX IF NOT EXISTS tmp_average_true_ranges_from_currency_idx ON tmp_average_true_ranges USING btree(from_currency);
--CREATE INDEX IF NOT EXISTS tmp_average_true_ranges_to_currency_idx ON tmp_average_true_ranges USING btree(to_currency);
--CREATE INDEX IF NOT EXISTS tmp_average_true_ranges_from_to_currency_idx ON tmp_average_true_ranges USING btree(from_currency,to_currency);
--CREATE INDEX IF NOT EXISTS tmp_average_true_ranges_the_date_idx ON tmp_average_true_ranges USING btree(the_date);


--===RSI===
--compute rsi for the set of candles. results will be between 0 and 1
WITH rates_of_change AS (
	SELECT from_currency, to_currency,
	(close_price - LAG(close_price,1) OVER w)  AS rate_of_change,
	close_price,
	the_date,
	time_index
	FROM tmp_candles  
	WINDOW w AS (PARTITION BY from_currency, to_currency ORDER BY the_date ASC)	
),
up_down_moves AS (
	SELECT from_currency, to_currency,
	SUM(GREATEST(rate_of_change,0)) OVER w AS up_moves,
	SUM(ABS(LEAST(rate_of_change,0))) OVER w AS down_moves,
	GREATEST(rate_of_change,0) AS up_move,
	ABS(LEAST(rate_of_change,0)) AS down_move,
	the_date,
	time_index
	FROM rates_of_change roc 
	WINDOW w AS (PARTITION BY from_currency, to_currency ORDER BY the_date ASC ROWS BETWEEN (%(relative_strength_index_period)s::INT-1) PRECEDING AND CURRENT ROW)	
),
avg_moves AS (
	SELECT from_currency, to_currency,
	up_moves,
	down_moves,
	EMA(
		CASE WHEN time_index <= %(relative_strength_index_period)s::INT THEN up_moves / time_index::DOUBLE PRECISION ELSE up_move END, 
		CASE WHEN time_index <= %(relative_strength_index_period)s::INT THEN 1.0 ELSE 1.0 / %(relative_strength_index_period)s::DOUBLE PRECISION END 
	) OVER w AS avg_moves_up,
	EMA(
		CASE WHEN time_index <= %(relative_strength_index_period)s::INT THEN down_moves / time_index::DOUBLE PRECISION ELSE down_move END, 
		CASE WHEN time_index <= %(relative_strength_index_period)s::INT THEN 1.0 ELSE 1.0 / %(relative_strength_index_period)s::DOUBLE PRECISION END 
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
)
SELECT * INTO TEMPORARY TABLE tmp_rsis FROM rs_calc;

--CREATE INDEX IF NOT EXISTS tmp_rsis_from_currency_idx ON tmp_rsis USING btree(from_currency);
--CREATE INDEX IF NOT EXISTS tmp_rsis_to_currency_idx ON tmp_rsis USING btree(to_currency);
--CREATE INDEX IF NOT EXISTS tmp_rsis_from_to_currency_idx ON tmp_rsis USING btree(from_currency,to_currency);
--CREATE INDEX IF NOT EXISTS tmp_rsis_the_date_idx ON tmp_rsis USING btree(the_date);

--===Stochastic Oscillator===
--compute stochastic and slow stochastic for the set of candles. results between 0 and 1
WITH periods AS (
	SELECT from_currency, to_currency,
	MAX(high_price) OVER w AS high_price,
	MIN(low_price) OVER w AS low_price,
	close_price,
	the_date
	FROM tmp_candles tc  
	WINDOW w AS (PARTITION BY from_currency,to_currency ORDER BY the_date ASC ROWS BETWEEN (%(stochastic_oscillator_period)s::INT-1) PRECEDING AND CURRENT ROW)
),
calc_k AS (
	SELECT from_currency, to_currency,
	(close_price - low_price) / (high_price - low_price) AS k,
	the_date
	FROM periods
),
calc_d AS (
	SELECT from_currency, to_currency,
	the_date,
	k AS stochastic_oscillator_k,
	AVG(k) OVER w AS stochastic_oscillator_d
	FROM calc_k
	WINDOW w AS (PARTITION BY from_currency, to_currency ORDER BY the_date ASC ROWS BETWEEN (%(stochastic_oscillator_fast_d)s::INT-1) PRECEDING AND CURRENT ROW)
),
calc_slow_d AS (
	SELECT from_currency, to_currency,
	the_date,
	stochastic_oscillator_k,
	stochastic_oscillator_d,
	AVG(stochastic_oscillator_d) OVER w AS stochastic_oscillator_slow_d
	FROM calc_d
	WINDOW w AS (PARTITION BY from_currency, to_currency ORDER BY the_date ASC ROWS BETWEEN (%(stochastic_oscillator_slow_d)s::INT-1) PRECEDING AND CURRENT ROW)
)
SELECT * INTO TEMPORARY TABLE tmp_stochastic_oscillators FROM calc_slow_d;

--CREATE INDEX IF NOT EXISTS tmp_stochastic_oscillators_from_currency_idx ON tmp_stochastic_oscillators USING btree(from_currency);
--CREATE INDEX IF NOT EXISTS tmp_stochastic_oscillators_to_currency_idx ON tmp_stochastic_oscillators USING btree(to_currency);
--CREATE INDEX IF NOT EXISTS tmp_stochastic_oscillators_from_to_currency_idx ON tmp_stochastic_oscillators USING btree(from_currency,to_currency);
--CREATE INDEX IF NOT EXISTS tmp_stochastic_oscillators_the_date_idx ON tmp_stochastic_oscillators USING btree(the_date);

--===MACD===
--compute the macd and signal line height for the set of candles. normalisation window used to get values between 0 and 1 
WITH moving_averages AS (
	SELECT from_currency, to_currency, 
	EMA(close_price, 1.0 / %(macd_slow_period)s::DOUBLE PRECISION) OVER w AS slow_price,
	EMA(close_price, 1.0 / %(macd_fast_period)s::DOUBLE PRECISION) OVER w AS fast_price,
	the_date 
	FROM tmp_candles 
	WINDOW w AS (PARTITION BY from_currency, to_currency ORDER BY the_date ASC)
),
macd_calculation AS (  ---normalise? 
	SELECT from_currency, to_currency, 
	fast_price - slow_price AS macd_line,
	EMA(fast_price - slow_price, 1.0 /  %(macd_signal_period)s::DOUBLE PRECISION) OVER w AS signal_line,
	the_date 
	FROM moving_averages
	WINDOW w AS (PARTITION BY from_currency, to_currency ORDER BY the_date ASC)
),
macd_bounds AS (
	SELECT from_currency, to_currency, 
	macd_line,
	signal_line,
	the_date,
	MAX(macd_line) OVER w AS max_macd_line,
	MIN(macd_line) OVER w AS min_macd_line
	FROM macd_calculation
	WINDOW w AS (PARTITION BY from_currency, to_currency ORDER BY the_date ASC ROWS BETWEEN (%(normalisation_window)s::INT-1) PRECEDING AND CURRENT ROW)
),
macd_scaled AS (
	SELECT from_currency,to_currency, 
	macd_line,
	signal_line,
	the_date,
	CASE WHEN max_macd_line = min_macd_line THEN 0.5 ELSE (macd_line - min_macd_line) / (max_macd_line - min_macd_line) END AS scaled_macd_line,
	CASE WHEN max_macd_line = min_macd_line THEN 0.5 ELSE (signal_line - min_macd_line) / (max_macd_line - min_macd_line) END  AS scaled_signal_line
	FROM macd_bounds
)
SELECT * INTO TEMPORARY TABLE tmp_macds FROM macd_scaled;


--===Bollinger Bands===
WITH middle_band_dev AS (
	SELECT from_currency, to_currency, 
	close_price,
	AVG(close_price) OVER w AS bollinger_band_middle,
	STDDEV(close_price) OVER w AS bollinger_band_dev,
	the_date 
	FROM tmp_candles 
	WINDOW w AS (PARTITION BY from_currency, to_currency ORDER BY the_date ASC ROWS BETWEEN (%(bollinger_band_period)s::INT - 1) PRECEDING AND CURRENT ROW)
),
top_bottom_bands AS (
	SELECT from_currency, to_currency, 
	close_price,
	bollinger_band_middle,
	bollinger_band_dev,
	bollinger_band_middle + %(bollinger_band_k)s::DOUBLE PRECISION * bollinger_band_dev AS bollinger_band_upper,
	bollinger_band_middle - %(bollinger_band_k)s::DOUBLE PRECISION * bollinger_band_dev AS bollinger_band_lower,
	the_date
	FROM middle_band_dev
),
percent_bandwidth AS (
	SELECT from_currency, to_currency, 
	close_price,
	bollinger_band_middle,
	bollinger_band_dev,
	bollinger_band_upper,
	bollinger_band_lower,
	(close_price - bollinger_band_lower) / (bollinger_band_upper - bollinger_band_lower) AS bollinger_band_percent_b,
	(bollinger_band_upper - bollinger_band_lower) / bollinger_band_middle AS bollinger_band_bandwidth,
	the_date
	FROM top_bottom_bands 
)
SELECT * INTO TEMPORARY TABLE tmp_bollinger_bands FROM percent_bandwidth;

--add any more indicators here!

--CREATE INDEX IF NOT EXISTS tmp_macds_from_currency_idx ON tmp_macds USING btree(from_currency);
--CREATE INDEX IF NOT EXISTS tmp_macds_to_currency_idx ON tmp_macds USING btree(to_currency);
--CREATE INDEX IF NOT EXISTS tmp_macds_from_currency_to_currency_idx ON tmp_macds USING btree(from_currency,to_currency);
--CREATE INDEX IF NOT EXISTS tmp_macds_the_date_idx ON tmp_macds USING btree(the_date);

--lets use a normalisation window to normalise the prices and get everything between 0 and 1
--===Normalised & moving average prices=== 
WITH price_bounds AS (
	SELECT from_currency, to_currency,
	the_date, 
	open_price,
	high_price,
	low_price,
	close_price,
	MAX(high_price) OVER w AS max_price,
	MIN(low_price) OVER w AS min_price
	FROM tmp_candles
	WINDOW w AS (PARTITION BY from_currency, to_currency ORDER BY the_date ASC ROWS BETWEEN (%(normalisation_window)s-1) PRECEDING AND CURRENT ROW)
),
normed_prices AS (
	SELECT *,
	(open_price - min_price) / (max_price - min_price) AS normed_open_price,
	(high_price - min_price) / (max_price - min_price) AS normed_high_price,
	(low_price - min_price) / (max_price - min_price) AS normed_low_price,
	(close_price - min_price) / (max_price - min_price) AS normed_close_price 
	FROM price_bounds
),
moving_averages AS (
	SELECT np.*,
	--usual close prices 
	AVG(np.close_price) OVER (PARTITION BY np.from_currency, np.to_currency ORDER BY np.the_date ASC ROWS BETWEEN (200-1) PRECEDING AND CURRENT ROW) AS sma200,
	EMA(np.close_price,1.0/200.0) OVER (PARTITION BY np.from_currency, np.to_currency ORDER BY np.the_date ASC) AS ema200,
	AVG(np.close_price) OVER (PARTITION BY np.from_currency, np.to_currency ORDER BY np.the_date ASC ROWS BETWEEN (100-1) PRECEDING AND CURRENT ROW) AS sma100,
	EMA(np.close_price,1.0/100.0) OVER (PARTITION BY np.from_currency, np.to_currency ORDER BY np.the_date ASC) AS ema100,
	AVG(np.close_price) OVER (PARTITION BY np.from_currency, np.to_currency ORDER BY np.the_date ASC ROWS BETWEEN (50-1) PRECEDING AND CURRENT ROW) AS sma50,
	EMA(np.close_price,1.0/50.0) OVER (PARTITION BY np.from_currency, np.to_currency ORDER BY np.the_date ASC) AS ema50,
	AVG(np.close_price) OVER (PARTITION BY np.from_currency, np.to_currency ORDER BY np.the_date ASC ROWS BETWEEN (%(custom_sma_period)s::INT-1) PRECEDING AND CURRENT ROW) AS sma_custom,
	EMA(np.close_price,1.0/%(custom_ema_period)s::DOUBLE PRECISION) OVER (PARTITION BY np.from_currency, np.to_currency ORDER BY np.the_date ASC) AS ema_custom,
	--normed close prices 
	AVG(np.normed_close_price) OVER (PARTITION BY np.from_currency, np.to_currency ORDER BY np.the_date ASC ROWS BETWEEN (200-1) PRECEDING AND CURRENT ROW) AS normed_sma200,
	EMA(np.normed_close_price,1.0/200.0) OVER (PARTITION BY np.from_currency, np.to_currency ORDER BY np.the_date ASC) AS normed_ema200,
	AVG(np.normed_close_price) OVER (PARTITION BY np.from_currency, np.to_currency ORDER BY np.the_date ASC ROWS BETWEEN (100-1) PRECEDING AND CURRENT ROW) AS normed_sma100,
	EMA(np.normed_close_price,1.0/100.0) OVER (PARTITION BY np.from_currency, np.to_currency ORDER BY np.the_date ASC) AS normed_ema100,
	AVG(np.normed_close_price) OVER (PARTITION BY np.from_currency, np.to_currency ORDER BY np.the_date ASC ROWS BETWEEN (50-1) PRECEDING AND CURRENT ROW) AS normed_sma50,
	EMA(np.normed_close_price,1.0/50.0) OVER (PARTITION BY np.from_currency, np.to_currency ORDER BY np.the_date ASC) AS normed_ema50,
	AVG(np.normed_close_price) OVER (PARTITION BY np.from_currency, np.to_currency ORDER BY np.the_date ASC ROWS BETWEEN (%(custom_sma_period)s::INT-1) PRECEDING AND CURRENT ROW) AS normed_sma_custom,
	EMA(np.normed_close_price,1.0/%(custom_ema_period)s::DOUBLE PRECISION) OVER (PARTITION BY np.from_currency, np.to_currency ORDER BY np.the_date ASC) AS normed_ema_custom
	--might also want to do highs/lows etc for other indicators 
	FROM normed_prices np
)
SELECT * INTO TEMPORARY TABLE tmp_moving_averages FROM moving_averages;


CREATE INDEX IF NOT EXISTS tmp_candles_all_idx ON tmp_candles USING btree(from_currency,to_currency,the_date);
CREATE INDEX IF NOT EXISTS tmp_average_true_ranges_all_idx ON tmp_average_true_ranges USING btree(from_currency,to_currency,the_date);
CREATE INDEX IF NOT EXISTS tmp_rsis_all_idx  ON tmp_rsis USING btree(from_currency,to_currency,the_date);
CREATE INDEX IF NOT EXISTS tmp_stochastic_oscillators_all_idx ON tmp_stochastic_oscillators USING btree(from_currency,to_currency,the_date);
CREATE INDEX IF NOT EXISTS tmp_macds_all_idx ON tmp_macds USING btree(from_currency,to_currency,the_date);
CREATE INDEX IF NOT EXISTS tmp_bollinger_bands_idx ON tmp_bollinger_bands USING btree(from_currency,to_currency,the_date);
CREATE INDEX IF NOT EXISTS tmp_moving_averages_all_idx ON tmp_moving_averages USING btree(from_currency,to_currency,the_date);


WITH candles_with_indicators AS (
	SELECT ma.*,
	atr.average_true_range,
	rsi.rsi,
	so.stochastic_oscillator_k,
	so.stochastic_oscillator_d,
	so.stochastic_oscillator_slow_d,
	macd.macd_line,
	macd.signal_line,
	macd.scaled_macd_line,
	macd.scaled_signal_line,
	bb.bollinger_band_middle,
	bb.bollinger_band_upper,
	bb.bollinger_band_lower,
	bb.bollinger_band_bandwidth,
	bb.bollinger_band_percent_b
	FROM tmp_moving_averages ma
	JOIN tmp_average_true_ranges atr ON atr.from_currency = ma.from_currency AND atr.to_currency = ma.to_currency AND atr.the_date = ma.the_date
	JOIN tmp_rsis rsi ON rsi.from_currency = ma.from_currency AND rsi.to_currency = ma.to_currency AND rsi.the_date = ma.the_date
	JOIN tmp_stochastic_oscillators so ON so.from_currency = ma.from_currency AND so.to_currency = ma.to_currency AND so.the_date = ma.the_date
	JOIN tmp_macds macd ON macd.from_currency = ma.from_currency AND macd.to_currency = ma.to_currency AND macd.the_date = ma.the_date
	JOIN tmp_bollinger_bands bb ON bb.from_currency = ma.from_currency AND bb.to_currency = ma.to_currency AND bb.the_date = ma.the_date
)
SELECT * INTO TEMPORARY TABLE tmp_candles_with_indicators FROM candles_with_indicators;

WITH all_results AS (
	SELECT the_date, count(1) AS n,
	json_object_agg(
		from_currency || '/' || to_currency, 
		json_build_object(
			'instrument',from_currency || '/' || to_currency,
			'the_date',the_date,
			'open_price',open_price,
			'high_price',high_price,
			'low_price',low_price,
			'close_price',close_price,
			'normed_open_price', normed_open_price,
			'normed_high_price', normed_high_price,
			'normed_low_price',  normed_low_price,
			'normed_close_price',normed_close_price,
			'max_price',max_price,
			'min_price',min_price,
			--moving averages (close)
			'sma_custom', sma_custom,
			'sma50', sma50,
			'sma100',sma100,
			'sma200',sma200,
			'ema_custom', ema_custom,
			'ema50', ema50,
			'ema100',ema100,
			'ema200',ema200,
			--normed moving averages 
			'normed_sma_custom', normed_sma_custom,
			'normed_sma50', normed_sma50,
			'normed_sma100',normed_sma100,
			'normed_sma200',normed_sma200,
			'normed_ema_custom', normed_ema_custom,
			'normed_ema50', normed_ema50,
			'normed_ema100',normed_ema100,
			'normed_ema200',normed_ema200,
			--indicator values 
			'average_true_range',average_true_range,
			'relative_strength_index',rsi,
			'stochastic_oscillator_k',stochastic_oscillator_k,
			'stochastic_oscillator_d',stochastic_oscillator_d,
			'stochastic_oscillator_slow_d',stochastic_oscillator_slow_d,
			'macd_line',macd_line,
			'macd_signal',signal_line,
			'normed_macd_line',scaled_macd_line,
			'normed_macd_signal',scaled_signal_line,
			'bollinger_band_middle',bollinger_band_middle,
			'bollinger_band_upper',bollinger_band_upper,
			'bollinger_band_lower',bollinger_band_lower,
			'bollinger_band_bandwidth',bollinger_band_bandwidth,
			'bollinger_band_percent_b',bollinger_band_percent_b
		)
	) AS results
	FROM tmp_candles_with_indicators
	GROUP BY the_date
),
max_n AS (
	SELECT MAX(n) AS N FROM all_results
)
SELECT r.* FROM all_results r, max_n n
WHERE r.n = n.N
ORDER BY the_date DESC






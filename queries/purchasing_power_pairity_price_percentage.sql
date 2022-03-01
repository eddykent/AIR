
--sample query that will grab candles AND condense them into actual candles of the correct size (quarts,halfs,hours,quads)
--quarts are 15m, halfs are 30m and quads are 4h candles 
DROP TABLE IF EXISTS tmp_currencies;
DROP TABLE IF EXISTS tmp_candles;

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
	the_date - INTERVAL '0 mins' AS the_date
	FROM exchange_value_tick evt 
	WHERE from_currency  = ANY(SELECT currency FROM tmp_currencies) AND to_currency = ANY(SELECT currency FROM tmp_currencies)
	AND the_date < (DATE '1 Mar 2022' + INTERVAL '16 hours')
	AND the_date >= (DATE '1 Mar 2022' - INTERVAL '20 days' + INTERVAL '16 hours') --600 = 400 + 200 (days_back + normalisation_window)
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
	(EXTRACT(MINUTE FROM the_date) + 60 * EXTRACT (HOUR FROM the_date))::INT / 15::INT AS candle_index
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
	TO_TIMESTAMP (FLOOR(( EXTRACT ('EPOCH' FROM (the_date )) ) / (60*15::INT) ) * (60*15::INT)) AT TIME ZONE 'UTC' AS the_date --round down the offset candles 
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
	c.the_date + INTERVAL '0 mins' AS the_date,
	t.time_index 
	FROM candles c 
	JOIN time_indexs t ON c.the_date = t.the_date
)
SELECT * INTO TEMPORARY TABLE tmp_candles FROM time_indexed_candles;




WITH point_prices AS (
	SELECT from_currency,
	to_currency,
	close_price,
	the_date 
	FROM tmp_candles 
),
this_pair AS (
	SELECT from_currency, 
	to_currency, 
	close_price AS their_price, 
	the_date 
	FROM point_prices 
	--WHERE from_currency = 'AUD' AND to_currency = 'USD'
),
froms AS (
	SELECT tp.from_currency AS this_currency,
	pp.to_currency AS other_currency, 
	pp.close_price AS other_price,
	pp.the_date 
	FROM this_pair tp
	JOIN point_prices pp ON tp.from_currency = pp.from_currency AND tp.the_date = pp.the_date
	WHERE tp.to_currency <> pp.to_currency
	UNION 
	SELECT tp.from_currency AS this_currency, 
	pp.from_currency AS other_currency,
	1 / pp.close_price AS other_price,
	pp.the_date
	FROM this_pair tp 
	JOIN point_prices pp ON tp.from_currency = pp.to_currency AND tp.the_date = pp.the_date
	WHERE pp.from_currency <> tp.to_currency 
),
tos AS (
	SELECT tp.to_currency AS this_currency,
	pp.to_currency AS other_currency, 
	pp.close_price AS other_price,
	pp.the_date 
	FROM this_pair tp
	JOIN point_prices pp ON tp.to_currency = pp.from_currency AND tp.the_date = pp.the_date
	WHERE tp.to_currency <> pp.to_currency
	UNION 
	SELECT tp.to_currency AS this_currency, 
	pp.from_currency AS other_currency,
	1 / pp.close_price AS other_price,
	pp.the_date
	FROM this_pair tp 
	JOIN point_prices pp ON tp.to_currency = pp.to_currency AND tp.the_date = pp.the_date
	WHERE pp.from_currency <> tp.from_currency 
),
calculated_rates AS (
	SELECT froms.this_currency AS from_currency, 
	tos.this_currency AS to_currency, 
	--froms.other_price,
	--tos.other_price, 
	AVG(froms.other_price / tos.other_price) AS calculated_rate,
	froms.the_date--,
	--froms.other_currency 
	FROM froms 
	JOIN tos ON froms.other_currency = tos.other_currency AND froms.the_date = tos.the_date
	GROUP BY froms.this_currency, tos.this_currency, froms.the_date
),
discrepancies AS (
	SELECT cr.from_currency, cr.to_currency, 
	cr.calculated_rate,
	this_pair.their_price,
	((this_pair.their_price - cr.calculated_rate) / cr.calculated_rate) * 100 AS percent_discrepancy,
	cr.the_date FROM calculated_rates cr
	JOIN this_pair 
	ON this_pair.from_currency = cr.from_currency 
	AND this_pair.to_currency = cr.to_currency 
	AND this_pair.the_date = cr.the_date
)
SELECT * FROM discrepancies WHERE abs(percent_discrepancy) > 0.1






















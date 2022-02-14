--query to extract all winning trades for learning algorithms

DROP TABLE IF EXISTS tmp_currencies; 
DROP TABLE IF EXISTS tmp_currency_pairs;
DROP TABLE IF EXISTS tmp_average_movements;
DROP TABLE IF EXISTS tmp_start_dates;
DROP TABLE IF EXISTS tmp_trade_days; 

WITH ccs AS (
	SELECT UNNEST(ARRAY['AUD','CAD','CHF','EUR','GBP','NZD','JPY','USD']) AS currency
)
SELECT currency INTO TEMPORARY TABLE tmp_currencies FROM ccs;

WITH currency_pairs AS (
	WITH currency_pairs_available AS (
		SELECT DISTINCT from_currency, to_currency FROM exchange_value_tick
	)
	SELECT 
	from_currency, to_currency, 
	from_currency || '/' || to_currency
	FROM currency_pairs_available 
	WHERE from_currency IN (SELECT currency FROM tmp_currencies)
	AND to_currency IN (SELECT currency FROM tmp_currencies)
)
SELECT * INTO TEMPORARY TABLE tmp_currency_pairs FROM currency_pairs;

CREATE INDEX IF NOT EXISTS tmp_currency_pairs_from_currency_idx ON tmp_currency_pairs USING btree(from_currency);
CREATE INDEX IF NOT EXISTS tmp_currency_pairs_to_currency_idx ON tmp_currency_pairs USING btree(to_currency);

WITH true_ranges AS (
	SELECT evt.from_currency, evt.to_currency,
	GREATEST(high_price - low_price, ABS(high_price - LAG(close_price) OVER w),ABS(low_price - LAG(close_price) OVER w)) AS true_range,
	the_date
	FROM exchange_value_tick evt  
	JOIN tmp_currency_pairs tcp ON evt.from_currency = tcp.from_currency AND evt.to_currency  = tcp.to_currency 
	WHERE evt.the_date <= TIMESTAMP '05 Jan 2022' + INTERVAL '13 hours' 
	AND evt.the_date >  TIMESTAMP '05 Jan 2022' + INTERVAL '13 hours' - INTERVAL '100 days' 
	WINDOW w AS (PARTITION BY evt.from_currency, evt.to_currency ORDER BY the_date ASC)
),
average_movements AS (
	SELECT from_currency, to_currency, 
	AVG(true_range) / 2.0 AS average_movement 
	FROM true_ranges
	GROUP BY from_currency, to_currency
) 
SELECT from_currency, to_currency, average_movement INTO TEMPORARY TABLE tmp_average_movements FROM average_movements; 

CREATE INDEX IF NOT EXISTS tmp_average_movements_from_currency_idx ON tmp_average_movements USING btree(from_currency);
CREATE INDEX IF NOT EXISTS tmp_average_movements_to_currency_idx ON tmp_average_movements USING btree(to_currency);


WITH dates_only AS (
	SELECT generate_series(TIMESTAMP '05 Jan 2022' - INTERVAL '250 days', TIMESTAMP '05 Jan 2022', INTERVAL '24 hours') AS the_date
),
dates_without_weekends AS (
	SELECT the_date + INTERVAL '13 hours' AS start_date,
	CASE WHEN EXTRACT(DOW FROM the_date) = 5 THEN 
		the_date + INTERVAL '3 days'
	ELSE 
		the_date + INTERVAL '1 day' 
	END + INTERVAL '13 hours' AS end_date,
	ROW_NUMBER() OVER (ORDER BY the_date) AS day_number
	FROM dates_only 
	WHERE EXTRACT(DOW FROM the_date) = ANY(ARRAY[1,2,3,4,5]) --sat = 6 AND sun = 0
)
SELECT start_date, end_date, day_number INTO TEMPORARY TABLE tmp_start_dates FROM dates_without_weekends;

CREATE INDEX IF NOT EXISTS tmp_start_dates_start_date_idx ON tmp_start_dates USING btree(start_date);
CREATE INDEX IF NOT EXISTS tmp_start_dates_end_date_idx ON tmp_start_dates USING btree(end_date);

WITH trade_days AS (
	SELECT evt.from_currency, evt.to_currency, 
	evt.open_price,
	evt.high_price,
	evt.low_price,
	evt.close_price, 
	evt.the_date,
	tsd.start_date,
	tsd.day_number,
	EXTRACT(HOUR FROM evt.the_date) = ANY(VALUES (17),(22)) AS bad_spread
	FROM tmp_start_dates tsd, exchange_value_tick evt 
	JOIN tmp_currency_pairs tcp ON tcp.from_currency = evt.from_currency AND tcp.to_currency  = evt.to_currency
	WHERE evt.the_date >= tsd.start_date AND evt.the_date < tsd.end_date
	AND evt.the_date > TIMESTAMP '05 Jan 2022' - INTERVAL '250 days'
)
SELECT * INTO TEMPORARY TABLE tmp_trade_days FROM trade_days; 

CREATE INDEX IF NOT EXISTS tmp_trade_days_from_currency_idx ON tmp_trade_days USING btree(from_currency);
CREATE INDEX IF NOT EXISTS tmp_trade_days_to_currency_idx ON tmp_trade_days USING btree(to_currency);
CREATE INDEX IF NOT EXISTS tmp_trade_days_the_date_idx ON tmp_trade_days USING btree(the_date);
CREATE INDEX IF NOT EXISTS tmp_trade_days_start_date_idx ON tmp_trade_days USING btree(start_date);
CREATE INDEX IF NOT EXISTS tmp_trade_days_day_number_idx ON tmp_trade_days USING btree(day_number);


WITH make_candle_numbers AS (
	SELECT from_currency, to_currency, 
	open_price, high_price, low_price, close_price, 
	day_number,
	ROW_NUMBER() OVER (PARTITION BY from_currency, to_currency, start_date ORDER BY the_date ASC) AS candle_number,
	the_date, 
	start_date, 
	bad_spread
	FROM tmp_trade_days
),
starting_prices AS (
	SELECT from_currency, to_currency, 
	start_date, 
	day_number,
	open_price AS start_price 
	FROM make_candle_numbers
	WHERE candle_number = 2 --start candle can be delayed for compensating for calculating time  
),
evaluate_candles AS (
	SELECT mcn.from_currency, mcn.to_currency, 
	mcn.start_date,
	mcn.day_number, 
	mcn.candle_number, 
	--mcn.the_date,
	--tam.average_movement,
	--sp.start_price, mcn.high_price, mcn.low_price,
	--consider high spread times like 5pm and 10pm - be more "pessimistic" at these times by reducing the stoploss factor 
	mcn.high_price > sp.start_price + tam.average_movement * 10  AS buy_win,
	mcn.low_price < sp.start_price - tam.average_movement * (7 - CASE WHEN mcn.bad_spread THEN 2 ELSE 0 END) AS buy_lose, 
	mcn.low_price < sp.start_price - tam.average_movement * 10 AS sell_win, 
	mcn.high_price > sp.start_price + tam.average_movement * (7 - CASE WHEN mcn.bad_spread THEN 2 ELSE 0 END) AS sell_lose
	FROM make_candle_numbers mcn 
	JOIN starting_prices sp ON mcn.from_currency = sp.from_currency AND mcn.to_currency = sp.to_currency AND mcn.day_number = sp.day_number 
	JOIN tmp_average_movements tam ON mcn.from_currency = tam.from_currency AND mcn.to_currency = tam.to_currency
	WHERE mcn.candle_number > 2
),
earliest_buy_win AS (
	SELECT DISTINCT ON (from_currency, to_currency, day_number) 
	from_currency, to_currency, 
	day_number, candle_number 
	FROM evaluate_candles 
	WHERE buy_win 
	ORDER BY from_currency, to_currency, day_number, candle_number
),
earliest_buy_lose AS (
	SELECT DISTINCT ON (from_currency, to_currency, day_number) 
	from_currency, to_currency, 
	day_number, candle_number 
	FROM evaluate_candles 
	WHERE buy_lose 
	ORDER BY from_currency, to_currency, day_number, candle_number
),
earliest_sell_win AS (
	SELECT DISTINCT ON (from_currency, to_currency, day_number) 
	from_currency, to_currency, 
	day_number, candle_number 
	FROM evaluate_candles 
	WHERE sell_win 
	ORDER BY from_currency, to_currency, day_number, candle_number
),
earliest_sell_lose AS (
	SELECT DISTINCT ON (from_currency, to_currency, day_number) 
	from_currency, to_currency, 
	day_number, candle_number 
	FROM evaluate_candles 
	WHERE sell_lose 
	ORDER BY from_currency, to_currency, day_number, candle_number
),
determine AS ( 
	SELECT sp.from_currency, sp.to_currency, 
	sp.start_date, 
	sp.day_number, 
	ebw.candle_number AS candle_buy_win,
	ebl.candle_number AS candle_buy_lose,
	esw.candle_number AS candle_sell_win,
	esl.candle_number AS candle_sell_lose
	FROM starting_prices sp 
	LEFT JOIN earliest_buy_win ebw ON sp.from_currency = ebw.from_currency AND sp.to_currency = ebw.to_currency AND sp.day_number = ebw.day_number 
	LEFT JOIN earliest_buy_lose ebl ON sp.from_currency = ebl.from_currency AND sp.to_currency = ebl.to_currency AND sp.day_number = ebl.day_number 
	LEFT JOIN earliest_sell_win esw ON sp.from_currency = esw.from_currency AND sp.to_currency = esw.to_currency AND sp.day_number = esw.day_number 
	LEFT JOIN earliest_sell_lose esl ON sp.from_currency = esl.from_currency AND sp.to_currency = esl.to_currency AND sp.day_number = esl.day_number 
),
get_wins AS (
	SELECT d.from_currency, d.to_currency, 
	d.day_number, 
	d.start_date, 
	--we dont care if it drew - we only want winning trades 
	COALESCE(d.candle_buy_win,99999) < COALESCE(d.candle_buy_lose,99999) AS buy_win,
	COALESCE(d.candle_sell_win,99999) < COALESCE(d.candle_sell_lose,99999) AS sell_win
	FROM determine d
),
all_results AS (
	SELECT start_date, COUNT(1) AS n, 
	JSON_OBJECT_AGG(
		from_currency || '/' || to_currency, 
		JSON_BUILD_OBJECT(
			'BUY', CASE WHEN buy_win THEN 1 ELSE 0 END,  --only care when hit a winning trade, otherwise 
			'SELL', CASE WHEN sell_win THEN 1 ELSE 0 END, --it is treated as a loss 
			'the_date',the_date
		)
	) AS day_result, 
	day_number
	FROM get_wins 
	GROUP BY start_date, day_number
),
max_n AS (
	SELECT MAX(n) AS N FROM all_results
)
SELECT * FROM all_results r, max_n n
WHERE r.n = n.N 
ORDER BY start_date DESC










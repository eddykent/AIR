--function that will grab candles and condense them into actual candles of the correct size (quarts,halfs,hours,quads)
--quarts are 15m, halfs are 30m and quads are 4h candles 

--from currencies 
DROP FUNCTION IF EXISTS trading.get_candles_from_instruments(TEXT[], timestamp, int, int, int);
CREATE OR REPLACE FUNCTION trading.get_candles_from_instruments(_instruments TEXT[], _this_date TIMESTAMP, _days_back INTEGER, _chart_resolution INTEGER DEFAULT 15, _candle_offset INTEGER DEFAULT 0)
RETURNS TABLE (
	row_index INTEGER,	
	from_currency TEXT,
	to_currency TEXT,
	full_name TEXT, --INDEX 
	open_price DOUBLE PRECISION,
	high_price DOUBLE PRECISION,
	low_price DOUBLE PRECISION,
	close_price DOUBLE PRECISION,
	the_date TIMESTAMP, --INDEX 
	candle_index INTEGER, 
	time_index INTEGER
)
AS $$

--function that will grab candles and condense them into actual candles of the correct size (quarts,halfs,hours,quads)
--quarts are 15m, halfs are 30m and quads are 4h candles 

BEGIN
	DROP TABLE IF EXISTS _return_candles;

	--build candles of our chosen chart size 
	CREATE TEMPORARY TABLE _return_candles
	--ON COMMIT DROP --consider  
	AS (
		WITH selected_candles AS (
			SELECT evt.from_currency, evt.to_currency,
			evt.open_price,
			evt.high_price,
			evt.low_price,
			evt.close_price, 
			evt.the_date - (_candle_offset || ' mins')::INTERVAL AS the_date
			FROM exchange_value_tick evt 
			WHERE evt.full_name  = ANY(_instruments) 
			AND evt.the_date < _this_date
			AND evt.the_date >= _this_date -  (_days_back || ' days')::INTERVAL --600 = 400 + 200 (days_back + normalisation_window)
		), 
		candle_indexs AS (
			SELECT sc.from_currency, 
			sc.to_currency,
			sc.open_price,
			sc.high_price,
			sc.low_price,
			sc.close_price,
			TO_TIMESTAMP (FLOOR(( EXTRACT ('EPOCH' FROM (sc.the_date )) ) / (60*15) ) * (60*15)) AT TIME ZONE 'UTC' AS the_date, --fix date
			(EXTRACT(MINUTE FROM sc.the_date) + 60 * EXTRACT (HOUR FROM sc.the_date))::INT / _chart_resolution AS candle_index,
			sc.the_date::DATE AS date_day
			FROM selected_candles sc
		),
		almost_candles AS (
			SELECT ci.from_currency, 
			ci.to_currency, 
			ci.candle_index,
			COUNT(1) AS n,
			ARRAY_AGG(ci.open_price ORDER BY ci.the_date) AS open_prices, 
			MAX(ci.high_price) AS high_price,
			MIN(ci.low_price) AS low_price,
			ARRAY_AGG(ci.close_price ORDER BY ci.the_date) AS close_prices,
			MIN(ci.the_date) AS the_date
			FROM candle_indexs ci
			GROUP BY ci.from_currency, ci.to_currency, ci.candle_index, ci.date_day
		),
		time_indexed_candles AS (
			SELECT 
			(ROW_NUMBER() OVER ())::INTEGER AS row_index,
			c.from_currency,
			c.to_currency,
			c.from_currency || '/' || c.to_currency AS full_name,
			c.open_prices[1] AS open_price,
			c.high_price,
			c.low_price,
			c.close_prices[c.n] AS close_price,
			c.the_date + (_candle_offset || ' mins')::INTERVAL AS the_date,
			c.candle_index,
			(ROW_NUMBER() OVER (PARTITION BY c.from_currency, c.to_currency ORDER BY c.the_date))::INTEGER AS time_index-- 
			--t.time_index 
			FROM almost_candles c 
			--JOIN time_indexs t ON c.the_date = t.the_date
		)
		SELECT * FROM time_indexed_candles
	);

	CREATE INDEX _return_candles_from_currency_idx ON _return_candles USING btree(from_currency);
	CREATE INDEX _return_candles_to_currency_idx ON _return_candles USING btree(to_currency);
	CREATE INDEX _return_candles_full_name_idx ON _return_candles USING btree(full_name);
	CREATE INDEX _return_candles_the_date_idx ON _return_candles USING btree(the_date); --check

	RETURN QUERY SELECT * FROM _return_candles; 

END
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION trading.get_candles_from_instruments(TEXT[], timestamp, int, int, int) IS 'From a set of instruments, and a timestamp, get the associated forex candles.';

--TEST
--SELECT * FROM get_candles_from_instruments(ARRAY['EUR/USD','GBP/JPY'], '07 Mar 2022 12:30:00'::timestamp, 100, 240,120) 




















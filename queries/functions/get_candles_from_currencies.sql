--function that will grab candles and condense them into actual candles of the correct size (quarts,halfs,hours,quads)
--quarts are 15m, halfs are 30m and quads are 4h candles 

--from currencies 
--DROP FUNCTION IF EXISTS trading.get_candles_from_currencies(TEXT[], timestamp, int, int, int);
DROP FUNCTION IF EXISTS trading.get_candles_from_currencies(TEXT[], timestamp, int, int, int, bool);
CREATE OR REPLACE FUNCTION trading.get_candles_from_currencies(_currencies TEXT[], _this_date TIMESTAMP, _days_back INTEGER, _chart_resolution INTEGER DEFAULT 15, _candle_offset INTEGER DEFAULT 0, _ask_candles BOOL DEFAULT FALSE)
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
	DROP TABLE IF EXISTS __currencies_tmp; 
	CREATE TEMPORARY TABLE __currencies_tmp 
	ON COMMIT DROP 
	AS ( 
		SELECT UNNEST(_currencies) AS currency
	);
	
	DROP TABLE IF EXISTS _get_candles_from_currencies;

	--build candles of our chosen chart size 
	CREATE TEMPORARY TABLE _get_candles_from_currencies
	ON COMMIT DROP  
	AS (
		WITH selected_candles AS (
			SELECT rfc.from_currency, rfc.to_currency,
			CASE WHEN _ask_candles THEN rfc.ask_open ELSE rfc.bid_open END AS open_price,
			CASE WHEN _ask_candles THEN rfc.ask_high ELSE rfc.bid_high END AS high_price,
			CASE WHEN _ask_candles THEN rfc.ask_low ELSE rfc.bid_low END AS low_price,
			CASE WHEN _ask_candles THEN rfc.ask_close ELSE rfc.bid_close END AS close_price, 
			rfc.the_date - (_candle_offset || ' mins')::INTERVAL AS the_date
			FROM raw_fx_candles_15m rfc 
			WHERE rfc.from_currency  = ANY(SELECT currency FROM __currencies_tmp) 
			AND rfc.to_currency = ANY(SELECT currency FROM __currencies_tmp)
			AND rfc.the_date < _this_date
			AND rfc.the_date >= _this_date -  (_days_back || ' days')::INTERVAL --600 = 400 + 200 (days_back + normalisation_window)
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
	
	CREATE INDEX _get_candles_from_currencies_row_index_idx ON _get_candles_from_currencies USING btree(row_index);
	CREATE INDEX _get_candles_from_currencies_full_name_idx ON _get_candles_from_currencies USING btree(full_name);
	CREATE INDEX _get_candles_from_currencies_the_date_idx ON _get_candles_from_currencies USING btree(the_date); --check

	RETURN QUERY SELECT * FROM _get_candles_from_currencies; 

END
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION trading.get_candles_from_currencies(TEXT[], timestamp, int, int, int, bool) IS 'From a set of currencies, and a timestamp, get the associated forex candles.';

--TEST
--SELECT * FROM get_candles_from_currencies(ARRAY['EUR','USD','GBP','JPY'], '07 Mar 2022 12:30:00'::timestamp, 100) 


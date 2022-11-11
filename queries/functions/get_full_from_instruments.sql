--function that will grab everything and condense them into actual candles of the correct size (quarts,halfs,hours,quads)
--quarts are 15m, halfs are 30m and quads are 4h candles 


--from instruments 
--DROP FUNCTION IF EXISTS trading.get_full_from_instruments(TEXT[], timestamp, int, int, int);
DROP FUNCTION IF EXISTS trading.get_full_from_instruments(TEXT[], timestamp, int, int, int);
CREATE OR REPLACE FUNCTION trading.get_full_from_instruments(_instruments TEXT[], _this_date TIMESTAMP, _days_back INTEGER, _chart_resolution INTEGER DEFAULT 15, _candle_offset INTEGER DEFAULT 0)
RETURNS TABLE (
	row_index INTEGER,	
	from_currency TEXT,
	to_currency TEXT,
	full_name TEXT, --INDEX 
	bid_open DOUBLE PRECISION,
	bid_high DOUBLE PRECISION,
	bid_low DOUBLE PRECISION,
	bid_close DOUBLE PRECISION,
	ask_open DOUBLE PRECISION,
	ask_high DOUBLE PRECISION,
	ask_low DOUBLE PRECISION,
	ask_close DOUBLE PRECISION,
	bid_volume DOUBLE PRECISION,
	ask_volume DOUBLE PRECISION,
	the_date TIMESTAMP, --INDEX 
	candle_index INTEGER, 
	time_index INTEGER
)
AS $$

--function that will grab full and condense them into actual candles of the correct size (quarts,halfs,hours,quads)
--quarts are 15m, halfs are 30m and quads are 4h candles 

BEGIN
	DROP TABLE IF EXISTS _get_full_from_instruments;

	--build candles of our chosen chart size 
	CREATE TEMPORARY TABLE _get_full_from_instruments
	ON COMMIT DROP  
	AS (
		WITH selected_full AS (
			SELECT rfc.from_currency, rfc.to_currency,
			rfc.bid_open,
			rfc.bid_high,
			rfc.bid_low,
			rfc.bid_close,
			rfc.ask_open,
			rfc.ask_high,
			rfc.ask_low,
			rfc.ask_close,
			rfc.bid_volume,
			rfc.ask_volume,
			rfc.the_date - (_candle_offset || ' mins')::INTERVAL AS the_date
			FROM raw_fx_candles_15m rfc 
			WHERE rfc.full_name  = ANY(_instruments) 
			AND rfc.the_date < _this_date
			AND rfc.the_date >= _this_date -  (_days_back || ' days')::INTERVAL --600 = 400 + 200 (days_back + normalisation_window)
		), 
		candle_indexs AS (
			SELECT sc.from_currency, 
			sc.to_currency,
			sc.bid_open,
			sc.bid_high,
			sc.bid_low,
			sc.bid_close,
			sc.ask_open,
			sc.ask_high,
			sc.ask_low,
			sc.ask_close,
			sc.bid_volume,
			sc.ask_volume,
			TO_TIMESTAMP (FLOOR(( EXTRACT ('EPOCH' FROM (sc.the_date )) ) / (60*15) ) * (60*15)) AT TIME ZONE 'UTC' AS the_date, --fix date
			(EXTRACT(MINUTE FROM sc.the_date) + 60 * EXTRACT (HOUR FROM sc.the_date))::INT / _chart_resolution AS candle_index,
			sc.the_date::DATE AS date_day
			FROM selected_full sc
		),
		almost_full AS (
			SELECT ci.from_currency, 
			ci.to_currency, 
			ci.candle_index,
			COUNT(1) AS n,
			ARRAY_AGG(ci.bid_open ORDER BY ci.the_date) AS bid_opens, 
			MAX(ci.bid_high) AS bid_high,
			MIN(ci.bid_low) AS bid_low,
			ARRAY_AGG(ci.bid_close ORDER BY ci.the_date) AS bid_closes,
			ARRAY_AGG(ci.ask_open ORDER BY ci.the_date) AS ask_opens, 
			MAX(ci.ask_high) AS ask_high,
			MIN(ci.ask_low) AS ask_low,
			ARRAY_AGG(ci.ask_close ORDER BY ci.the_date) AS ask_closes,
			SUM(ci.bid_volume) AS bid_volume,
			SUM(ci.ask_volume) AS ask_volume,
			MIN(ci.the_date) AS the_date
			FROM candle_indexs ci
			GROUP BY ci.from_currency, ci.to_currency, ci.candle_index, ci.date_day
		),
		time_indexed_full AS (
			SELECT 
			(ROW_NUMBER() OVER ())::INTEGER AS row_index,
			c.from_currency,
			c.to_currency,
			c.from_currency || '/' || c.to_currency AS full_name,
			c.bid_opens[1] AS bid_open,
			c.bid_high,
			c.bid_low,
			c.bid_closes[c.n] AS bid_close,
			c.ask_opens[1] AS ask_open,
			c.ask_high,
			c.ask_low,
			c.ask_closes[c.n] AS ask_close,
			c.bid_volume,
			c.ask_volume,
			c.the_date + (_candle_offset || ' mins')::INTERVAL AS the_date,
			c.candle_index,
			(ROW_NUMBER() OVER (PARTITION BY c.from_currency, c.to_currency ORDER BY c.the_date))::INTEGER AS time_index-- 
			--t.time_index 
			FROM almost_full c 
			--JOIN time_indexs t ON c.the_date = t.the_date
		)
		SELECT * FROM time_indexed_full
	);
	
	CREATE INDEX _get_full_from_instruments_row_index_idx ON _get_full_from_instruments USING btree(row_index);
	CREATE INDEX _get_full_from_instruments_full_name_idx ON _get_full_from_instruments USING btree(full_name);
	CREATE INDEX _get_full_from_instruments_the_date_idx ON _get_full_from_instruments USING btree(the_date); --check

	RETURN QUERY SELECT * FROM _get_full_from_instruments; 

END
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION trading.get_full_from_instruments(TEXT[], timestamp, int, int, int) IS 'From a set of instruments, and a timestamp, get the associated bid and ask forex candles and volumes.';

--TEST
--SELECT * FROM get_candles_from_instruments(ARRAY['EUR','USD','GBP','JPY'], '07 Mar 2022 12:30:00'::timestamp, 100) 


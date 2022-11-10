

--from currencies 

--DROP FUNCTION IF EXISTS trading.get_partial_candles_from_instruments(TEXT[], TIMESTAMP[], int, int);
DROP FUNCTION IF EXISTS trading.get_partial_candles_from_instruments(TEXT[], TIMESTAMP[], int, int, bool);
CREATE OR REPLACE FUNCTION trading.get_partial_candles_from_instruments(_instruments TEXT[], _trade_times TIMESTAMP[], _chart_resolution INTEGER DEFAULT 15, _candle_offset INTEGER DEFAULT 0, _ask_candles BOOLEAN DEFAULT FALSE)
RETURNS TABLE (
	row_index INTEGER,	
	from_currency TEXT,
	to_currency TEXT,
	full_name TEXT, --INDEX 
	open_price DOUBLE PRECISION,
	high_price DOUBLE PRECISION,
	low_price DOUBLE PRECISION,
	close_price DOUBLE PRECISION,
	the_date TIMESTAMP
)
AS $$

BEGIN 

	DROP TABLE IF EXISTS __candle_ends;
	CREATE TEMPORARY TABLE __candle_ends 
	AS (
		SELECT * FROM UNNEST(ARRAY[_trade_times]
		) WITH ORDINALITY AS a(the_date,row_index)
	);

	DROP TABLE IF EXISTS __candle_ranges; 
	CREATE TEMPORARY TABLE __candle_ranges
	ON COMMIT DROP 
	AS (
		WITH the_range AS (
			SELECT 
				MIN(ce.the_date) - (_chart_resolution || ' mins')::INTERVAL AS start_date,  --chart_resolution
				MAX(ce.the_date) + INTERVAL '2 mins' AS end_date --enure we get all candles so add buffer 
			FROM __candle_ends ce
		),
		candle_cutoffs AS (
			SELECT generate_series(
				tr.start_date::date::timestamp,
				tr.end_date::date::timestamp + INTERVAL '1 day',
				(_chart_resolution || ' mins')::INTERVAL --candle offset
			) - (_candle_offset || ' mins')::INTERVAL 
			AS pc_start_date
			FROM the_range tr
		)
		SELECT cc.pc_start_date AS start_date, 
			TO_TIMESTAMP (FLOOR(( EXTRACT ('EPOCH' FROM (ce.the_date )) ) / (60*15) ) * (60*15)) AT TIME ZONE 'UTC' AS end_date, --roll back to nearest 15 mins !
			ce.the_date,
			ce.row_index
		FROM __candle_ends ce 
		JOIN candle_cutoffs cc ON cc.pc_start_date <= ce.the_date AND cc.pc_start_date + (_chart_resolution || ' mins')::INTERVAL > ce.the_date
		ORDER BY row_index
	);
	
	DROP TABLE IF EXISTS _get_partial_candles_from_instruments;
	CREATE TEMPORARY TABLE _get_partial_candles_from_instruments
	ON COMMIT DROP 
	AS (
		WITH the_range AS (
			SELECT 
				MIN(ce.the_date) - (_chart_resolution || ' mins')::INTERVAL AS start_date, 
				MAX(ce.the_date) + INTERVAL '2 minutes' AS end_date --enure we get all candles so add buffer 
			FROM __candle_ends ce
		),
		selected_candles AS (
			SELECT rfc.from_currency, rfc.to_currency,
			CASE WHEN _ask_candles THEN rfc.ask_open ELSE rfc.bid_open END AS open_price,
			CASE WHEN _ask_candles THEN rfc.ask_high ELSE rfc.bid_high END AS high_price,
			CASE WHEN _ask_candles THEN rfc.ask_low ELSE rfc.bid_low END AS low_price,
			CASE WHEN _ask_candles THEN rfc.ask_close ELSE rfc.bid_close END AS close_price, 
			rfc.the_date
			FROM raw_fx_candles_15m rfc
			JOIN the_range tr ON rfc.the_date <= tr.end_date AND rfc.the_date >= tr.start_date AND tsrange(tr.start_date,tr.end_date) @> rfc.the_date
			WHERE rfc.full_name  = ANY(_instruments) 
		), 
		candle_groups AS (
			SELECT sc.from_currency, 
			sc.to_currency,
			sc.open_price,
			sc.high_price,
			sc.low_price,
			sc.close_price,
			TO_TIMESTAMP (FLOOR(( EXTRACT ('EPOCH' FROM (sc.the_date )) ) / (60*15) ) * (60*15)) AT TIME ZONE 'UTC' AS the_date, --fix date
			cr.row_index
			FROM selected_candles sc
			JOIN __candle_ranges cr ON sc.the_date >= cr.start_date AND sc.the_date < cr.end_date AND tsrange(cr.start_date,cr.end_date) @> sc.the_date
		),
		almost_candles AS (
			SELECT 
			cg.row_index,
			cg.from_currency, 
			cg.to_currency, 
			COUNT(1) AS n,
			ARRAY_AGG(cg.open_price ORDER BY cg.the_date) AS open_prices, 
			MAX(cg.high_price) AS high_price,
			MIN(cg.low_price) AS low_price,
			ARRAY_AGG(cg.close_price ORDER BY cg.the_date) AS close_prices,
			MIN(cg.the_date) AS the_date 
			FROM candle_groups cg
			GROUP BY cg.from_currency, cg.to_currency, cg.row_index
		),
		partial_candles AS (
			SELECT 
			c.row_index::INTEGER,
			c.from_currency,
			c.to_currency,
			c.from_currency || '/' || c.to_currency AS full_name,
			c.open_prices[1] AS open_price,
			c.high_price,
			c.low_price,
			c.close_prices[c.n] AS close_price,
			c.the_date
			FROM almost_candles c 
		)
		SELECT * FROM partial_candles
	);
	
	CREATE INDEX _get_partial_candles_from_instruments_row_index_idx ON _get_partial_candles_from_instruments USING btree(row_index);
	CREATE INDEX _get_partial_candles_from_instruments_full_name_idx ON _get_partial_candles_from_instruments USING btree(full_name);
	CREATE INDEX _get_partial_candles_from_instruments_the_date_idx ON _get_partial_candles_from_instruments USING btree(the_date); --check

	RETURN QUERY SELECT * FROM _get_partial_candles_from_instruments; 

END
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION trading.get_partial_candles_from_instruments(TEXT[], TIMESTAMP[], int, int, bool) IS 'From instrument names and candle end times, get the associated forex partial candles';











--from currencies 

DROP FUNCTION IF EXISTS trading.get_partial_candles_volumes_from_instruments(TEXT[], TIMESTAMP[], int, int);
CREATE OR REPLACE FUNCTION trading.get_partial_candles_volumes_from_instruments(_instruments TEXT[], _trade_times TIMESTAMP[], _chart_resolution INTEGER DEFAULT 15, _candle_offset INTEGER DEFAULT 0)
RETURNS TABLE (
	row_index INTEGER,	
	from_currency TEXT,
	to_currency TEXT,
	full_name TEXT, --INDEX 
	open_price DOUBLE PRECISION,
	high_price DOUBLE PRECISION,
	low_price DOUBLE PRECISION,
	close_price DOUBLE PRECISION,
	bid_volume DOUBLE PRECISION,
	ask_volume DOUBLE PRECISION,
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
	
	DROP TABLE IF EXISTS _get_partial_candles_volumes_from_instruments;
	CREATE TEMPORARY TABLE _get_partial_candles_volumes_from_instruments
	ON COMMIT DROP 
	AS (
		WITH the_range AS (
			SELECT 
				MIN(ce.the_date) - (_chart_resolution || ' mins')::INTERVAL AS start_date, 
				MAX(ce.the_date) + INTERVAL '2 minutes' AS end_date --enure we get all candles so add buffer 
			FROM __candle_ends ce
		),
		selected_candles AS (
			SELECT evt.from_currency, evt.to_currency,
			evt.open_price,
			evt.high_price,
			evt.low_price,
			evt.close_price, 
			evt.the_date
			FROM exchange_value_tick evt
			JOIN the_range tr ON evt.the_date <= tr.end_date AND evt.the_date >= tr.start_date AND tsrange(tr.start_date,tr.end_date) @> evt.the_date
			WHERE evt.full_name  = ANY(_instruments) 
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
		selected_volumes AS (
			SELECT evt.from_currency, evt.to_currency,
			evt.bid_volume,
			evt.ask_volume,
			evt.the_date
			FROM exchange_volume_tick evt
			JOIN the_range tr ON evt.the_date <= tr.end_date AND evt.the_date >= tr.start_date AND tsrange(tr.start_date,tr.end_date) @> evt.the_date
			WHERE evt.full_name = ANY(_instruments) 
		), 
		volume_groups AS (
			SELECT sv.from_currency, 
			sv.to_currency,
			sv.bid_volume,
			sv.ask_volume,
			TO_TIMESTAMP (FLOOR(( EXTRACT ('EPOCH' FROM (sv.the_date )) ) / (60*15) ) * (60*15)) AT TIME ZONE 'UTC' AS the_date, --fix date
			cr.row_index
			FROM selected_volumes sv
			JOIN __candle_ranges cr ON sv.the_date >= cr.start_date AND sv.the_date < cr.end_date AND tsrange(cr.start_date,cr.end_date) @> sv.the_date
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
			SUM(vg.bid_volume) AS bid_volume,
			SUM(vg.ask_volume) AS ask_volume,
			LEAST(MIN(cg.the_date),MIN(vg.the_date)) AS the_date
			FROM candle_groups cg 
			JOIN volume_groups vg ON cg.from_currency = vg.from_currency AND cg.to_currency = vg.to_currency 
			AND cg.row_index = vg.row_index AND cg.the_date = vg.the_date
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
			c.bid_volume,
			c.ask_volume,
			c.the_date
			FROM almost_candles c 
		)
		SELECT * FROM partial_candles
	);
	
	CREATE INDEX _get_partial_candles_volumes_from_instruments_row_index_idx ON _get_partial_candles_volumes_from_instruments USING btree(row_index);
	CREATE INDEX _get_partial_candles_volumes_from_instruments_full_name_idx ON _get_partial_candles_volumes_from_instruments USING btree(full_name);
	CREATE INDEX _get_partial_candles_volumes_from_instruments_the_date_idx ON _get_partial_candles_volumes_from_instruments USING btree(the_date); --check

	RETURN QUERY SELECT * FROM _get_partial_candles_volumes_from_instruments; 

END
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION trading.get_partial_candles_volumes_from_instruments(TEXT[], TIMESTAMP[], int, int) IS 'From a set of currencies and candle end times, get the associated forex partial candles and volumes';





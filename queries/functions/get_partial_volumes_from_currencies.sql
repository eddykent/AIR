

--from currencies 

DROP FUNCTION IF EXISTS trading.get_partial_volumes_from_currencies(TEXT[], TIMESTAMP[], int, int);
CREATE OR REPLACE FUNCTION trading.get_partial_volumes_from_currencies(_currencies TEXT[], _trade_times TIMESTAMP[], _chart_resolution INTEGER DEFAULT 15, _candle_offset INTEGER DEFAULT 0)
RETURNS TABLE (
	row_index INTEGER,	
	from_currency TEXT,
	to_currency TEXT,
	full_name TEXT, --INDEX 
	bid_volume DOUBLE PRECISION,
	ask_volume DOUBLE PRECISION,
	the_date TIMESTAMP
)
AS $$

BEGIN 
	
	DROP TABLE IF EXISTS __currencies_tmp; 
	CREATE TEMPORARY TABLE __currencies_tmp 
	ON COMMIT DROP 
	AS ( 
		SELECT UNNEST(_currencies) AS currency
	);

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
	
	DROP TABLE IF EXISTS _get_partial_volumes_from_currencies;
	CREATE TEMPORARY TABLE _get_partial_volumes_from_currencies
	ON COMMIT DROP 
	AS (
		WITH the_range AS (
			SELECT 
				MIN(ce.the_date) - (_chart_resolution || ' mins')::INTERVAL AS start_date, 
				MAX(ce.the_date) + INTERVAL '2 minutes' AS end_date --enure we get all candles so add buffer 
			FROM __candle_ends ce
		),
		selected_volumes AS (
			SELECT evt.from_currency, evt.to_currency,
			evt.bid_volume,
			evt.ask_volume,
			evt.the_date
			FROM exchange_volume_tick evt
			JOIN the_range tr ON evt.the_date <= tr.end_date AND evt.the_date >= tr.start_date AND tsrange(tr.start_date,tr.end_date) @> evt.the_date
			WHERE evt.from_currency = ANY(SELECT currency FROM __currencies_tmp) 
			AND evt.to_currency = ANY(SELECT currency FROM __currencies_tmp) 
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
		collected_volumes AS (
			SELECT 
			vg.row_index,
			vg.from_currency, 
			vg.to_currency, 
			SUM(vg.bid_volume) AS bid_volume,
			SUM(vg.ask_volume) AS ask_volume,			
			MIN(vg.the_date) AS the_date 
			FROM volume_groups vg
			GROUP BY vg.from_currency, vg.to_currency, vg.row_index
		),
		partial_candles AS (
			SELECT 
			cv.row_index::INTEGER,
			cv.from_currency,
			cv.to_currency,
			cv.from_currency || '/' || cv.to_currency AS full_name,
			cv.bid_volume,
			cv.ask_volume,
			cv.the_date
			FROM collected_volumes cv 
		)
		SELECT * FROM partial_candles
	);
	
	CREATE INDEX _get_partial_volumes_from_currencies_row_index_idx ON _get_partial_volumes_from_currencies USING btree(row_index);
	CREATE INDEX _get_partial_volumes_from_currencies_full_name_idx ON _get_partial_volumes_from_currencies USING btree(full_name);
	CREATE INDEX _get_partial_volumes_from_currencies_the_date_idx ON _get_partial_volumes_from_currencies USING btree(the_date); --check

	RETURN QUERY SELECT * FROM _get_partial_volumes_from_currencies; 

END
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION trading.get_partial_volumes_from_currencies(TEXT[], TIMESTAMP[], int, int) IS 'From currencies and candle end times, get the associated forex partial volumes';



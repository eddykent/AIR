--function that will grab candles and condense them into actual candles of the correct size (quarts,halfs,hours,quads)
--quarts are 15m, halfs are 30m and quads are 4h candles 

--from currencies 
DROP FUNCTION IF EXISTS trading.get_volumes_from_currencies(TEXT[], timestamp, int, int, int);
CREATE OR REPLACE FUNCTION trading.get_volumes_from_currencies(_currencies TEXT[], _this_date TIMESTAMP, _days_back INTEGER, _chart_resolution INTEGER DEFAULT 15, _candle_offset INTEGER DEFAULT 0)
RETURNS TABLE (
	row_index INTEGER,	
	from_currency TEXT,
	to_currency TEXT,
	full_name TEXT, --INDEX 
	bid_volume DOUBLE PRECISION,
	ask_volume DOUBLE PRECISION,
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
	
	DROP TABLE IF EXISTS _get_volumes_from_currencies;

	--build volumes of our chosen chart size 
	CREATE TEMPORARY TABLE _get_volumes_from_currencies
	ON COMMIT DROP  
	AS (
		WITH selected_volume AS (
			SELECT rfc.from_currency, rfc.to_currency,
			rfc.bid_volume,
			rfc.ask_volume,
			rfc.the_date - (_candle_offset || ' mins')::INTERVAL AS the_date
			FROM raw_fx_candles_15m rfc
			WHERE rfc.from_currency  = ANY(SELECT currency FROM __currencies_tmp) 
			AND rfc.to_currency = ANY(SELECT currency FROM __currencies_tmp)
			AND rfc.the_date < _this_date
			AND rfc.the_date >= _this_date -  (_days_back || ' days')::INTERVAL --600 = 400 + 200 (days_back + normalisation_window)
		), 
		volume_indexs AS (
			SELECT sv.from_currency, 
			sv.to_currency,
			sv.bid_volume,
			sv.ask_volume,
			TO_TIMESTAMP (FLOOR(( EXTRACT ('EPOCH' FROM (sv.the_date )) ) / (60*15) ) * (60*15)) AT TIME ZONE 'UTC' AS the_date, --fix date
			(EXTRACT(MINUTE FROM sv.the_date) + 60 * EXTRACT (HOUR FROM sv.the_date))::INT / _chart_resolution AS volume_index,
			sv.the_date::DATE AS date_day
			FROM selected_volume sv
		),
		collected_volumes AS (
			SELECT vi.from_currency, 
			vi.to_currency, 
			vi.volume_index,
			SUM(vi.bid_volume) AS bid_volume,
			SUM(vi.ask_volume) AS ask_volume,
			MIN(vi.the_date) AS the_date
			FROM volume_indexs vi
			GROUP BY vi.from_currency, vi.to_currency, vi.volume_index, vi.date_day
		),
		time_indexed_volumes AS (
			SELECT 
			(ROW_NUMBER() OVER ())::INTEGER AS row_index,
			v.from_currency,
			v.to_currency,
			v.from_currency || '/' || v.to_currency AS full_name,
			v.bid_volume,
			v.ask_volume,
			v.the_date + (_candle_offset || ' mins')::INTERVAL AS the_date,
			v.volume_index AS candle_index, --should line up with candles
			(ROW_NUMBER() OVER (PARTITION BY v.from_currency, v.to_currency ORDER BY v.the_date))::INTEGER AS time_index-- 
			--t.time_index 
			FROM collected_volumes v
			--JOIN time_indexs t ON c.the_date = t.the_date
		)
		SELECT * FROM time_indexed_volumes
	);
	
	CREATE INDEX _get_volumes_from_currencies_row_index_idx ON _get_volumes_from_currencies USING btree(row_index);
	CREATE INDEX _get_volumes_from_currencies_full_name_idx ON _get_volumes_from_currencies USING btree(full_name);
	CREATE INDEX _get_volumes_from_currencies_the_date_idx ON _get_volumes_from_currencies USING btree(the_date); --check

	RETURN QUERY SELECT * FROM _get_volumes_from_currencies; 

END
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION trading.get_volumes_from_currencies(TEXT[], timestamp, int, int, int) IS 'From a set of currencies, and a timestamp, get the associated forex volumes.';

--TEST
--SELECT * FROM trading.get_volume_from_currencies(ARRAY['EUR','USD','GBP','JPY'], '07 Mar 2022 12:30:00'::timestamp, 100) 

--join test:
--SELECT count(1) FROM trading.get_volume_from_currencies(ARRAY['EUR','USD','GBP','JPY'], '07 Mar 2022 12:30:00'::timestamp, 100) vols
--JOIN trading.get_candles_from_currencies(ARRAY['EUR','USD','GBP','JPY'], '07 Mar 2022 12:30:00'::timestamp, 100) cands
--ON vols.the_date = cands.the_date AND vols.full_name = cands.full_name



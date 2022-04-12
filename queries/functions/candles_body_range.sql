--function for taking in a set of candles and returning their body range

DROP FUNCTION IF EXISTS trading.candles_body_range(_candles_tmp TEXT);
CREATE OR REPLACE FUNCTION trading.candles_body_range(_candles_tmp TEXT)
RETURNS TABLE (
	row_index INTEGER, 
	full_name TEXT,
	the_date TIMESTAMP,
	body_range DOUBLE PRECISION
)
AS $$
BEGIN 
	DROP TABLE IF EXISTS __candles_body_range_tmp;
	EXECUTE FORMAT('ALTER TABLE %s RENAME TO __candles_body_range_tmp', _candles_tmp); --possibly just use formatter -- might NOT be parallelizable 
	DROP TABLE IF EXISTS __candles_body_range_results;
	CREATE TEMPORARY TABLE __candles_body_range_results 
	ON COMMIT DROP
	AS (
		SELECT 
		c.row_index, 
		c.full_name, 
		c.the_date,
		ABS(c.open_price - c.close_price) AS body_range
		FROM __candles_body_range_tmp c
	);
	EXECUTE FORMAT('ALTER TABLE __candles_body_range_tmp RENAME TO %s', _candles_tmp);
	
	CREATE INDEX __candles_body_range_results_row_index_idx ON __candles_body_range_results USING btree(row_index);
	CREATE INDEX __candles_body_range_results_full_name_idx ON __candles_body_range_results USING btree(full_name);
	CREATE INDEX __candles_body_range_results_the_date_idx ON __candles_body_range_results USING btree(the_date);
	
	RETURN QUERY SELECT * FROM __candles_body_range_results;
END
$$ LANGUAGE plpgsql; 

COMMENT ON FUNCTION trading.candles_body_range(TEXT) IS 'From a set of candles, get their mean price';

--TEST
--DROP TABLE IF EXISTS candles_tmp CASCADE;
--SELECT * INTO candles_tmp FROM get_candles_from_instruments(ARRAY['EUR/GBP','USD/JPY'], '07 Mar 2022 12:30:00'::timestamp, 100, 240,120)
--SELECT * FROM candles_body_range('candles_tmp');

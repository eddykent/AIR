--function for taking in a set of candles and returning their mean

DROP FUNCTION IF EXISTS candles_mean_price(_candles_tmp TEXT);
CREATE OR REPLACE FUNCTION candles_mean_price(_candles_tmp TEXT)
RETURNS TABLE (
	row_index INTEGER, 
	full_name TEXT,
	the_date TIMESTAMP,
	mean_price DOUBLE PRECISION
)
AS $$
BEGIN 
	DROP TABLE IF EXISTS __candles_mean_price_tmp;
	EXECUTE FORMAT('ALTER TABLE %s RENAME TO __candles_mean_price_tmp', _candles_tmp); --possibly just use formatter -- might NOT be parallelizable 
	DROP TABLE IF EXISTS __candles_mean_price_results;
	CREATE TEMPORARY TABLE __candles_mean_price_results 
	ON COMMIT DROP
	AS (
		SELECT 
		c.row_index, 
		c.full_name, 
		c.the_date,
		(c.open_price + c.high_price + c.low_price + c.close_price) / 4.0 AS mean_price
		FROM __candles_mean_price_tmp c
	);
	EXECUTE FORMAT('ALTER TABLE __candles_mean_price_tmp RENAME TO %s', _candles_tmp);
	
	CREATE INDEX __candles_mean_price_results_row_index_idx ON __candles_mean_price_results USING btree(row_index);
	CREATE INDEX __candles_mean_price_results_full_name_idx ON __candles_mean_price_results USING btree(full_name);
	CREATE INDEX __candles_mean_price_results_the_date_idx ON __candles_mean_price_results USING btree(the_date);
	
	RETURN QUERY SELECT * FROM __candles_mean_price_results;
END
$$ LANGUAGE plpgsql; 

COMMENT ON FUNCTION candles_mean_price(TEXT) IS 'From a set of candles, get their mean price';

--TEST
--DROP TABLE IF EXISTS candles_tmp CASCADE;
--SELECT * INTO candles_tmp FROM get_candles_from_instruments(ARRAY['EUR/GBP','USD/JPY'], '07 Mar 2022 12:30:00'::timestamp, 100, 240,120)
--SELECT * FROM candles_mean_price('candles_tmp');

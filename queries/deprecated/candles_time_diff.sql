--function for taking in a set of candles and returning their difference

DROP FUNCTION IF EXISTS trading.candles_time_diff(_candles_tmp TEXT, _difference INT );
CREATE OR REPLACE FUNCTION trading.candles_time_diff(_candles_tmp TEXT, _difference INT DEFAULT 1)
RETURNS TABLE (
	row_index INTEGER, 
	full_name TEXT,
	the_date TIMESTAMP,
	open_difference DOUBLE PRECISION, 
	high_difference DOUBLE PRECISION,
	low_difference DOUBLE PRECISION,
	close_difference DOUBLE PRECISION
)
AS $$
BEGIN 
	DROP TABLE IF EXISTS __candles_time_diff_tmp;
	EXECUTE FORMAT('ALTER TABLE %s RENAME TO __candles_time_diff_tmp', _candles_tmp); --possibly just use formatter -- might NOT be parallelizable 
	DROP TABLE IF EXISTS __candles_time_diff_results;
	CREATE TEMPORARY TABLE __candles_time_diff_results 
	--ON COMMIT DROP
	AS (
		SELECT 
		c.row_index, 
		c.full_name, 
		c.the_date,
		c.open_price - LAG(c.open_price,_difference) OVER (PARTITION BY c.full_name ORDER BY c.the_date) AS open_difference,
		c.high_price - LAG(c.high_price,_difference) OVER (PARTITION BY c.full_name ORDER BY c.the_date) AS high_difference,
		c.low_price - LAG(c.low_price,_difference) OVER (PARTITION BY c.full_name ORDER BY c.the_date) AS low_difference,
		c.close_price - LAG(c.close_price,_difference) OVER (PARTITION BY c.full_name ORDER BY c.the_date) AS close_difference
		FROM __candles_time_diff_tmp c
	);
	EXECUTE FORMAT('ALTER TABLE __candles_time_diff_tmp RENAME TO %s', _candles_tmp);
	
	CREATE INDEX __candles_time_diff_results_row_index_idx ON __candles_time_diff_results USING btree(row_index);
	CREATE INDEX __candles_time_diff_results_full_name_idx ON __candles_time_diff_results USING btree(full_name);
	CREATE INDEX __candles_time_diff_results_the_date_idx ON __candles_time_diff_results USING btree(the_date);
	
	RETURN QUERY SELECT * FROM __candles_time_diff_results;
END
$$ LANGUAGE plpgsql; 

COMMENT ON FUNCTION trading.candles_time_diff(TEXT, INTEGER) IS 'From a set of candles, get their difference from the candles before them.';

--TEST
--DROP TABLE IF EXISTS candles_tmp CASCADE;
--SELECT * INTO candles_tmp FROM get_candles_from_instruments(ARRAY['EUR/JPY','USD/JPY'], '07 Mar 2022 12:30:00'::timestamp, 100, 240,120)
--SELECT * FROM candles_time_diff('candles_tmp');

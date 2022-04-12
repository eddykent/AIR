--function for taking in a set of values and returning their difference

DROP FUNCTION IF EXISTS trading.values_time_diff(_values_tmp TEXT, _difference INT );
CREATE OR REPLACE FUNCTION trading.values_time_diff(_values_tmp TEXT, _difference INT DEFAULT 1)
RETURNS TABLE (
	row_index INTEGER, 
	full_name TEXT,
	the_date TIMESTAMP,
	difference DOUBLE PRECISION
)
AS $$
BEGIN 
	DROP TABLE IF EXISTS __values_time_diff_tmp;
	EXECUTE FORMAT('ALTER TABLE %s RENAME TO __values_time_diff_tmp', _values_tmp); --possibly just use formatter -- might NOT be parallelizable 
	DROP TABLE IF EXISTS __values_time_diff_results;
	CREATE TEMPORARY TABLE __values_time_diff_results 
	ON COMMIT DROP
	AS (
		SELECT 
		v.row_index, 
		v.full_name, 
		v.the_date,
		v.value - LAG(v.value,_difference) OVER (PARTITION BY v.full_name ORDER BY v.the_date) AS difference
		FROM __values_time_diff_tmp v
	);
	EXECUTE FORMAT('ALTER TABLE __values_time_diff_tmp RENAME TO %s', _values_tmp);
	
	CREATE INDEX __values_time_diff_row_index_idx ON __values_time_diff_results USING btree(row_index);
	CREATE INDEX __values_time_diff_results_full_name_idx ON __values_time_diff_results USING btree(full_name);
	CREATE INDEX __values_time_diff_results_the_date_idx ON __values_time_diff_results USING btree(the_date);	

	RETURN QUERY SELECT * FROM __values_time_diff_results;

	
END
$$ LANGUAGE plpgsql; 

COMMENT ON FUNCTION trading.values_time_diff(TEXT, INTEGER) IS 'From a set of values, get their difference from the candles before them.';

--TEST
--DROP TABLE IF EXISTS values_tmp CASCADE;
--SELECT row_index, full_name, the_date, close_price AS value INTO values_tmp FROM get_candles_from_instruments(ARRAY['EUR/JPY','USD/JPY'], '07 Mar 2022 12:30:00'::timestamp, 100, 240,120)
--SELECT * FROM values_time_diff('values_tmp');

--function for taking in a set of valus and returning their rate of change
DROP FUNCTION IF EXISTS trading.values_rate_of_change(_values_tmp TEXT, _difference INT );
CREATE OR REPLACE FUNCTION trading.values_rate_of_change(_values_tmp TEXT, _difference INT DEFAULT 1)
RETURNS TABLE (
	row_index INTEGER, 
	full_name TEXT,
	the_date TIMESTAMP,
	rate DOUBLE PRECISION
)
AS $$
BEGIN 
	DROP TABLE IF EXISTS __values_rate_of_change_tmp CASCADE;
	EXECUTE FORMAT('ALTER TABLE %s RENAME TO __values_rate_of_change_tmp', _values_tmp); --possibly just use formatter -- might NOT be parallelizable 
	DROP TABLE IF EXISTS __values_rate_of_change_results;
	CREATE TEMPORARY TABLE __values_rate_of_change_results 
	ON COMMIT DROP
	AS (
		WITH previous AS (
			SELECT 
			v.row_index, 
			v.full_name, 
			v.the_date,
			v.value,
			LAG(v.value,_difference) OVER (PARTITION BY v.full_name ORDER BY v.the_date) AS value_prev
			FROM __values_rate_of_change_tmp v
		)
		SELECT p.row_index,
		p.full_name,
		p.the_date,
		(p.value - p.value_prev) / p.value_prev AS rate
		FROM previous p		
	);
	EXECUTE FORMAT('ALTER TABLE __values_rate_of_change_tmp RENAME TO %s', _values_tmp);
	
	CREATE INDEX __values_rate_of_change_results_row_index_idx ON __values_rate_of_change_results USING btree(row_index);
	CREATE INDEX __values_rate_of_change_results_full_name_idx ON __values_rate_of_change_results USING btree(full_name);
	CREATE INDEX __values_rate_of_change_results_the_date_idx ON __values_rate_of_change_results USING btree(the_date);

	RETURN QUERY SELECT * FROM __values_rate_of_change_results;
END
$$ LANGUAGE plpgsql; 

COMMENT ON FUNCTION trading.values_rate_of_change(TEXT, INTEGER) IS 'From a set of values, get their rate of change (multiply by 100 to get percentage)';

--TEST
--DROP TABLE IF EXISTS values_tmp CASCADE;
--SELECT row_index, full_name, the_date, close_price AS value INTO values_tmp FROM get_candles_from_instruments(ARRAY['EUR/JPY','USD/JPY'], '07 Mar 2022 12:30:00'::timestamp, 100, 240,120)
--SELECT * FROM values_rate_of_change('values_tmp');

--function for taking in a set of values and returning a normalized version of  them bounded between 0 and 1
DROP FUNCTION IF EXISTS values_rolling_normalised(_values_tmp TEXT,  _period INTEGER);
CREATE OR REPLACE FUNCTION values_rolling_normalised(_values_tmp TEXT,  _period INTEGER)
RETURNS TABLE (
	row_index INTEGER, 
	full_name TEXT,
	the_date TIMESTAMP,
	value DOUBLE PRECISION
)
AS $$
BEGIN 
	DROP TABLE IF EXISTS __values_rolling_normalised_tmp;
	EXECUTE FORMAT('ALTER TABLE %s RENAME TO __values_rolling_normalised_tmp', _values_tmp); --possibly just use formatter -- might NOT be parallelizable 
	DROP TABLE IF EXISTS __values_rolling_normalised_results;
	CREATE TEMPORARY TABLE __values_rolling_normalised_results 
	ON COMMIT DROP
	AS (
		WITH periods AS (
			SELECT 
			v.row_index, 
			v.full_name, 
			v.the_date,
			v.value,
			MIN(v.value) OVER w AS min_value, 
			MAX(v.value) OVER w AS max_value
			FROM __values_rolling_normalised_tmp v
			WINDOW w AS (PARTITION BY v.full_name ORDER BY v.the_date ASC ROWS BETWEEN (_period-1) PRECEDING AND CURRENT ROW)
		),
		normed_calculation AS (
			SELECT 
			p.row_index,
			p.full_name,
			p.the_date,
			CASE WHEN p.max_value = p.min_value THEN 0.5 ELSE (p.value - p.min_value) / (p.max_value - p.min_value) END AS value 
			FROM periods p  
		)
		SELECT * FROM normed_calculation
	);
	EXECUTE FORMAT('ALTER TABLE __values_rolling_normalised_tmp RENAME TO %s', _values_tmp);
	
	CREATE INDEX __values_macd_row_index_idx ON __values_rolling_normalised_results USING btree(row_index);
	CREATE INDEX __values_macd_results_full_name_idx ON __values_rolling_normalised_results USING btree(full_name);
	CREATE INDEX __values_macd_results_the_date_idx ON __values_rolling_normalised_results USING btree(the_date);	

	RETURN QUERY SELECT * FROM __values_rolling_normalised_results;

	
END
$$ LANGUAGE plpgsql; 

COMMENT ON FUNCTION values_rolling_normalised(TEXT, INTEGER) IS 'From a set of values, return their normed value.';

--TEST
--DROP TABLE IF EXISTS values_tmp CASCADE;
--SELECT row_index, full_name, the_date, close_price AS value INTO values_tmp FROM get_candles_from_instruments(ARRAY['EUR/JPY','USD/JPY'], '07 Mar 2022 12:30:00'::timestamp, 100, 240,120)
--SELECT * FROM values_rolling_normalised('values_tmp',5);

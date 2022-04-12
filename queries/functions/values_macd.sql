--function for taking in a set of values and returning their macd (moving averages convergence divergence)

DROP FUNCTION IF EXISTS trading.values_macd(_values_tmp TEXT,  _period INTEGER, _fast INTEGER, _slow INTEGER);
CREATE OR REPLACE FUNCTION trading.values_macd(_values_tmp TEXT,  _period INTEGER DEFAULT 9, _fast INTEGER DEFAULT 12, _slow INTEGER DEFAULT 26)
RETURNS TABLE (
	row_index INTEGER, 
	full_name TEXT,
	the_date TIMESTAMP,
	macd_line DOUBLE PRECISION,
	signal_line DOUBLE PRECISION
)
AS $$
BEGIN 
	DROP TABLE IF EXISTS __values_macd_tmp;
	EXECUTE FORMAT('ALTER TABLE %s RENAME TO __values_macd_tmp', _values_tmp); --possibly just use formatter -- might NOT be parallelizable 
	DROP TABLE IF EXISTS __values_macd_results;
	CREATE TEMPORARY TABLE __values_macd_results 
	ON COMMIT DROP
	AS (
		WITH mvs AS (
			SELECT 
			v.row_index, 
			v.full_name, 
			v.the_date,
			EMA(v.value, 1.0 / _slow::DOUBLE PRECISION) OVER w AS slow_value,
			EMA(v.value, 1.0 / _fast::DOUBLE PRECISION) OVER w AS fast_value
			FROM __values_macd_tmp v
			WINDOW w AS (PARTITION BY v.full_name ORDER BY v.the_date ASC)
		),
		macd_calculation AS (
			SELECT 
			m.row_index, 
			m.full_name, 
			m.the_date,
			m.fast_value - m.slow_value AS macd_line,
			EMA(m.fast_value - m.slow_value, 1.0 /  _period::DOUBLE PRECISION) OVER w AS signal_line
			FROM mvs m 
			WINDOW w AS (PARTITION BY m.full_name ORDER BY m.the_date ASC)
		)
		SELECT * FROM macd_calculation
	);
	EXECUTE FORMAT('ALTER TABLE __values_macd_tmp RENAME TO %s', _values_tmp);
	
	CREATE INDEX __values_macd_row_index_idx ON __values_macd_results USING btree(row_index);
	CREATE INDEX __values_macd_results_full_name_idx ON __values_macd_results USING btree(full_name);
	CREATE INDEX __values_macd_results_the_date_idx ON __values_macd_results USING btree(the_date);	

	RETURN QUERY SELECT * FROM __values_macd_results;

	
END
$$ LANGUAGE plpgsql; 

COMMENT ON FUNCTION trading.values_macd(TEXT, INTEGER, INTEGER, INTEGER) IS 'From a set of values, get the macd line and signal line.';

--TEST
--DROP TABLE IF EXISTS values_tmp CASCADE;
--SELECT row_index, full_name, the_date, close_price AS value INTO values_tmp FROM get_candles_from_instruments(ARRAY['EUR/JPY','USD/JPY'], '07 Mar 2022 12:30:00'::timestamp, 100, 240,120)
--SELECT * FROM values_macd('values_tmp');

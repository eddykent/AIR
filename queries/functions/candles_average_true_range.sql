--function for taking in a set of candles and returning their average true range
--DEPENDS ON EMA
DROP FUNCTION IF EXISTS trading.candles_average_true_range(_candles_tmp TEXT, _period INTEGER );
CREATE OR REPLACE FUNCTION trading.candles_average_true_range(_candles_tmp TEXT, _period INTEGER DEFAULT 14)
RETURNS TABLE (
	row_index INTEGER, 
	full_name TEXT,
	the_date TIMESTAMP,
	average_true_range DOUBLE PRECISION
)
AS $$
BEGIN 
	DROP TABLE IF EXISTS __candles_average_true_range_tmp;
	EXECUTE FORMAT('ALTER TABLE %s RENAME TO __candles_average_true_range_tmp', _candles_tmp); --possibly just use formatter -- might NOT be parallelizable 
	DROP TABLE IF EXISTS __candles_average_true_range_results;
	CREATE TEMPORARY TABLE __candles_average_true_range_results 
	ON COMMIT DROP
	AS (
		WITH true_ranges AS (
			SELECT tc.row_index,
			tc.full_name,
			tc.the_date,
			GREATEST(tc.high_price - tc.low_price, ABS(tc.high_price - LAG(tc.close_price) OVER w),ABS(tc.low_price - LAG(tc.close_price) OVER w)) AS true_range
			FROM __candles_average_true_range_tmp tc
			WINDOW w AS (PARTITION BY tc.full_name ORDER BY tc.the_date ASC)
		), 
		average_true_ranges AS (
			SELECT
			tr.row_index,
			tr.full_name,
			tr.the_date,
			EMA(tr.true_range,1.0 / _period::DOUBLE PRECISION) OVER w AS average_true_range
			FROM true_ranges tr
			WINDOW w AS (PARTITION BY tr.full_name ORDER BY tr.the_date ASC)
		)
		SELECT * FROM average_true_ranges
	);
	EXECUTE FORMAT('ALTER TABLE __candles_average_true_range_tmp RENAME TO %s', _candles_tmp);
	
	CREATE INDEX __candles_average_true_range_results_row_index_idx ON __candles_average_true_range_results USING btree(row_index);
	CREATE INDEX __candles_average_true_range_results_full_name_idx ON __candles_average_true_range_results USING btree(full_name);
	CREATE INDEX __candles_average_true_range_results_the_date_idx ON __candles_average_true_range_results USING btree(the_date);
	
	RETURN QUERY SELECT * FROM __candles_average_true_range_results;
END
$$ LANGUAGE plpgsql; 

COMMENT ON FUNCTION trading.candles_average_true_range(TEXT, INTEGER) IS 'From a set of candles and a period, get their average true range';

--TEST
--DROP TABLE IF EXISTS candles_tmp CASCADE;
--SELECT * INTO candles_tmp FROM get_candles_from_instruments(ARRAY['EUR/GBP','USD/JPY'], '07 Mar 2022 12:30:00'::timestamp, 100, 240,120)
--SELECT * FROM candles_average_true_range('candles_tmp');

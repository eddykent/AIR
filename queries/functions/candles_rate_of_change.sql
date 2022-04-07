--function for taking in a set of candles and returning their difference, appending nulls?

DROP FUNCTION IF EXISTS candles_rate_of_change(_candles_tmp TEXT, _difference INT );
CREATE OR REPLACE FUNCTION candles_rate_of_change(_candles_tmp TEXT, _difference INT DEFAULT 1)
RETURNS TABLE (
	row_index INTEGER, 
	full_name TEXT,
	the_date TIMESTAMP,
	open_rate DOUBLE PRECISION, 
	high_rate DOUBLE PRECISION,
	low_rate DOUBLE PRECISION,
	close_rate DOUBLE PRECISION
)
AS $$
BEGIN 
	EXECUTE FORMAT('ALTER TABLE %s RENAME TO __candles_tmp', _candles_tmp); --possibly just use formatter -- might NOT be parallelizable 
	DROP TABLE IF EXISTS _candles_rate_of_change_results;
	CREATE TEMPORARY TABLE _candles_rate_of_change_results 
	ON COMMIT DROP
	AS (
		WITH previous AS (
			SELECT 
			c.row_index, 
			c.full_name, 
			c.the_date,
			c.open_price,
			c.high_price,
			c.low_price,
			c.close_price,
			LAG(c.open_price,_difference) OVER (PARTITION BY c.full_name ORDER BY c.the_date) AS open_prev,
			LAG(c.high_price,_difference) OVER (PARTITION BY c.full_name ORDER BY c.the_date) AS high_prev,
			LAG(c.low_price,_difference) OVER (PARTITION BY c.full_name ORDER BY c.the_date) AS low_prev,
			LAG(c.close_price,_difference) OVER (PARTITION BY c.full_name ORDER BY c.the_date) AS close_prev
			FROM __candles_tmp c
		)
		SELECT p.row_index,
		p.full_name,
		p.the_date,
		(p.open_price - p.open_prev) / p.open_prev AS open_rate,
		(p.high_price - p.high_prev) / p.high_prev AS high_rate,
		(p.low_price - p.low_prev) / p.low_prev AS low_rate,
		(p.close_price - p.close_prev) / p.close_prev AS close_rate
		FROM previous p		
	);
	EXECUTE FORMAT('ALTER TABLE __candles_tmp RENAME TO %s', _candles_tmp);
	RETURN QUERY SELECT * FROM _candles_rate_of_change_results;
END
$$ LANGUAGE plpgsql; 

COMMENT ON FUNCTION candles_rate_of_change(TEXT, INTEGER) IS 'From a set of candles, get their rate of change (multiply by 100 to get percentage)';

--TEST
--DROP TABLE IF EXISTS candles_tmp CASCADE;
--SELECT * INTO candles_tmp FROM get_candles_from_instruments(ARRAY['EUR/JPY','USD/JPY'], '07 Mar 2022 12:30:00'::timestamp, 100, 240,120)
--SELECT * FROM candles_rate_of_change('candles_tmp');

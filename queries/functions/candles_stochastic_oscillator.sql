--function for taking in a set of candles and returning stochastic oscillator values
--DEPENDS ON EMA
DROP FUNCTION IF EXISTS candles_stochastic_oscillator(_candles_tmp TEXT, _period INTEGER, _fast_d INTEGER, _slow_d INTEGER);
CREATE OR REPLACE FUNCTION candles_stochastic_oscillator(_candles_tmp TEXT, _period INTEGER DEFAULT 14, _fast_d INTEGER DEFAULT 3, _slow_d INTEGER DEFAULT 3)
RETURNS TABLE (
	row_index INTEGER, 
	full_name TEXT,
	the_date TIMESTAMP,
	k_value DOUBLE PRECISION,
	d_value DOUBLE PRECISION,
	slow_d_value DOUBLE PRECISION
)
AS $$
BEGIN 
	DROP TABLE IF EXISTS __candles_stochastic_oscillator_tmp;
	EXECUTE FORMAT('ALTER TABLE %s RENAME TO __candles_stochastic_oscillator_tmp', _candles_tmp); --possibly just use formatter -- might NOT be parallelizable 
	DROP TABLE IF EXISTS __candles_stochastic_oscillator_results;
	CREATE TEMPORARY TABLE __candles_stochastic_oscillator_results 
	ON COMMIT DROP
	AS (
		WITH periods AS (
			SELECT c.row_index,
			c.full_name,
			c.the_date,
			MAX(c.high_price) OVER w AS high_price,
			MIN(c.low_price) OVER w AS low_price,
			c.close_price
			FROM __candles_stochastic_oscillator_tmp c
			WINDOW w AS (PARTITION BY c.full_name ORDER BY c.the_date ASC ROWS BETWEEN (_period-1) PRECEDING AND CURRENT ROW)
		), 
		calc_k AS (
			SELECT
			p.row_index,
			p.full_name,
			p.the_date,
			(p.close_price - p.low_price) / (p.high_price - p.low_price) AS k_value
			FROM periods p
		),
		calc_d AS (
			SELECT
			k.row_index,
			k.full_name,
			k.the_date,
			k.k_value,
			AVG(k.k_value) OVER w AS d_value
			FROM calc_k k
			WINDOW w AS (PARTITION BY k.full_name ORDER BY k.the_date ASC ROWS BETWEEN (_fast_d::INT-1) PRECEDING AND CURRENT ROW)
		),
		calc_slow_d AS (
			SELECT
			d.row_index,
			d.full_name,
			d.the_date,
			d.k_value,
			d.d_value,
			AVG(d.d_value) OVER w AS slow_d_value
			FROM calc_d d
			WINDOW w AS (PARTITION BY d.full_name ORDER BY d.the_date ASC ROWS BETWEEN (_slow_d::INT-1) PRECEDING AND CURRENT ROW)
		)
		SELECT * FROM calc_slow_d
	);
	EXECUTE FORMAT('ALTER TABLE __candles_stochastic_oscillator_tmp RENAME TO %s', _candles_tmp);
	
	CREATE INDEX __candles_stochastic_oscillator_results_row_index_idx ON __candles_stochastic_oscillator_results USING btree(row_index);
	CREATE INDEX __candles_stochastic_oscillator_results_full_name_idx ON __candles_stochastic_oscillator_results USING btree(full_name);
	CREATE INDEX __candles_stochastic_oscillator_results_the_date_idx ON __candles_stochastic_oscillator_results USING btree(the_date);
	
	RETURN QUERY SELECT * FROM __candles_stochastic_oscillator_results;
END
$$ LANGUAGE plpgsql; 

COMMENT ON FUNCTION candles_stochastic_oscillator(TEXT, INTEGER, INTEGER, INTEGER) IS 'From a set of candles and a period, get the stochastic oscillator values';

--TEST
--DROP TABLE IF EXISTS candles_tmp CASCADE;
--SELECT * INTO candles_tmp FROM get_candles_from_instruments(ARRAY['EUR/GBP','USD/JPY'], '07 Mar 2022 12:30:00'::timestamp, 100, 240,120)
--SELECT * FROM candles_stochastic_oscillator('candles_tmp');

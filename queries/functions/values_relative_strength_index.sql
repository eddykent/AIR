--function for calculating RSI values from the close price a given set of candles. 
--DEPENDS: values_rate_of_change, EMA 

DROP FUNCTION IF EXISTS values_relative_strength_index(_values_tmp TEXT, _period INT, _difference INT);
CREATE OR REPLACE FUNCTION values_relative_strength_index(_values_tmp TEXT, _period INT DEFAULT 14, _difference INT DEFAULT 1)
RETURNS TABLE (
	row_index INTEGER, 
	full_name TEXT,
	the_date TIMESTAMP,
	rsi DOUBLE PRECISION
)
AS $$
BEGIN 
	
	DROP TABLE IF EXISTS __rsi_tmp CASCADE; --remember __values_tmp is already taken in nested function
	EXECUTE FORMAT('ALTER TABLE %s RENAME TO __rsi_tmp', _values_tmp); --possibly just use formatter -- might NOT be parallelizable 
	
	DROP TABLE IF EXISTS _values_relative_strength_index_results CASCADE;
	CREATE TEMPORARY TABLE _values_relative_strength_index_results
	ON COMMIT DROP 
	AS (
		WITH up_down_moves AS (
			SELECT r.row_index,
			r.full_name,
			r.the_date,
			SUM(GREATEST(r.rate,0)) OVER w AS up_moves,
			SUM(ABS(LEAST(r.rate,0))) OVER w AS down_moves,
			GREATEST(r.rate,0) AS up_move,
			ABS(LEAST(r.rate,0)) AS down_move,
			ROW_NUMBER() OVER (PARTITION BY r.full_name ORDER BY r.the_date ASC) AS time_index
			FROM values_rate_of_change('__rsi_tmp',_difference) AS r 
			WINDOW w AS (PARTITION BY r.full_name ORDER BY r.the_date ASC ROWS BETWEEN (_period - 1) PRECEDING AND CURRENT ROW)	
		),
		avg_moves AS (
			SELECT u.row_index,
			u.full_name,
			u.the_date, 
			u.up_moves,
			u.down_moves,
			EMA(CASE WHEN u.time_index < _period THEN u.up_moves ELSE u.up_move END, CASE WHEN u.time_index < _period THEN 1.0 ELSE 1.0 / _period::DOUBLE PRECISION END ) OVER w AS avg_moves_up,
			EMA(CASE WHEN u.time_index < _period THEN u.down_moves ELSE u.down_move END, CASE WHEN u.time_index < _period THEN 1.0 ELSE 1.0 / _period::DOUBLE PRECISION END ) OVER w AS avg_moves_down 
			FROM up_down_moves u
			WINDOW w AS (PARTITION BY u.full_name ORDER BY u.the_date)	
		),
		rs_calc AS ( 
			SELECT a.row_index,
			a.full_name,
			a.the_date,
			CASE WHEN a.avg_moves_down = 0 THEN 1.0 ELSE 1.0 - (1.0 / (1.0 + (a.avg_moves_up / a.avg_moves_down)) ) END  AS rsi
			--CASE WHEN down_moves = 0 THEN 1.0 ELSE 1.0 - (1.0 / (1.0 + (up_moves / down_moves)) ) END  AS rsi2, --WRONG
			FROM avg_moves a
		)
		SELECT * FROM rs_calc 
	);
	
	EXECUTE FORMAT('ALTER TABLE __rsi_tmp RENAME TO %s', _values_tmp);

	CREATE INDEX _values_relative_strength_index_results_row_index_idx ON _values_relative_strength_index_results USING btree(row_index);
	CREATE INDEX _values_relative_strength_index_results_full_name_idx ON _values_relative_strength_index_results USING btree(full_name);
	CREATE INDEX _values_relative_strength_index_results_the_date_idx ON _values_relative_strength_index_results USING btree(the_date);

	RETURN QUERY SELECT * FROM _values_relative_strength_index_results;
END
$$ LANGUAGE plpgsql; 

COMMENT ON FUNCTION values_relative_strength_index(TEXT, INTEGER, INTEGER) IS 'From a set of values, get their relative strength index';

--TEST
--DROP TABLE IF EXISTS values_tmp CASCADE;
--SELECT row_index, full_name, the_date, close_price AS value INTO values_tmp FROM get_candles_from_instruments(ARRAY['EUR/JPY','USD/JPY'], '07 Mar 2022 12:30:00'::timestamp, 100, 240,120)
--SELECT * FROM values_relative_strength_index('values_tmp');


--function for calculating RSI values from the close price a given set of candles. 
--DEPENDS: candles_rate_of_change, EMA 


DROP FUNCTION IF EXISTS value_relative_strength_index(_values_tmp TEXT, _period INT,  );
CREATE OR REPLACE FUNCTION values_relative_strength_index(_values_tmp TEXT, _period INT DEFAULT 14)
RETURNS TABLE (
	row_index INTEGER, 
	full_name TEXT,
	the_date TIMESTAMP,
	rsi DOUBLE PRECISION
)
AS $$
BEGIN 
	
	DROP TABLE IF EXISTS __rsi_tmp; --remember __values_tmp is already taken in nested function
	EXECUTE FORMAT('ALTER TABLE %s RENAME TO __rsi_tmp', _values_tmp); --possibly just use formatter -- might NOT be parallelizable 
	
	WITH up_down_moves AS (
		SELECT from_currency, to_currency,
		SUM(GREATEST(rate_of_change,0)) OVER w AS up_moves,
		SUM(ABS(LEAST(rate_of_change,0))) OVER w AS down_moves,
		GREATEST(rate_of_change,0) AS up_move,
		ABS(LEAST(rate_of_change,0)) AS down_move,
		the_date,
		time_index
		FROM tmp_all_rates_of_change taroc 
		WINDOW w AS (PARTITION BY from_currency, to_currency ORDER BY the_date ASC ROWS BETWEEN (14-1) PRECEDING AND CURRENT ROW)	
	),
	avg_moves AS (
		SELECT from_currency, to_currency,
		up_moves,
		down_moves,
		EMA(CASE WHEN time_index < 14 THEN up_moves ELSE up_move END, CASE WHEN time_index < 14 THEN 1.0 ELSE 1.0 / 14.0 END ) OVER w AS avg_moves_up,
		EMA(CASE WHEN time_index < 14 THEN down_moves ELSE down_move END, CASE WHEN time_index < 14 THEN 1.0 ELSE 1.0 / 14.0 END ) OVER w AS avg_moves_down,
		the_date,
		time_index
		FROM up_down_moves 
		WINDOW w AS (PARTITION BY from_currency, to_currency ORDER BY the_date)	
	),
	rs_calc AS ( 
		SELECT from_currency, to_currency, 
		CASE WHEN avg_moves_down = 0 THEN 1.0 ELSE 1.0 - (1.0 / (1.0 + (avg_moves_up / avg_moves_down)) ) END  AS rsi,
		--CASE WHEN down_moves = 0 THEN 1.0 ELSE 1.0 - (1.0 / (1.0 + (up_moves / down_moves)) ) END  AS rsi2, --WRONG
		the_date,
		time_index
		FROM avg_moves
	)
	SELECT * FROM rs_calc 
	
	EXECUTE FORMAT('ALTER TABLE __rsi_tmp RENAME TO %s', _values_tmp);
	RETURN QUERY SELECT * FROM _return_results;
END
$$ LANGUAGE plpgsql; 

COMMENT ON FUNCTION values_relative_strength_index(TEXT, INTEGER) IS 'From a set of values, get their relative strength index';



WITH up_down_moves AS (
	SELECT from_currency, to_currency,
	SUM(GREATEST(rate_of_change,0)) OVER w AS up_moves,
	SUM(ABS(LEAST(rate_of_change,0))) OVER w AS down_moves,
	GREATEST(rate_of_change,0) AS up_move,
	ABS(LEAST(rate_of_change,0)) AS down_move,
	the_date,
	time_index
	FROM tmp_all_rates_of_change taroc 
	WINDOW w AS (PARTITION BY from_currency, to_currency ORDER BY the_date ASC ROWS BETWEEN (14-1) PRECEDING AND CURRENT ROW)	
),
avg_moves AS (
	SELECT from_currency, to_currency,
	up_moves,
	down_moves,
	EMA(CASE WHEN time_index < 14 THEN up_moves ELSE up_move END, CASE WHEN time_index < 14 THEN 1.0 ELSE 1.0 / 14.0 END ) OVER w AS avg_moves_up,
	EMA(CASE WHEN time_index < 14 THEN down_moves ELSE down_move END, CASE WHEN time_index < 14 THEN 1.0 ELSE 1.0 / 14.0 END ) OVER w AS avg_moves_down,
	the_date,
	time_index
	FROM up_down_moves 
	WINDOW w AS (PARTITION BY from_currency, to_currency ORDER BY the_date)	
),
rs_calc AS ( 
	SELECT from_currency, to_currency, 
	CASE WHEN avg_moves_down = 0 THEN 1.0 ELSE 1.0 - (1.0 / (1.0 + (avg_moves_up / avg_moves_down)) ) END  AS rsi,
	--CASE WHEN down_moves = 0 THEN 1.0 ELSE 1.0 - (1.0 / (1.0 + (up_moves / down_moves)) ) END  AS rsi2, --WRONG
	the_date,
	time_index
	FROM avg_moves
)
SELECT * FROM rs_calc 
WHERE from_currency = 'EUR' AND to_currency = 'USD'
ORDER BY the_date ASC


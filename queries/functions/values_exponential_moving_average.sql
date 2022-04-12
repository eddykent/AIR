--function for taking in a set of forex values, combining them to return a strength value of each currency
--DEPENDS ON EMA
DROP FUNCTION IF EXISTS trading.values_exponential_moving_average(_values_tmp TEXT, _period INTEGER);
CREATE OR REPLACE FUNCTION trading.values_exponential_moving_average(_values_tmp TEXT, _period INTEGER)
RETURNS TABLE (
	row_index INTEGER, 
	full_name TEXT,
	the_date TIMESTAMP,
	ema_value DOUBLE PRECISION
)
AS $$
BEGIN 
	DROP TABLE IF EXISTS __values_exponential_moving_average_tmp;
	EXECUTE FORMAT('ALTER TABLE %s RENAME TO __values_exponential_moving_average_tmp', _values_tmp); --possibly just use formatter -- might NOT be parallelizable 
	DROP TABLE IF EXISTS __values_exponential_moving_average_results;
	CREATE TEMPORARY TABLE __values_exponential_moving_average_results 
	ON COMMIT DROP
	AS (
		SELECT 
		vsm.row_index, 
		vsm.full_name,
		vsm.the_date, 
		EMA(vsm.value,1.0 / _period::DOUBLE PRECISION) OVER w  AS ema_value
		FROM __values_exponential_moving_average_tmp vsm
		WINDOW w AS (PARTITION BY vsm.full_name ORDER BY vsm.the_date ASC)
	);
	EXECUTE FORMAT('ALTER TABLE __values_exponential_moving_average_tmp RENAME TO %s', _values_tmp);
	
	CREATE INDEX __values_exponential_moving_average_results_row_index_idx ON __values_exponential_moving_average_results USING btree(row_index);
	CREATE INDEX __values_exponential_moving_average_results_full_name_idx ON __values_exponential_moving_average_results USING btree(full_name);
	CREATE INDEX __values_exponential_moving_average_results_the_date_idx ON __values_exponential_moving_average_results USING btree(the_date);
	
	RETURN QUERY SELECT * FROM __values_exponential_moving_average_results;
END
$$ LANGUAGE plpgsql; 

COMMENT ON FUNCTION trading.values_exponential_moving_average(TEXT,INTEGER) IS 'Get the exponential moving average per instrument based on _period';

--TEST
--DROP TABLE IF EXISTS candles_tmp CASCADE;
--DROP TABLE IF EXISTS close_prices_tmp CASCADE; 
--SELECT * INTO candles_tmp FROM get_candles_from_currencies(ARRAY['EUR','USD','JPY','AUD','NZD','CAD','CHF','GBP'], '07 Mar 2022 12:30:00'::timestamp, 100, 15)
--SELECT row_index, full_name, the_date, close_price AS value INTO close_prices_tmp FROM candles_close_price('candles_tmp')
--SELECT * FROM values_exponential_moving_average('close_prices_tmp',2)

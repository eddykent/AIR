--function for taking in a set of forex values, combining them to return a strength value of each currency
--DEPENDS ON EMA
DROP FUNCTION IF EXISTS values_instrument_ranking(_values_tmp TEXT);
CREATE OR REPLACE FUNCTION values_instrument_ranking(_values_tmp TEXT)
RETURNS TABLE (
	row_index INTEGER, 
	full_name TEXT,
	the_date TIMESTAMP,
	ranking DOUBLE PRECISION
)
AS $$
BEGIN 
	DROP TABLE IF EXISTS __values_instrument_ranking_tmp;
	EXECUTE FORMAT('ALTER TABLE %s RENAME TO __values_instrument_ranking_tmp', _values_tmp); --possibly just use formatter -- might NOT be parallelizable 
	DROP TABLE IF EXISTS __values_instrument_ranking_results;
	CREATE TEMPORARY TABLE __values_instrument_ranking_results 
	ON COMMIT DROP
	AS (
		SELECT 
		vir.row_index, 
		vir.full_name,
		vir.the_date, 
		ROW_NUMBER() OVER (PARTITION BY vir.the_date ORDER BY vir.value DESC) AS ranking
		FROM __values_instrument_ranking_tmp vir
	);
	EXECUTE FORMAT('ALTER TABLE __values_instrument_ranking_tmp RENAME TO %s', _values_tmp);
	
	CREATE INDEX __values_instrument_ranking_results_row_index_idx ON __values_instrument_ranking_results USING btree(row_index);
	CREATE INDEX __values_instrument_ranking_results_full_name_idx ON __values_instrument_ranking_results USING btree(full_name);
	CREATE INDEX __values_instrument_ranking_results_the_date_idx ON __values_instrument_ranking_results USING btree(the_date);
	
	RETURN QUERY SELECT * FROM __values_instrument_ranking_results;
END
$$ LANGUAGE plpgsql; 

COMMENT ON FUNCTION values_instrument_ranking(TEXT) IS 'For every timestep, rank the instruments by their value';

--TEST
--DROP TABLE IF EXISTS candles_tmp CASCADE;
--DROP TABLE IF EXISTS close_prices_tmp CASCADE; 
--DROP TABLE IF EXISTS rsi_tmp CASCADE; 
--DROP TABLE IF EXISTS currency_strengths_tmp CASCADE;
--DROP TABLE IF EXISTS simple_moving_averages_tmp CASCADE;
--SELECT * INTO candles_tmp FROM get_candles_from_currencies(ARRAY['EUR','USD','JPY','AUD','NZD','CAD','CHF','GBP'], '07 Mar 2022 12:30:00'::timestamp, 100, 15)
--SELECT row_index, full_name, the_date, close_price AS value INTO close_prices_tmp FROM candles_close_price('candles_tmp')
--SELECT row_index, full_name, the_date, rsi AS value INTO rsi_tmp FROM values_relative_strength_index('close_prices_tmp', 14, 1) 
--SELECT row_index, currency AS full_name, the_date, currency_strength AS value INTO currency_strengths_tmp FROM values_currency_strength('rsi_tmp');
--SELECT row_index, full_name, the_date, value INTO simple_moving_averages_tmp FROM values_simple_moving_average('currency_strengths_tmp',3)
--SELECT * FROM values_instrument_ranking('simple_moving_averages_tmp')

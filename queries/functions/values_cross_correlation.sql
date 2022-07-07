--function for taking in a set of different timeseries and correlating them to eachother - returning all correlation values for each timestepr 
DROP FUNCTION IF EXISTS trading.values_cross_correlation(_values_tmp TEXT, _correlation_length INT);
CREATE OR REPLACE FUNCTION trading.values_cross_correlation(_values_tmp TEXT, _correlation_length INT DEFAULT 30)
RETURNS TABLE (
	row_index INTEGER,
	full_name1 TEXT,
	full_name2 TEXT,
	the_date TIMESTAMP,
	correlation DOUBLE PRECISION
)
AS $$
BEGIN 
	DROP TABLE IF EXISTS __values_cross_correlation_tmp;
	EXECUTE FORMAT('ALTER TABLE %s RENAME TO __values_cross_correlation_tmp', _values_tmp); --possibly just use formatter -- might NOT be parallelizable 
	DROP TABLE IF EXISTS __values_cross_correlation_results;
	CREATE TEMPORARY TABLE __values_cross_correlation_results 
	ON COMMIT DROP
	AS (
		WITH the_values AS (
			SELECT 
			vac.row_index, 
			vac.full_name,
			vac.the_date, 
			vac.value
			FROM __values_cross_correlation_tmp vac
		),
		values_paired AS (
			SELECT
			v1.the_date,
			v1.full_name AS full_name1, 
			v2.full_name AS full_name2, 
			v1.value AS value1, 
			v2.value AS value2
			FROM the_values v1 
			JOIN the_values v2 ON v1.the_date = v2.the_date
			WHERE v1.full_name < v2.full_name
			ORDER BY v1.the_date ASC
		),
		correlations AS (
			SELECT 
			v.the_date,
			v.full_name1,
			v.full_name2,
			v.value1,
			v.value2, 
			CORR(v.value1,v.value2) OVER w AS correlation --correlates timeseries. other stats add here
			FROM values_paired v
			WINDOW w AS (
				PARTITION BY v.full_name1, v.full_name2
				ORDER BY v.the_date ASC ROWS BETWEEN (_correlation_length-1) PRECEDING AND CURRENT ROW --correlate last 8 entries - works well with low correlations on 12 Jan 2022 AT 12pm.. so does high correl! 
			)
		)
		SELECT 
		(ROW_NUMBER() OVER (ORDER BY a.the_date, a.full_name1, a.full_name2) ) :: INTEGER AS row_index, 
		a.full_name1 ::TEXT ,
		a.full_name2 ::TEXT ,
		a.the_date ::TIMESTAMP, 
		a.correlation :: DOUBLE PRECISION
		FROM correlations a
	);
	EXECUTE FORMAT('ALTER TABLE __values_cross_correlation_tmp RENAME TO %s', _values_tmp);
	
	CREATE INDEX __values_cross_correlation_results_row_index_idx ON __values_cross_correlation_results USING btree(row_index);
	CREATE INDEX __values_cross_correlation_results_full_name1_idx ON __values_cross_correlation_results USING btree(full_name1);
	CREATE INDEX __values_cross_correlation_results_full_name2_idx ON __values_cross_correlation_results USING btree(full_name2);
	CREATE INDEX __values_cross_correlation_results_the_date_idx ON __values_cross_correlation_results USING btree(the_date);
	
	RETURN QUERY SELECT * FROM __values_cross_correlation_results;
END
$$ LANGUAGE plpgsql; 

COMMENT ON FUNCTION trading.values_cross_correlation(TEXT, INT) IS 
	'For every timestep, get the correlation between all pairwise timeseries (including lags) and then use high correlations to predict the next values. Also reports number of hits and variance for filter purposes';

--TEST
--DROP TABLE IF EXISTS candles_tmp CASCADE;
--DROP TABLE IF EXISTS close_prices_tmp CASCADE; 
--DROP TABLE IF EXISTS price_changes CASCADE; 
--DROP TABLE IF EXISTS cross_correlations CASCADE;
--SELECT * INTO candles_tmp FROM trading.get_candles_from_currencies(ARRAY['EUR','USD','JPY','AUD','NZD','CAD','CHF','GBP'], '07 Mar 2022 12:30:00'::timestamp, 10, 240);
--SELECT row_index, full_name, the_date, close_price AS value INTO close_prices_tmp FROM trading.candles_close_price('candles_tmp');
--SELECT row_index, full_name, the_date, rate AS value INTO price_changes FROM trading.values_rate_of_change('close_prices_tmp',1);
--SELECT * INTO correlations FROM trading.values_cross_correlation('price_changes');
--SELECT * FROM correlations












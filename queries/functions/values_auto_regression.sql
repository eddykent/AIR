--function for taking in a set of different timeseries and correlating them with themselves AND  eachother - returning all correlation values for each timestep
--tempted to black box all of this into its own auto-regression method... but lag-auto-crosses might be useful for projecting future values later 
DROP FUNCTION IF EXISTS trading.values_auto_regression(_values_tmp TEXT, _lags INT, _correlation_length INT, _correlation_thres DOUBLE PRECISION);
CREATE OR REPLACE FUNCTION trading.values_auto_regression(_values_tmp TEXT, _lags INT DEFAULT 12, _correlation_length INT DEFAULT 30,  _correlation_thres DOUBLE PRECISION DEFAULT 0.3)
RETURNS TABLE (
	row_index INTEGER,
	full_name TEXT,
	the_date TIMESTAMP,
	predicted_result DOUBLE PRECISION,
	result_variance DOUBLE PRECISION,
	n_result INTEGER	
)
AS $$
BEGIN 
	DROP TABLE IF EXISTS __values_auto_regression_tmp;
	EXECUTE FORMAT('ALTER TABLE %s RENAME TO __values_auto_regression_tmp', _values_tmp); --possibly just use formatter -- might NOT be parallelizable 
	DROP TABLE IF EXISTS __values_auto_regression_results;
	CREATE TEMPORARY TABLE __values_auto_regression_results 
	ON COMMIT DROP
	AS (
		WITH the_values AS (
			SELECT 
			vac.row_index, 
			vac.full_name,
			vac.the_date, 
			vac.value
			FROM __values_auto_regression_tmp vac
		),
		lagged_indexs AS (
			SELECT generate_series(1,_lags,1) AS lag_index
		),
		lagged_values AS (
			SELECT 
			v.full_name,
			v.the_date,
			v.value,
			li.lag_index,
			LAG(v.value,li.lag_index) OVER (PARTITION BY v.full_name,li.lag_index ORDER BY v.the_date) AS lag_value
			FROM the_values v, lagged_indexs li
		),
		values_paired AS (
			SELECT
			v1.the_date,
			v1.full_name AS full_name1, 
			v2.full_name AS full_name2, 
			v1.value AS value1, 
			v2.value AS value2,
			v2.lag_value AS lag_value2, 
			v2.lag_index AS lag_index
			FROM lagged_values v1 
			JOIN lagged_values v2 ON v1.the_date = v2.the_date 
			WHERE v1.lag_index = 1 
			ORDER BY v1.the_date ASC
		),
		correlations AS (
			SELECT 
			v.the_date,
			v.full_name1,
			v.full_name2,
			v.value1,
			v.value2, 
			v.lag_value2,
			CORR(v.value1,v.lag_value2) OVER w AS correlation, --correlates this with the previous value
			REGR_SLOPE(v.value1, v.lag_value2) OVER w AS slope,
			REGR_INTERCEPT(v.value1, v.lag_value2) OVER w AS intercept,  
			v.lag_index 
			FROM values_paired v
			WINDOW w AS (
				PARTITION BY v.full_name1, v.full_name2, v.lag_index
				ORDER BY v.the_date ASC ROWS BETWEEN (_correlation_length-1) PRECEDING AND CURRENT ROW --correlate last 8 entries - works well with low correlations on 12 Jan 2022 AT 12pm.. so does high correl! 
			)
		),
		value2_lead_lag AS ( --this IS confusing, but it needs TO have the current SET OF candles TO predict the NEXT one NOT the previous ones 
			SELECT c.*,
			CASE WHEN lag_index = 1 THEN value2 ELSE LAG(lag_value2,1) OVER w END AS value2_leadlag
			FROM correlations c
			WINDOW w AS (
				PARTITION BY full_name1, full_name2, lag_index
				ORDER BY c.the_date ASC
			)
		),
		collected_results AS (
			SELECT 
			v.the_date,
			v.full_name1 AS full_name,
			--lag_index, --intercept causes issues
			SUM(CASE WHEN ABS(v.correlation) > _correlation_thres THEN (v.slope*v.value2_leadlag) ELSE 0 END) AS next_result,
			SUM(CASE WHEN ABS(v.correlation) > _correlation_thres THEN (v.slope*v.value2_leadlag)*(v.slope*v.value2_leadlag) ELSE 0 END) AS next_result_squared,
			SUM(CASE WHEN ABS(v.correlation) > _correlation_thres THEN 1 ELSE 0 END) AS n_result
			FROM value2_lead_lag v
			GROUP BY v.the_date, v.full_name1--, lag_index--, candle2_lead_percent_change
		),
		average_results AS (
			SELECT 
			v.row_index,
			c.the_date, 
			c.full_name, 
			CASE WHEN c.n_result = 0 THEN NULL ELSE c.next_result / c.n_result END AS predicted_result,
			CASE WHEN c.n_result = 0 THEN 0 ELSE 
				(c.next_result_squared / c.n_result) - ((c.next_result / c.n_result)*(c.next_result / c.n_result))
			END AS result_variance,
			c.n_result 
			FROM collected_results c
			JOIN the_values v ON c.full_name = v.full_name AND c.the_date = v.the_date
		)
		SELECT 
		a.row_index :: INTEGER, 
		a.full_name ::TEXT ,
		a.the_date ::TIMESTAMP, 
		a.predicted_result :: DOUBLE PRECISION,
		a.result_variance :: DOUBLE PRECISION,
		a.n_result :: INTEGER
		FROM average_results a
	);
	EXECUTE FORMAT('ALTER TABLE __values_auto_regression_tmp RENAME TO %s', _values_tmp);
	
	CREATE INDEX __values_auto_regression_results_row_index_idx ON __values_auto_regression_results USING btree(row_index);
	CREATE INDEX __values_auto_regression_results_full_name_idx ON __values_auto_regression_results USING btree(full_name);
	CREATE INDEX __values_auto_regression_results_the_date_idx ON __values_auto_regression_results USING btree(the_date);
	
	RETURN QUERY SELECT * FROM __values_auto_regression_results;
END
$$ LANGUAGE plpgsql; 

COMMENT ON FUNCTION trading.values_auto_regression(TEXT, INT, INT, DOUBLE PRECISION) IS 
	'For every timestep, get the correlation between all pairwise timeseries (including lags) and then use high correlations to predict the next values. Also reports number of hits and variance for filter purposes';

--TEST
--DROP TABLE IF EXISTS candles_tmp CASCADE;
--DROP TABLE IF EXISTS close_prices_tmp CASCADE; 
--DROP TABLE IF EXISTS price_changes CASCADE; 
--DROP TABLE IF EXISTS auto_regressions CASCADE;
--SELECT * INTO candles_tmp FROM trading.get_candles_from_currencies(ARRAY['EUR','USD','JPY','AUD','NZD','CAD','CHF','GBP'], '07 Mar 2022 12:30:00'::timestamp, 10, 240);
--SELECT row_index, full_name, the_date, close_price AS value INTO close_prices_tmp FROM trading.candles_close_price('candles_tmp');
--SELECT row_index, full_name, the_date, rate AS value INTO price_changes FROM trading.values_rate_of_change('close_prices_tmp',1);
--SELECT * INTO auto_regressions FROM trading.values_auto_regression('price_changes');














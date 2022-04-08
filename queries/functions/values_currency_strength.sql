--function for taking in a set of forex values, combining them to return a strength value of each currency
--DEPENDS ON EMA
DROP FUNCTION IF EXISTS values_currency_strength(_values_tmp TEXT);
CREATE OR REPLACE FUNCTION values_currency_strength(_values_tmp TEXT)
RETURNS TABLE (
	row_index INTEGER, 
	currency TEXT,
	the_date TIMESTAMP,
	currency_strength DOUBLE PRECISION
)
AS $$
BEGIN 
	DROP TABLE IF EXISTS __values_currency_strength_tmp;
	EXECUTE FORMAT('ALTER TABLE %s RENAME TO __values_currency_strength_tmp', _values_tmp); --possibly just use formatter -- might NOT be parallelizable 
	DROP TABLE IF EXISTS __values_currency_strength_results;
	
	CREATE TEMPORARY TABLE __forex_candles_tmp
	ON COMMIT DROP 
	AS (
		WITH forex_candles AS (
			SELECT 
			--vcs.row_index, --this is now o longer used 
			vcs.full_name,
			vcs.the_date, 
			vcs.value,
			NULLIF(SPLIT_PART(vcs.full_name, '/', 1),'') AS from_currency,
			NULLIF(SPLIT_PART(vcs.full_name, '/', 2),'') AS to_currency
			FROM __values_currency_strength_tmp vcs
		)
		SELECT * FROM forex_candles
	);
	CREATE INDEX IF NOT EXISTS __forex_candles_tmp_full_name_idx ON __forex_candles_tmp USING btree(full_name);
	CREATE INDEX IF NOT EXISTS __forex_candles_tmp_the_date_idx ON __forex_candles_tmp USING btree(the_date);
	CREATE INDEX IF NOT EXISTS __forex_candles_tmp_from_currency_idx ON __forex_candles_tmp USING btree(from_currency);
	CREATE INDEX IF NOT EXISTS __forex_candles_tmp_to_currency_idx ON __forex_candles_tmp USING btree(to_currency);
	--index from currency & to_currency
	
	CREATE TEMPORARY TABLE __currencies_tmp
	ON COMMIT DROP 
	AS (
		WITH instruments AS (
			SELECT DISTINCT fx.full_name FROM __forex_candles_tmp fx
		),
		instruments_split AS (
			SELECT i.full_name,
			NULLIF(SPLIT_PART(i.full_name, '/', 1),'') AS from_currency,
			NULLIF(SPLIT_PART(i.full_name, '/', 2),'') AS to_currency
			FROM instruments i
		),
		currencies AS (
			SELECT i.from_currency AS currency FROM instruments_split i
			WHERE from_currency IS NOT NULL AND to_currency IS NOT NULL 
			UNION 
			SELECT i.to_currency AS currency FROM instruments_split i
			WHERE from_currency IS NOT NULL AND to_currency IS NOT NULL 
		)
		SELECT c.currency FROM currencies c
	);
	CREATE INDEX IF NOT EXISTS __currencies_tmp_currency_idx ON __currencies_tmp USING btree(currency); --necessary?

	CREATE TEMPORARY TABLE __dates_tmp 
	ON COMMIT DROP 
	AS (
		SELECT DISTINCT fx.the_date FROM __forex_candles_tmp fx
	);
	CREATE INDEX IF NOT EXISTS __dates_tmp_the_date_idx ON __dates_tmp USING btree(the_date); --necessary?
	
	CREATE TEMPORARY TABLE __friends_tmp 
	ON COMMIT DROP 
	AS (
		SELECT 
		c.currency,
		fx.the_date,
		fx.value
		FROM __currencies_tmp c 
		JOIN __forex_candles_tmp fx ON c.currency = fx.from_currency
	);
	CREATE INDEX IF NOT EXISTS __friends_tmp_currency_idx ON __friends_tmp USING btree(currency);
	CREATE INDEX IF NOT EXISTS __friends_tmp_the_date_idx ON __friends_tmp USING btree(the_date);
	
	CREATE TEMPORARY TABLE __enemies_tmp 
	ON COMMIT DROP 
	AS (
		SELECT 
		c.currency,
		fx.the_date,
		fx.value
		FROM __currencies_tmp c 
		JOIN __forex_candles_tmp fx ON c.currency = fx.to_currency
	);
	CREATE INDEX IF NOT EXISTS __enemies_tmp_currency_idx ON __enemies_tmp USING btree(currency);
	CREATE INDEX IF NOT EXISTS __enemies_tmp_the_date_idx ON __enemies_tmp USING btree(the_date);
	
	CREATE TEMPORARY TABLE __currency_the_date_tmp 
	ON COMMIT DROP 
	AS (
		SELECT
		(ROW_NUMBER() OVER (ORDER BY d.the_date,c.currency))::INTEGER AS row_index, --ALWAYS ORDER BY the_date THEN currency
		c.currency,
		d.the_date 
		FROM __currencies_tmp c, __dates_tmp d
	);
	CREATE INDEX IF NOT EXISTS __currency_the_date_tmp_row_index_idx ON __currency_the_date_tmp USING btree(row_index);
	CREATE INDEX IF NOT EXISTS __currency_the_date_tmp_currency_idx ON __currency_the_date_tmp USING btree(currency);
	CREATE INDEX IF NOT EXISTS __currency_the_date_tmp_the_date_idx ON __currency_the_date_tmp USING btree(the_date);
	
	CREATE TEMPORARY TABLE __values_currency_strength_results 
	ON COMMIT DROP
	AS (
		WITH all_values AS (
			SELECT cd.row_index, 
			f.value 
			FROM __currency_the_date_tmp cd 
			JOIN __friends_tmp f ON cd.currency = f.currency AND cd.the_date = f.the_date
			UNION 
			SELECT cd.row_index,
			-e.value AS value
			FROM __currency_the_date_tmp cd
			JOIN __enemies_tmp e ON cd.currency = e.currency AND cd.the_date = e.the_date
		),
		summed_values AS (
			SELECT a.row_index,
			SUM(a.value) AS value
			FROM all_values a
			GROUP BY a.row_index
		)
		SELECT cd.row_index,
		cd.currency,
		cd.the_date,
		sv.value AS currency_strength
		FROM __currency_the_date_tmp cd
		JOIN summed_values sv ON cd.row_index = sv.row_index
	);
	EXECUTE FORMAT('ALTER TABLE __values_currency_strength_tmp RENAME TO %s', _values_tmp);
	
	CREATE INDEX __values_currency_strength_results_row_index_idx ON __values_currency_strength_results USING btree(row_index);
	CREATE INDEX __values_currency_strength_results_currency_idx ON __values_currency_strength_results USING btree(currency);
	CREATE INDEX __values_currency_strength_results_the_date_idx ON __values_currency_strength_results USING btree(the_date);
	
	RETURN QUERY SELECT * FROM __values_currency_strength_results;
END
$$ LANGUAGE plpgsql; 

COMMENT ON FUNCTION values_currency_strength(TEXT) IS 'From a set of candles and a period, get the stochastic oscillator values';

--TEST
DROP TABLE IF EXISTS candles_tmp CASCADE;
DROP TABLE IF EXISTS values_tmp CASCADE;
DROP TABLE IF EXISTS rates_tmp CASCADE;
SELECT * INTO candles_tmp FROM get_candles_from_currencies(ARRAY['EUR','USD','JPY','AUD','NZD','CAD','CHF','GBP'], '07 Mar 2022 12:30:00'::timestamp, 100, 15);
SELECT row_index, full_name, the_date, typical_price AS value INTO values_tmp FROM candles_typical_price('candles_tmp');
SELECT row_index, full_name, the_date, rate AS value INTO rates_tmp FROM values_rate_of_change('values_tmp',1); 
SELECT * FROM values_currency_strength('rates_tmp')



--SELECT * FROM values_currency_strength('candles_tmp');

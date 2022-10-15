--function that will grab candles and condense them into actual candles of the correct size (quarts,halfs,hours,quads)
--quarts are 15m, halfs are 30m and quads are 4h candles 

--from currencies 
DROP FUNCTION IF EXISTS trading.get_candles_volumes_from_currencies(TEXT[], timestamp, int, int, int);
CREATE OR REPLACE FUNCTION trading.get_candles_volumes_from_currencies(_currencies TEXT[], _this_date TIMESTAMP, _days_back INTEGER, _chart_resolution INTEGER DEFAULT 15, _candle_offset INTEGER DEFAULT 0)
RETURNS TABLE (
	row_index INTEGER,	
	from_currency TEXT,
	to_currency TEXT,
	full_name TEXT, --INDEX 
	open_price DOUBLE PRECISION,
	high_price DOUBLE PRECISION,
	low_price DOUBLE PRECISION,
	close_price DOUBLE PRECISION,
	bid_volume DOUBLE PRECISION,
	ask_volume DOUBLE PRECISION,
	the_date TIMESTAMP, --INDEX 
	candle_index INTEGER, 
	time_index INTEGER
)
AS $$

--function that will grab candles and condense them into actual candles of the correct size (quarts,halfs,hours,quads)
--quarts are 15m, halfs are 30m and quads are 4h candles 

BEGIN
	DROP TABLE IF EXISTS __currencies_tmp; 
	CREATE TEMPORARY TABLE __currencies_tmp 
	ON COMMIT DROP 
	AS ( 
		SELECT UNNEST(_currencies) AS currency
	);
	
	DROP TABLE IF EXISTS _get_candles_volumes_from_currencies;

	--build candles of our chosen chart size 
	CREATE TEMPORARY TABLE _get_candles_volumes_from_currencies
	ON COMMIT DROP  
	AS (
		WITH selected_candles AS (
			SELECT evt.from_currency, evt.to_currency,
			evt.open_price,
			evt.high_price,
			evt.low_price,
			evt.close_price, 
			evt.the_date - (_candle_offset || ' mins')::INTERVAL AS the_date
			FROM exchange_value_tick evt
			WHERE evt.from_currency  = ANY(SELECT currency FROM __currencies_tmp) 
			AND evt.to_currency = ANY(SELECT currency FROM __currencies_tmp)
			AND evt.the_date < _this_date
			AND evt.the_date >= _this_date -  (_days_back || ' days')::INTERVAL --600 = 400 + 200 (days_back + normalisation_window)
		), 
		candle_indexs AS (
			SELECT sc.from_currency, 
			sc.to_currency,
			sc.open_price,
			sc.high_price,
			sc.low_price,
			sc.close_price,
			TO_TIMESTAMP (FLOOR(( EXTRACT ('EPOCH' FROM (sc.the_date )) ) / (60*15) ) * (60*15)) AT TIME ZONE 'UTC' AS the_date, --fix date
			(EXTRACT(MINUTE FROM sc.the_date) + 60 * EXTRACT (HOUR FROM sc.the_date))::INT / _chart_resolution AS candle_index,
			sc.the_date::DATE AS date_day
			FROM selected_candles sc
		),
		selected_volumes AS ( --need to select the volumes separately because the candle might be offset within the 15 mins (or chart res)
			SELECT evt.from_currency, evt.to_currency,
			evt.bid_volume,
			evt.ask_volume,
			evt.the_date - (_candle_offset || ' mins')::INTERVAL AS the_date
			FROM exchange_volume_tick evt
			WHERE evt.from_currency  = ANY(SELECT currency FROM __currencies_tmp) 
			AND evt.to_currency = ANY(SELECT currency FROM __currencies_tmp)
			AND evt.the_date < _this_date
			AND evt.the_date >= _this_date -  (_days_back || ' days')::INTERVAL --600 = 400 + 200 (days_back + normalisation_window)
		),
		volume_indexs AS (
			SELECT sv.from_currency, 
			sv.to_currency,
			sv.bid_volume,
			sv.ask_volume,
			TO_TIMESTAMP (FLOOR(( EXTRACT ('EPOCH' FROM (sv.the_date )) ) / (60*15) ) * (60*15)) AT TIME ZONE 'UTC' AS the_date, --fix date
			(EXTRACT(MINUTE FROM sv.the_date) + 60 * EXTRACT (HOUR FROM sv.the_date))::INT / _chart_resolution AS volume_index,
			sv.the_date::DATE AS date_day
			FROM selected_volumes sv
		),
		almost_candles AS (
			SELECT ci.from_currency, 
			ci.to_currency, 
			ci.candle_index,
			COUNT(1) AS n,
			ARRAY_AGG(ci.open_price ORDER BY ci.the_date) AS open_prices, 
			MAX(ci.high_price) AS high_price,
			MIN(ci.low_price) AS low_price,
			ARRAY_AGG(ci.close_price ORDER BY ci.the_date) AS close_prices,
			SUM(vi.bid_volume) AS bid_volume,
			SUM(vi.ask_volume) AS ask_volume,
			LEAST(MIN(ci.the_date),MIN(vi.the_date)) AS the_date
			FROM candle_indexs ci
			JOIN volume_indexs vi 
			ON ci.from_currency = vi.from_currency AND ci.to_currency = vi.to_currency 
			AND ci.candle_index = vi.volume_index AND ci.date_day = vi.date_day
			GROUP BY ci.from_currency, ci.to_currency, ci.candle_index, ci.date_day --, vi.from_currency, vi.to_currency, vi.volume_index, vi.date_day  --yikes!
		),
		time_indexed_candles AS (
			SELECT 
			(ROW_NUMBER() OVER ())::INTEGER AS row_index,
			c.from_currency,
			c.to_currency,
			c.from_currency || '/' || c.to_currency AS full_name,
			c.open_prices[1] AS open_price,
			c.high_price,
			c.low_price,
			c.close_prices[c.n] AS close_price,
			c.bid_volume,
			c.ask_volume,
			c.the_date + (_candle_offset || ' mins')::INTERVAL AS the_date,
			c.candle_index,
			(ROW_NUMBER() OVER (PARTITION BY c.from_currency, c.to_currency ORDER BY c.the_date))::INTEGER AS time_index-- 
			--t.time_index 
			FROM almost_candles c 
			--JOIN time_indexs t ON c.the_date = t.the_date
		)
		SELECT * FROM time_indexed_candles
	);
	
	CREATE INDEX _get_candles_volumes_from_currencies_row_index_idx ON _get_candles_volumes_from_currencies USING btree(row_index);
	CREATE INDEX _get_candles_volumes_from_currencies_full_name_idx ON _get_candles_volumes_from_currencies USING btree(full_name);
	CREATE INDEX _get_candles_volumes_from_currencies_the_date_idx ON _get_candles_volumes_from_currencies USING btree(the_date); --check

	RETURN QUERY SELECT * FROM _get_candles_volumes_from_currencies; 

END
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION trading.get_candles_volumes_from_currencies(TEXT[], timestamp, int, int, int) IS 'From a set of currencies, and a timestamp, get the associated forex candles with their bid and ask volumes.';

--TEST
--SELECT * FROM trading.get_candles_volumes_from_currencies(ARRAY['EUR','USD','GBP','JPY'], '07 Mar 2022 12:30:00'::timestamp, 100) 




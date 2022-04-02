
DROP TABLE IF EXISTS tmp_queries;
DROP TABLE IF EXISTS tmp_candles;

WITH textresultqueries AS (
	SELECT * FROM (VALUES 
		%(text_result_queries)s
	) AS trq(the_date,instrument,duration)
)
SELECT *,
	the_date + (duration::TEXT || ' minutes')::INTERVAL AS select_end_date,
	ROW_NUMBER() OVER () - 1 AS query_id
INTO tmp_queries FROM textresultqueries;

CREATE INDEX tmp_query_instrument_date_idx ON tmp_queries USING btree(instrument,the_date);

WITH candles AS (
	SELECT trq.query_id, 
	trq.instrument, 
	evt.high_price,
	evt.low_price,
	evt.close_price,
	ROUND(((evt.high_price + evt.low_price + evt.close_price) / 3)::DECIMAL,4) AS typical_price,
	TO_TIMESTAMP (FLOOR(( EXTRACT ('EPOCH' FROM (evt.the_date )) ) / (60*15) ) * (60*15)) AT TIME ZONE 'UTC' AS the_date  --rounding the date off to the nearest 15 mins 
	FROM tmp_queries trq 
	LEFT JOIN exchange_value_tick evt 
	ON evt.full_name = trq.instrument 
	WHERE evt.the_date > trq.the_date 
	AND evt.the_date < trq.select_end_date
)
SELECT * INTO tmp_candles FROM candles; 

CREATE INDEX tmp_candles_queries_idx ON tmp_candles USING btree(query_id);

WITH aggs AS (
	SELECT query_id,
	ARRAY_LENGTH(ARRAY_AGG(1),1) AS n,
	ARRAY_AGG(low_price ORDER BY the_date ASC) AS low_prices, 
	ARRAY_AGG(high_price ORDER BY the_date ASC) AS high_prices, 
	ARRAY_AGG(typical_price ORDER BY the_date ASC) AS typical_prices, 
	STDDEV(low_price) AS low_std,
	STDDEV(high_price) AS high_std,
	STDDEV(typical_price) AS typical_std,
	MIN(the_date) AS start_date,
	MAX(the_date) AS end_date,
	AVG(typical_price) AS typical_average,
	AVG(low_price) AS low_average,
	AVG(high_price) AS high_average
	FROM tmp_candles 
	GROUP BY query_id
),
rate_changes AS (
	SELECT *, 
	(typical_prices[n] - typical_prices[1]) / typical_prices[n] AS typical_rate,
	(high_prices[n] - high_prices[1]) / high_prices[n] AS high_rate,
	(low_prices[n] - low_prices[1]) / low_prices[n] AS low_rate
	FROM aggs
	WHERE n > 0
)
SELECT JSON_BUILD_OBJECT( --FIRST the VALUES 
	'query_id',q.query_id,
	'start_date',r.start_date,
	'end_date',r.end_date,
	'n_candles',COALESCE(r.n,0),
	'typical',JSON_BUILD_OBJECT(
		'rate',r.typical_rate,
		'std',r.typical_std,
		'average',r.typical_average
	),
	'high',JSON_BUILD_OBJECT(
		'rate',r.high_rate,
		'std',r.high_std,
		'average',r.high_average
	),
	'low',JSON_BUILD_OBJECT(
		'rate',r.low_rate,
		'std',r.low_std,
		'average',r.low_average
	)	
),
JSON_BUILD_OBJECT( --now the paths 
	'typical',r.typical_prices,
	'high',r.high_prices,
	'low',r.low_prices
)
FROM tmp_queries q
LEFT JOIN rate_changes r ON q.query_id = r.query_id
ORDER BY q.query_id ASC --sticks everything back in order for a quick zip in the data provider


















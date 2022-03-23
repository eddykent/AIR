
DROP TABLE IF EXISTS tmp_queries;
DROP TABLE IF EXISTS tmp_candles;

WITH textresultqueries AS (
	SELECT * FROM (VALUES 
		('9e6db9e9-5f60-4799-9235-a6820795e1ac','2021-04-27T12:50:00'::timestamp::TIMESTAMP,'USD/CAD',360::INT),('2c186dc0-d4d8-44fd-935a-136295966622','2021-04-27T07:00:00'::timestamp::TIMESTAMP,'GBP/USD',360::INT),('e3f8e0aa-5a55-4089-9c6d-e70dcd111ea5','2021-04-27T05:30:00'::timestamp::TIMESTAMP,'CAD/JPY',360::INT),('d1db0e71-631f-4ec0-b3c2-480a7b4fbd52','2021-04-27T02:00:00'::timestamp::TIMESTAMP,'AUD/USD',360::INT),('b381befd-0cd8-4a8b-ae1a-451e3149747a','2021-04-26T19:00:00'::timestamp::TIMESTAMP,'AUD/USD',360::INT),('1ef3501d-9a9d-413c-8d0e-2e542caf8b4e','2021-04-26T14:30:00'::timestamp::TIMESTAMP,'USD/CAD',360::INT),('84977c0a-e4fa-4538-8ecb-0dca8e26a8ca','2021-04-26T11:00:00'::timestamp::TIMESTAMP,'GBP/USD',360::INT),('ccacf323-8151-434e-969c-4e25e275971d','2021-04-26T08:32:00'::timestamp::TIMESTAMP,'EUR/USD',360::INT),('ce59a368-8c58-4667-9a58-7a595856c929','2021-04-26T08:00:00'::timestamp::TIMESTAMP,'EUR/USD',360::INT),('4a7a7026-2580-4816-bcff-ac375ee3b01a','2021-04-26T02:00:00'::timestamp::TIMESTAMP,'EUR/JPY',360::INT),('38a8977d-db7d-45d7-b31a-d85440dff98a','2021-04-25T23:00:00'::timestamp::TIMESTAMP,'USD/JPY',360::INT),('09acda9b-d322-471c-ae2a-1ba5d8771f9d','2021-04-25T00:00:00'::timestamp::TIMESTAMP,'EUR/USD',360::INT),('9dff0235-250e-4a8a-85f6-229774e5064f','2021-04-24T20:00:00'::timestamp::TIMESTAMP,'GBP/USD',360::INT),('286578ad-a350-4836-be82-98773ece6f49','2021-04-21T07:00:00'::timestamp::TIMESTAMP,'USD/CAD',360::INT),('dd4f5b77-bb1f-4cf4-b81b-274d631059b1','2021-04-23T21:00:00'::timestamp::TIMESTAMP,'AUD/USD',360::INT),('d7ecff9d-0ad0-4f62-a677-7700aa4d1546','2021-04-23T15:00:00'::timestamp::TIMESTAMP,'EUR/USD',360::INT),('e7d0c4ac-e199-44f2-a0d4-48804c2ea7ad','2021-04-23T14:00:00'::timestamp::TIMESTAMP,'EUR/USD',360::INT),('74e8af88-3ed2-4f23-a373-7a70c3ae393c','2021-04-23T09:30:00'::timestamp::TIMESTAMP,'GBP/USD',360::INT),('e87557f9-6a10-4b83-ac24-1a23bd2908fc','2021-04-23T07:00:00'::timestamp::TIMESTAMP,'EUR/USD',360::INT),('9c7f7a98-c599-4b2d-ac54-246892c3f7ef','2021-04-23T05:00:00'::timestamp::TIMESTAMP,'EUR/GBP',360::INT),('5a17e85e-b36f-4cd6-87c1-27c0ff4e777a','2021-10-11T00:56:00'::timestamp::TIMESTAMP,'EUR/GBP',360::INT),('e7090ed1-fdbd-4cb6-8245-9cb4e82733d3','2021-04-22T23:00:00'::timestamp::TIMESTAMP,'NZD/USD',360::INT),('58205bf0-3187-4a29-b5c7-2dddefa4e1da','2021-04-22T22:00:00'::timestamp::TIMESTAMP,'CAD/JPY',360::INT),('5f962972-9b63-48c3-98c7-007b1872c1ee','2021-04-22T19:00:00'::timestamp::TIMESTAMP,'USD/JPY',360::INT),('9b0dee4b-b429-4d25-814a-b71b776aa896','2021-04-22T15:37:00'::timestamp::TIMESTAMP,'EUR/USD',360::INT)
	) AS trq(query_id,the_date,instrument,duration)
)
SELECT *, the_date + (duration::TEXT || ' minutes')::INTERVAL AS select_end_date INTO tmp_queries FROM textresultqueries;

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
	'query_id',query_id,
	'start_date',start_date,
	'end_date',end_date,
	'n_candles',n,
	'typical',JSON_BUILD_OBJECT(
		'rate',typical_rate,
		'std',typical_std,
		'average',typical_average
	),
	'high',JSON_BUILD_OBJECT(
		'rate',high_rate,
		'std',high_std,
		'average',high_average
	),
	'low',JSON_BUILD_OBJECT(
		'rate',low_rate,
		'std',low_std,
		'average',low_average
	)	
),
JSON_BUILD_OBJECT( --now the paths 
	'typical',typical_prices,
	'high',high_prices,
	'low',low_prices
)
FROM rate_changes 


















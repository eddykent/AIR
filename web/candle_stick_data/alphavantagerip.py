import requests
import json 

import time

import psycopg2

from datetime import datetime

import pdb


###failed: 
#[['BGN','JPY'],['CAD', 'TRY'], ['CHF', 'TRY'], ['EUR', 'ZAR'], ['NOK', 'DKK'], ['NZD', 'RON'], ['NZD', 'TRY'], ['NZD', 'ZAR'], ['SGD', 'HKD'], ['SGD', 'JPY'], ['USD', 'HKD'], ['ZAR', 'RUB']]

sql_row_upsert = '''
UPDATE %(table)s 
SET high_price = %(high)s, low_price = %(low)s, open_price = %(open)s, close_price = %(close)s 
WHERE the_date = %(date)s AND from_currency = %(from)s AND to_currency = %(to)s;
INSERT INTO %(table)s(from_currency,to_currency,full_name,open_price,high_price,low_price,close_price,the_date)
SELECT %(from)s, %(to)s, %(full_name)s, %(open)s, %(high)s, %(low)s, %(close)s, %(date)s
WHERE NOT EXISTS (
	SELECT 1 FROM %(table)s 
	WHERE the_date = %(date)s AND from_currency = %(from)s AND to_currency = %(to)s
);
'''

sql_batch_upsert = '''
WITH dat(_open,_high,_low,_close,_from,_to,_date) AS (
	VALUES %(allrows)s
)
SELECT * INTO TEMPORARY TABLE temp_data FROM dat;

UPDATE %(table)s 
SET high_price = temp_data._high, low_price = temp_data._low, open_price = temp_data._open, close_price = temp_data._close 
FROM temp_data
WHERE the_date = temp_data._date AND from_currency = temp_data._from AND to_currency = temp_data._to;

INSERT INTO %(table)s(from_currency,to_currency,full_name,open_price,high_price,low_price,close_price,the_date)
SELECT td._from, td._to, td._from || '/' || td._to, td._open, td._high, td._low, td._close, td._date 
FROM temp_data td
LEFT JOIN %(table)s e 
ON e.the_date = td._date AND e.from_currency = td._from AND e.to_currency = td._to 
WHERE e IS NULL;
DROP TABLE temp_data;
'''
sql_batch_upsert_row = '''
(%(open)s,%(high)s,%(low)s,%(close)s,'%(from)s','%(to)s','%(date)s'::TIMESTAMP)
'''

###API CALL URLS
api_url = "https://www.alphavantage.co/query?function=%(func)s&from_symbol=%(from)s&to_symbol=%(to)s&outputsize=%(output_size)s&interval=%(interval)s&apikey=%(key)s"


api_example = "https://www.alphavantage.co/query?function=FX_INTRADAY&from_symbol=AUD&to_symbol=CAD&outputsize=full&interval=30min&apikey=WY128RHJH8IPCM4J"


time_step = 'quarts' #'days','hours','halfs','quarts' #no point going lower than quarter of an hour as alpha vantage only gives a few days data

func_map = {
	'quarts':'FX_INTRADAY',
	'halfs':'FX_INTRADAY',
	'hours':'FX_INTRADAY',
	'days':'FX_DAILY',
}

interval_map = {
	'quarts':'15min',
	'halfs':'30min',
	'hours':'60min',
	'days':'60min',
}

table_map = {
	'quarts':'exchange_value_tick',
	'halfs':'exchange_value_hourly',
	'hours':'exchange_value_hourly',
	'days':'exchange_value_daily'
}

headermap = {
	'quarts':'Time Series FX (15min)',
	'halfs':'Time Series FX (30min)',
	'hours':'Time Series FX (60min)',
	'days':'Time Series FX (Daily)'
}

timezonemap = {
	'quarts':'7. Time Zone',
	'hours':'7. Time Zone',
	'halfs':'7. Time Zone',
	'days':'6. Time Zone'
}



def rip_fx_pairs(forexs, keys):
	
	#try:
	retryable = forexs #forexs
	conn = psycopg2.connect("host='localhost' user='postgres' password='0o9i8u7y' dbname='TradeData'")
	cur = conn.cursor()
	
	key_limit = 1
	key_index = 0
	key_used = 0
	N = len(forexs)
	i = 0

	n_records_to_take =  -1


	retries = 5
	try_i = 0

	timezones = {}

	# we can only make 5 requests per key, so list a bunch of keys here
	api_keys = keys

	#pdb.set_trace()

	while retryable and try_i < retries:

		try_i += 1

		failed_pairs = []
		
		#pdb.set_trace()

		for pair in retryable: 

			i += 1

			while True:
				
				f = pair[0]
				t = pair[1]
				
				if key_used >= key_limit:
					key_used = 0
					key_index += 1 # save other keys for now
					key_index = key_index % len(api_keys)
				
				key = api_keys[key_index]
				
				#f = 'EUR'  # when testing
				#t = 'USD'
				#key = 'demo'
				
				start_time = time.time() 
				
				api_params = {'from':str(f),'to':str(t),'key':str(key),'output_size':'full','func':func_map[time_step],'interval':interval_map[time_step]}
				
				
				try:
					response = requests.get(api_url % api_params)
					result = json.loads(response.text)
				except:
					print("%(code)s - %(reason)s" % {'code':response.status_code if response else 'd/c','reason':response.reason if response else 'Temporarily lost connection!'})
					continue 
					
				if 'Information' in result:
					print("Blocked! key was %(key)s. Instrument: %(from)s/%(to)s" % api_params)
					
				
				if headermap[time_step] not in result:
					if 'Invalid API' in response.text:
						failed_pairs.append(pair)
						print('URL FAILED: ')
						print(api_url % api_params)
						print("FAILED PAIRS:"+str(failed_pairs))
						break
					print(api_url % api_params)
					#print(result)
					time.sleep(5)
					if 'Note' in result and 'Thank you for using Alpha Vantage!' in result['Note']:
						key_used = 0 # reset key
						key_index += 1 
						key_index = key_index % len(api_keys)
					continue
					
				series = result[headermap[time_step]]
				meta = result['Meta Data'] if 'Meta Data' in result else {}
				tz = meta.get(timezonemap[time_step],'unknown')
				
				timezones["%(from)s/%(to)s" % api_params] = tz
				#print(timezones)
				
				got_request = time.time()
				
				sqls = ''
				sql_rows = []
				
				i_record = 0
				
				for date in series:
					bits = series[date]
					#date_str  = str(date.year) + '-'+str(date.month)+'-'+str(date.day)
					params = {'open':float(bits['1. open']), 'high':float(bits['2. high']), 'low': float(bits['3. low']), 'close': float(bits['4. close'])}
					params.update({'date':date,'from':str(f),'to':str(t),'full_name':str(f+'/'+t)})
					sql_rows += [sql_batch_upsert_row % params]
					i_record += 1
					if i_record >= n_records_to_take and n_records_to_take > 0:
						break # only take up to so many as already have the data
					
				#print(sqls)
				#allsql = sql_batch_upsert % { 'allrows':','.join(sql_rows)}
				#print(allsql)
				cur.execute(sql_batch_upsert % { 'allrows':','.join(sql_rows),'table':table_map[time_step]})
				
				handled_db = time.time()
				
				print("%(i)s/%(N)s ) Ripped %(from)s/%(to)s. Key %(k)s, HTTP:%(http)s ms, DB:%(db)s ms..." % {
					'i':i,
					'N':N,
					'from':f,
					'to':t, 
					'k': key_index,
					'http':int((got_request - start_time)*1000),
					'db':int((handled_db - got_request)*1000)
				})
				
				key_used += 1 #used it one times
				
				conn.commit()
				break;
			
		retryable = failed_pairs

	#print("ALL FAILED PAIRS: "+str(failed_pairs))

	print("ALL FAILED PAIRS: "+str(retryable))
	print("Timezones: "+str(timezones))

	cur.close()
	conn.close()


fx_mains = [
	'AUD/CAD',
	'AUD/CHF',
	'AUD/JPY',
	'AUD/NZD',
	'AUD/USD',
	'CAD/CHF',
	'CAD/JPY',
	'CHF/JPY',
	'EUR/AUD',
	'EUR/CAD',
	'EUR/CHF',
	'EUR/GBP',
	'EUR/JPY',
	'EUR/NZD',
	'EUR/USD',
	'GBP/AUD',
	'GBP/CAD',
	'GBP/CHF',
	'GBP/JPY',
	'GBP/NZD',
	'GBP/USD',
	'NZD/CAD',
	'NZD/CHF',
	'NZD/JPY',
	'NZD/USD',
	'USD/CAD',
	'USD/CHF',
	'USD/JPY'
]


config_ini = '../../config.ini'
from configparser import ConfigParser
parser = ConfigParser()
parser.read(config_ini)
alphavantage_keys = parser.get('alpha_vantage_keys','keys')

fx_pairs = [fx.split('/') for fx in fx_mains]

rip_fx_pairs(fx_pairs, json.loads(alphavantage_keys))









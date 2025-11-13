

##file to put CSV price/volume data into the database 

import os 
from tqdm import tqdm
import pdb

from data.tools.cursor import Database, Inject

from utils import ListFileReader, TimeHandler


candle_csv_directory = 'data/csvs'

csv_files = [fn for fn in os.listdir(candle_csv_directory) if fn.endswith('.csv')]

#use volume for now - could use dukascopy data instead though probably much better! 
#upsert the volume from every csv file 


sql_batch_upsert_row = '''
(%(bidask)s,%(volume)s,%(from_currency)s,%(to_currency)s,%(the_date)s::TIMESTAMP)
'''

sql_batch_upsert = '''
DROP TABLE IF EXISTS upsert_data;
WITH data(bidask,volume,from_currency,to_currency,the_date) AS (
	VALUES %(allrows)s
)
SELECT * INTO TEMPORARY TABLE upsert_data FROM data;

--first, work out what isnt there & insert
--update the row BID columns 
--update the row ASK columns

INSERT INTO exchange_volume_hourly(from_currency,to_currency,full_name,bid_volume,ask_volume,the_date)
SELECT ud.from_currency, ud.to_currency, ud.from_currency || '/' || ud.to_currency, NULL::DOUBLE PRECISION, NULL::DOUBLE PRECISION, ud.the_date 
FROM upsert_data ud 
LEFT JOIN exchange_volume_hourly evh ON evh.the_date = ud.the_date AND evh.from_currency = ud.from_currency AND evh.to_currency = ud.to_currency
WHERE evh.from_currency IS NULL; --row does not exist

UPDATE exchange_volume_hourly 
SET bid_volume = ud.volume  
FROM upsert_data ud 
WHERE exchange_volume_hourly.from_currency = ud.from_currency 
AND exchange_volume_hourly.to_currency = ud.to_currency 
AND exchange_volume_hourly.the_date = ud.the_date
AND ud.bidask = 'BID';

UPDATE exchange_volume_hourly 
SET ask_volume = ud.volume  
FROM upsert_data ud 
WHERE exchange_volume_hourly.from_currency = ud.from_currency 
AND exchange_volume_hourly.to_currency = ud.to_currency 
AND exchange_volume_hourly.the_date = ud.the_date
AND ud.bidask = 'ASK';

SELECT 1;
'''

#for now, assume we are only using forex (change this later for reading other instruments such as stocks) 
lfr = ListFileReader()
for filename in tqdm(csv_files):
	csv_data = lfr.read_csv(os.path.join(candle_csv_directory,filename))
	from_currency = filename[0:3]
	to_currency = filename[3:6]
	bidask = ''
	if '_BID_' in filename:
		bidask = 'BID'
	if '_ASK_' in filename:
		bidask = 'ASK'
	
	batch_size = 100
	
	sql_rows = [] 
	csv_batches = [csv_data[i:i+batch_size] for i in range(0,len(csv_data),batch_size)]
	for csv_batch in tqdm(csv_batches,leave=False):
		with Database(cache=False,commit=True) as cursor:
			for csv_row in csv_batch:
				volume_str = csv_row['Volume']
				try:
					volume = float(volume_str)
				except:
					#do a log here
					print(f"failed to parse volume string '{volume_str}'...")
					pdb.set_trace()
					volume = None
				if not volume:
					continue
				the_date = csv_row['Gmt time'] #parse date?
				the_date = TimeHandler.from_str_1(the_date,date_delimiter='.',time_delimiter=':')
				row_params = {			
					'bidask':bidask,
					'volume':volume,
					'from_currency':from_currency,
					'to_currency':to_currency,
					'the_date': the_date
				}
				sql_rows.append(cursor.mogrify(sql_batch_upsert_row,row_params).decode())
			if sql_rows:
				cursor.execute(sql_batch_upsert,{'allrows':Inject(','.join(sql_rows))})























import datetime 
from dateutil.rrule import rrule, MONTHLY
from tqdm import tqdm

##file for finding any missing data between two dates 
import pdb

from utils import ListFileReader, Inject, Database
lfr = ListFileReader()
fx_pairs = lfr.read("./fx_pairs/fx_mains.txt")

class HoleFinder:
	
	output_filename = "./data/data_holes.txt"
	
	query_file = "./queries/holefinder.sql" #find holes in raw_fx_candles_15m - config! 
	table_name = "raw_fx_candles_15m" #exchange_value_tick, exchange_volume_tick 
	table_alias = 'rfc'
	columns = [
		'bid_open',
		'bid_high',
		'bid_low',
		'bid_close',
		'bid_volume',
		'ask_open',
		'ask_high',
		'ask_low',
		'ask_close',
		'ask_volume'		
	] #['open_price','high_price','low_price','close_price'] or ['bid_volume','ask_volume']
	
	bank_holidates = []
	
	
	start_date = datetime.datetime.now() - datetime.timedelta(weeks=52)
	end_date = datetime.datetime.now() 
	instruments = fx_pairs
	
	def __init__(self,start_date=None,end_date=None,instruments=[]):
		self.start_date = start_date or self.start_date
		self.end_date = end_date or self.end_date
		self.instruments = instruments or self.instruments
	
	def find_holes(self):
		result = []
		column_null_checks = ' OR '.join([self.table_alias+'.'+col+ ' IS NULL' for col in self.columns])
		#start_date = self.start_date
		#end_date = self.end_date
		monthlys = [dt for dt in rrule(MONTHLY, dtstart=self.start_date,until=self.end_date)]
		bank_holidays = [datetime.datetime(1900,1,1)]
		
		excemptions = [] #TODO
		query = ''
		with open(self.query_file,'r') as fp:
			query = fp.read()
		with Database(cache=False, commit=False) as cur:
			for (start_date,end_date) in tqdm(list(zip(monthlys[:-1],monthlys[1:]))):
				#print(f"FROM {start_date} TO {end_date}...")
				params = {
					'table_name':Inject(self.table_name), 
					'table_alias':Inject(self.table_alias),
					'column_null_checks':Inject(column_null_checks),
					'instruments':self.instruments,
					'start_date':start_date, 
					'end_date':end_date,
					'bank_holidays':bank_holidays#,
					#'excemptions':Inject([])
				}
				#pdb.set_trace()
				cur.execute(query,params)
				result_batch = cur.fetchall()
				#pdb.set_trace() 
				result += result_batch
		
		return result 






















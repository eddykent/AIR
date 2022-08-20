import pdb
import numpy as np 
from tqdm import tqdm 


from utils import overrides
from filters.trade_filter import *

from utils import Database, ListFileReader, Inject

###filters that are time based or that are based on events in time 
##filter that stops any trade signal that has a particular time of day (eg 10pm to 10:30pm where the spreads are fucking wild) to stop trades
class CrazySpreadsFilter(TimelineTradeFilter):
	
	bad_spread_times = [((21,0),(22,30))] #convert to minutes from start of day (simple timespans) 
	sbs = 30 #30 mins either side of the bad spread times 
	
	
	def check_instrument(self,instrument, direction, the_date):
		minute = the_date.min
		hour = the_date.hour 
		
		day_mins = minute + 60*hour 
		
		for ((sh,sm),(eh,em)) in self.bad_spread_times:	
			if (sh*60 + sm) <= day_mins and (eh*60 + em) <= day_mins:  
				return False #this time is within the bad spread time - do not execute! 
		return True

##filter based on the economic calendar events 
class EconomicCalendarFilter(TimelineTradeFilter):
	
	after = 30#ok 30 mins after the event 
	before = 360#ok 1 hours before the event 
	
	chunk_size = 200
	
	mapping_to_currencies = { #read from file 
		##'USD':['USA'],
		#'EUR':['European Area','France','Germany'] #Spain, Italy, France, Germany, Belgium - add if needede 
		#'
	}
	
	def __init__(self):
		lfr = ListFileReader()
		self.mapping_to_currencies = lfr.read_json("./currency_country_map.json")
		
	
	@overrides(TimelineTradeFilter)
	def filter(self,trades):
		ttts = [] 
		for trade in trades: 
			instrs = trade.instrument.split('/')
			if len(instrs) == 1:	
				instrs.append(instrs[0])
			curr1, curr2 = instrs 
			the_time = trade.the_date 
			ttts.append((curr1.upper(),curr2.upper(),the_time))
		
		cur = Database() 
		sql_row = '(%(countries)s,%(the_time)s)'
		sql_eca = ''
		with open('queries/economic_calendar_analyse.sql','r') as f:
			sql_eca = f.read()
		mask_arr = []
		event_guids = []
		print('Analysing economic calendar...')
		for ttsc in tqdm([ttts[i:i+self.chunk_size] for i in range(0,len(ttts),self.chunk_size)]):
			sql_rows = [] 
			for tts in ttsc:
				countries = self.mapping_to_currencies.get(tts[0],[]) + self.mapping_to_currencies.get(tts[1],[])
				sql_rows.append(cur.mogrify(sql_row,{'countries':countries,'the_time':tts[2]}).decode())
			cur.execute(sql_eca,{'events':Inject(','.join(sql_rows)),'before':self.before,'after':self.after})
			results = cur.fetchall()
			#pdb.set_trace()
			mask_arr.extend([r[1] == 0 for r in results])
			event_guids.extend([r[2] for r in results])
		return_trades = []
		for trade,mask in zip(trades,mask_arr):
			if mask:
				return_trades.append(trade)
		return return_trades 

















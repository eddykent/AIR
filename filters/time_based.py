import pdb
import numpy as np 
import pandas as pd
from tqdm import tqdm 
import datetime

from utils import overrides
from filters.trade_filter import *

from utils import Database, ListFileReader, Inject, PipHandler

economic_calendar_sql = """
SELECT 
guid, the_date, impact, country, description 
FROM economic_calendar 
WHERE the_date >= %(start_date)s 
AND the_date <= %(end_date)s
"""

#use this tool to read the economic calendar events out of the database into a dataframe
class EconomicCalendarTool:
	
	start_date = None
	end_date = None 
	currency_country_map = []
	
	def __init__(self,start_date=datetime.datetime.now(),end_date=None):
	
		#,start_date, end_date=datetime.datetime.now()):
		self.start_date = start_date
		self.end_date = end_date if end_date is not None else start_date + datetime.timedelta(days=7)
		
		lfr = ListFileReader()
		self.currency_country_map = lfr.read_json("config/currency_country_map.json")
		
		#inv map 
		self.country_currency_map = {v:k for (k,vs) in self.currency_country_map.items() for v in vs }
		
		
		
	def get_df(self):
		rows = []
		ccm = self.country_currency_map
		with Database(cache=False,commit=False) as cur:
			cur.execute(economic_calendar_sql,{
				'start_date':self.start_date,
				'end_date':self.end_date
			})
			rows = cur.fetchall()
		the_df = pd.DataFrame(rows,columns=['guid', 'the_date', 'impact', 'country', 'description']) 
		#pdb.set_trace()
		the_df['currency'] = the_df.apply(lambda r, ccm=ccm: ccm.get(r['country'],'???'),axis=1)
		#now expand with currency using apply
		return the_df
	

class EconomicCalendarFilter(ExtractableFilter):
	
	events_df = None 
	
	impact = 3 #impact level to consider 
	before = 300 #ok 5 hours before event 
	after = 60 #ok 1 hour after the event 
	
	@overrides(TimelineTradeFilter)
	def __init__(self,events_df):
		self.events_df = events_df
	
	@overrides(TimelineTradeFilter)
	def check_instrument(self,instrument, direction, the_date):
		#pdb.set_trace()
		#print(instrument + ' @ ' + str(the_date))
		ins = instrument.split('/')
		if len(ins) == 2:
			impact = (self.events_df['impact'] >= self.impact)
			ins1 = (self.events_df['currency'] == ins[0])
			ins2 = (self.events_df['currency'] == ins[1])
			before = (self.events_df['the_date'] >= the_date - datetime.timedelta(minutes=self.after))
			after = (self.events_df['the_date'] <= the_date + datetime.timedelta(minutes=self.before))
			
			instr = ins1 | ins2 
			timing = before & after
			indexer = impact & instr & timing 
			#print(self.events_df[indexer][['impact','the_date','currency','description']])
			#pdb.set_trace() #check a few of em 
			return not indexer.any() #esnure there are not any economic events about to happen 
		return True 
	
	
	@overrides(ExtractableFilter)
	def extract_mask(self,instruments,timeline):
		result = np.full((len(instruments),len(timeline)),True)
		using_df = self.events_df[self.events_df['impact'] >= self.impact][['the_date','currency']].copy() 
		pdt = pd.Series(timeline)
		pdt.index = pdt
		#USE IN BT OPTIMISATION
		using_df['tl_start_index'] = pdt.index.get_indexer(using_df['the_date'] - datetime.timedelta(minutes=self.before),method='nearest') 
		using_df['tl_end_index'] = pdt.index.get_indexer(using_df['the_date'] + datetime.timedelta(minutes=self.after),method='nearest') 
		ia = np.array([ifx.split('/') for ifx in instruments]) #replace with list of currencies per instrument for stocks data?
		#np.where((ia[:,0] == 'AUD') | (ia[:,1] == 'AUD'))[0]
		using_df['instrument_indexs'] = using_df.apply(lambda row, ia=ia : np.where((ia[:,0] == row['currency']) | (ia[:,1] == row['currency']))[0] ,axis=1)
		#index_df.apply(lambda row, result=result : result[row[instrument_indexs],row['tl_start_index']:row['tl_end_index']+1] = False)
		pdb.set_trace()
		for (start,end,iis) in using_df[['tl_start_index','tl_end_index','instrument_indexs']].to_numpy():	
			result[iis,start:end] = False   #+1 on end?
			
		return result
		

###filters that are time based or that are based on events in time 
##filter that stops any trade signal that has a particular time of day (eg 10pm to 10:30pm where the spreads are fucking wild) to stop trades
class TimeOfDayFilter(ExtractableFilter): #think of daylight savings
	
	timespans = [((21,0),(22,30))] #convert to minutes from start of day (simple timespans) 
	#consider creating class TimeSpanOfDay, also a dataframe? 
	sbs = 30 #30 mins either side of the bad spread times 
	
	@overrides(TimelineTradeFilter)
	def __init__(self,timespans=None):
		if timespans:
			self.timespans = timespans 
	
	@overrides(TimelineTradeFilter)
	def check_instrument(self,instrument, direction, the_date):
		return self._check_time(the_date)
	
	def _check_time(self,the_date):
		
		day_mins = the_date.minute + 60*the_date.hour 
		
		for ((sh,sm),(eh,em)) in self.timespans:	
			if (sh*60 + sm) <= day_mins <= (eh*60 + em):  
				return False #this time is within the bad spread time - do not execute! 
		return True
	
	@overrides(ExtractableFilter)
	def extract_mask(self,instruments,timeline):
		ok_times = [self._check_time(the_date) for the_date in timeline]
		mult = len(instruments)
		ok_block = [ok_times]*mult
		return np.array(ok_block)
		
		
		

class PipSpreadFilter(ExtractableFilter):#eg, if spread is over 5 pips skip it. Used only for backtest as we got live broker for forward
	
	max_pips = 5
	pip_handle = None
	backtest_data = None 
	
	#calc'd values 
	_spreads = None 
	
	@overrides(TimelineTradeFilter)
	def __init__(self, backtest_data, max_pips=5, pip_handle=None):
		if not pip_handle:
			pip_handle = PipHandler() #default one 
		self.pip_handle = pip_handle
		self.max_pips = 5
		self.backtest_data = backtest_data
		self._calc_spreads_pips()
		
	def _calc_spreads_pips(self):
		#bidask = np.sum(self.backtest_data.np_candles[:,:,:,1:],axis=3)
		bidask = self.backtest_data.np_candles[:,:,:,3]
		spreads = np.abs(bidask[:,:,0] - bidask[:,:,1])
		instr_conv = np.array([self.pip_handle.pip_map[i] for i in self.backtest_data.instruments])[:,np.newaxis]
		self._spreads = spreads / instr_conv
		#pdb.set_trace()
		#print('calc typical spreads')
	
	@overrides(TimelineTradeFilter)
	def check_instrument(self,instrument, direction, the_date):
		ti = self.backtest_data.closest_time_index(the_date) - 1 #back 1 since we want start time of candle 
		ii = self.backtest_data.instrument_index(instrument) #these func calls might be slow :( 
		return self._spreads[ii,ti] < self.max_pips
		
	@overrides(ExtractableFilter)
	def extract_mask(self,instruments,timeline): #could add capacity to use diff timeline & instruments but for now not needed
		assert len(instruments) == self._spreads.shape[0], 'instruments diff length to spreads'
		assert len(timeline) == self._spreads.shape[1], 'timeline diff length to spreads'
		return self._spreads < self.max_pips
		
	
##filter based on the economic calendar events from the database - consider a database free one (read info first) 
class DatabaseEconomicCalendarFilter(TimelineTradeFilter):
	
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
		self.mapping_to_currencies = lfr.read_json("config/currency_country_map.json")
		
	
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

















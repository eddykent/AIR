

import datetime
from typing import Optional, List 
import numpy as np #for optimising later 

import pdb 

from utils import CurrencyPair, ListFileReader, overrides
from setups.trade_setup import TradeSignal, TradeDirection
from indicators.indicator import CandleSticks

 #abstract class for laying out a trade filter - attempt to stop "stupid" trades! Works with a single instance in time 
class InstanceTradeFilter:
	
	snapshot = {} #the snapshot in time of some stuff to use in the filtering 
	
	def __init__(self,snap : dict):
		self.snapshot = snap
	
	def filter(self,trades : List[TradeSignal]):
		return [t for t in trades if self.check_instrument(t.instrument,t.direction)]
	
	def check_instrument(self,instrument : str,direction : TradeDirection=TradeDirection.VOID):
		raise NotImplementedError('This method must be overridden')
		return True  #check to see if doing a buy/sell on this pair is a good idea or not 


#from a wealth of information regarding each instrument across time, this filter tests to see if a 
#trade will go against something in one of these timelines. Used mainly for news filters 
class TimelineTradeFilter:
	
	expire = 360 #6 hours -anything after 6 hours can be considered forgotten. Can be changed for different things 
	candle_length = None 
	
	def set_chart_resolution(self,cr):
		self.candle_length = cr
	
	def filter(self,trades):
		return [t for t in trades if self.check_instrument(t.instrument,t.direction,t.the_date)]
	
	
	def check_instrument(self,instrument,direction=TradeDirection.VOID,the_date=datetime.datetime.now()):
		raise NotImplementedError('This method must be overridden')
		return True  #check to see if doing a buy/sell on this pair is a good idea or not 
	
#filter based on an indicator, or many
class IndicatorFilter(TimelineTradeFilter):  ##base this on an indicator so any indicator can be used as a filter? 
	
	#expire = 1440 #full day - the timeline should have dates in it at a higher resolution 
	timeline = None 
	instruments = None
	np_candles = None
	candle_streams = None 
	
	_instrument_map = {} 
	
	#results = None  #specific to what indicators are used 
	
	def __init__(self,candles,instruments,chart_resolution): 
		self.set_chart_resolution(chart_resolution)
		cs = CandleSticks()
		cs.pass_instrument_names(instruments)
		self.candle_streams = candles
		np_candles = cs.calculate_multiple(candles)
		self.instruments = instruments
		self.timeline = cs.timeline 
		self.np_candles = np_candles 
		
		for e,i in enumerate(instruments):	
			self._instrument_map[i] = e
		
		self.setup_indicator_results()
		
	def setup_indicator_results(self):
		raise NotImplementedError('This method must be overridden')
	
	#def check_instrument(self,instrument,direction,the_date):
	#	raise NotImplementedError('This method must be overridden')
		
	def _closest_time_index(self,the_date,offset=0):
		#this needs to be modified to get the previous candle result - we dont have the full candle yet in backtesting 
		timeline = self.timeline[:,0]
		the_date = the_date - datetime.timedelta(minutes=self.candle_length) #use prev candle for pretty much every indicator
		end_date = the_date 
		start_date = the_date - datetime.timedelta(minutes=self.expire)
		mask = (timeline >= start_date) & (timeline <= end_date)
		inds = np.where(mask)[0]
		if len(inds):
			return inds[-1] #get latest most recent index - might be different for news?
		return None #not found 
		
		
	def _instrument_index(self,instrument):
		return self._instrument_map.get(instrument)
		#if instrument in self.instruments:
		#	return self.instruments.index(instrument)
		#return None

#beautiful filter that sorts out the db stuff for us. 
class DataBasedFilter(TimelineTradeFilter):
	
	timeline = None
	instruments = None
	_instrument_map = {}
	
	data_block = None #np array?
	
	def __init__(self,data):
		
		self.data_block, self.instruments, self.timeline = self._process_data_block(data)
		
		for e,i in enumerate(self.instruments):	
			self._instrument_map[i] = e


	def _process_data_block(self,data,select_function=None):
		instruments = list(data[0][2].keys())
		timeline = [] 
		instruments = sorted(instruments)
		
		#assert that whole list has all instruments? 
		for timestepdict in data: 
			for inst in instruments:
				if not inst in timestepdict[2]:
					pdb.set_trace()
				assert inst in timestepdict[2], "data is incomplete"
		
		#make correlation block - instrument, timeline, {n_corr, std, up/down change}
		block = [] 
		if select_function and callable(select_function):
			for timestepdict in data:
				block_items = [] 
				timeline.append(timestepdict[0])
				for inst in instruments:
					block_items.append(select_function(timestepdict[2][inst]))
				block.append(block_items)
		else:
			for timestepdict in data:
				block_items = [] 
				timeline.append(timestepdict[0])
				for inst in instruments:
					block_items.append(self.process_data_piece(timestepdict[2][inst]))
				block.append(block_items)
		
		assert len(block), 'no data'
		assert len(block[0]), 'no data' 
		
		dim3 = len(block[0][0])
		dim1 = len(instruments)
		dim2 = len(data)
		
		data_block = np.full((dim1,dim2,dim3),np.nan)  #better way anywhere? 
		for d1 in range(dim1):
			for d2 in range(dim2):
				for d3 in range(dim3):
					try:
						data_block[d1,d2,d3] = block[d2][d1][d3]
					except:
						pdb.set_trace()
		#pdb.set_trace()
		return data_block, instruments, np.array(timeline).reshape((len(timeline),1))


	#weird stuff - perhaps consider refactoring  
	def _closest_time_index(self,the_date):
		return IndicatorFilter._closest_time_index(self,the_date)
	
	def _instrument_index(self,instrument):
		return IndicatorFilter._instrument_index(self,instrument)

	def process_data_piece(self,data_piece):
		raise NotImplementedError('This method must be overridden')

	def check_instrument(self,instrument,direction,the_time):
		raise NotImplementedError('This method must be overridden')












	





















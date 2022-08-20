

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
	
	def filter(self,trades):
		return [t for t in trades if self.check_instrument(t.instrument,t.direction,t.the_date)]
	
	
	def check_instrument(self,instrument,direction=TradeDirection.VOID,the_date=datetime.datetime.now()):
		raise NotImplementedError('This method must be overridden')
		return True  #check to see if doing a buy/sell on this pair is a good idea or not 
	

class IndicatorFilter(TimelineTradeFilter):  ##base this on an indicator so any indicator can be used as a filter? 
	
	#expire = 1440 #full day - the timeline should have dates in it at a higher resolution 
	timeline = None 
	instruments = None
	np_candles = None
	
	_instrument_map = {} 
	
	#results = None  #specific to what indicators are used 
	
	def __init__(self,candles,instruments): 
		cs = CandleSticks()
		cs.pass_instrument_names(instruments)
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
		
	def _closest_time_index(self,the_date):
		timeline = self.timeline[:,0]
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


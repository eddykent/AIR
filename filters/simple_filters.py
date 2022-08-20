
import pdb
import numpy as np 

##indicator based filters

from utils import overrides
from filters.trade_filter import *
from indicators.moving_average import EMA 



class ForexSignalsAnchorBarFilter(IndicatorFilter):
	
	ema_fast = EMA()
	ema_slow = EMA()
	
	fast_results = None
	slow_results = None
	
	@overrides(IndicatorFilter)
	def setup_indicator_results(self):
		
		self.ema_fast.period = 8 #check
		self.ema_slow.period = 21 
		
		self.fast_results = self.ema_fast._perform(self.np_candles)[:,:,0]
		self.slow_results = self.ema_slow._perform(self.np_candles)[:,:,0]
			
	
	@overrides(IndicatorFilter)
	def check_instrument(self, instrument, direction, the_time):	
		
		#pdb.set_trace()
		
		ti = self._closest_time_index(the_time)
		ii = self._instrument_index(instrument) 
		
		if ti is not None and ii is not None: 
			if (self.fast_results[ii,ti] > self.slow_results[ii,ti]) and direction == TradeDirection.SELL:
				return False #selling when we should be buying 
			if (self.fast_results[ii,ti] < self.slow_results[ii,ti]) and direction == TradeDirection.BUY:
				return False 
		return True 
			
	
	
	
	





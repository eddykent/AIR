
import pdb
import numpy as np 

##indicator based filters

from utils import overrides
from filters.trade_filter import *
from indicators.moving_average import EMA 
from indicators.reversal import RSI 
from indicators.indicator import CandleSticks
import charting.candle_stick_functions as csf

#for use with the crappy forex signal strat
class ForexSignalsAnchorBarFilter(IndicatorFilter):
	
	ema_fast = EMA()
	ema_slow = EMA()
	candlesticks = CandleSticks() 
	
	fast_results = None
	slow_results = None
	candlestick_data = None 
	
	@overrides(IndicatorFilter)
	def setup_indicator_results(self):
		
		self.ema_fast.period = 8 #check
		self.ema_slow.period = 21 
		
		self.fast_results = self.ema_fast._perform(self.np_candles)[:,:,0]
		self.slow_results = self.ema_slow._perform(self.np_candles)[:,:,0]
		self.candlestick_data = self.candlesticks._perform(self.np_candles) 
		
			
	
	@overrides(IndicatorFilter)
	def check_instrument(self, instrument, direction, the_time):	
		
		
		ti = self._closest_time_index(the_time)
		ii = self._instrument_index(instrument) 
		
		if ti is None or ii is None: 
			return False
		
		if direction == TradeDirection.BUY:
			if (self.fast_results[ii,ti] > self.slow_results[ii,ti]) and (self.candlestick_data[ii,ti,csf.low] > self.fast_results[ii,ti]):
				return True  
		if direction == TradeDirection.SELL:
			if (self.fast_results[ii,ti] < self.slow_results[ii,ti]) and (self.candlestick_data[ii,ti,csf.high] < self.fast_results[ii,ti]):
				return True 

		
		return False 
			
class RSIFilter(IndicatorFilter):
	
	rsi_op = RSI()
	rsi_thres = 0.2
	rsi_results = None
	
	@overrides(IndicatorFilter)
	def setup_indicator_results(self):
		
		self.rsi_op.period = 14 #check
		
		self.rsi_results = self.rsi_op._perform(self.np_candles)[:,:,0]
			
	
	@overrides(IndicatorFilter)
	def check_instrument(self, instrument, direction, the_time):	
		
		ti = self._closest_time_index(the_time)
		ii = self._instrument_index(instrument) 
		
		if ti is not None and ii is not None: 
			if self.rsi_results[ii,ti] < self.rsi_thres and direction == TradeDirection.SELL:
				return False #selling when we should be buying 
			if self.rsi_results[ii,ti] > (1 - self.rsi_thres) and direction == TradeDirection.BUY:
				return False 
		return True 	
	

class LambdaSelectFilter(TimelineTradeFilter):	
	
	lambda_function = None
	
	def __init__(self, lambda_function):
		self.lambda_function = lambda_function
		assert callable(lambda_function) , 'LambdaSelectFilter requires a function that maps a trade signal to bool'
	
	#def check_instrument() #dont use
	@overrides(TimelineTradeFilter)
	def filter(self,trades):
		return [t for t in trades if self.lambda_function(t)]







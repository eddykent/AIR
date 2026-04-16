
import pdb
import numpy as np 
from tqdm import tqdm
import datetime
import time

##indicator based filters - one result per trade (more accurate)

from data.tools.cursor import Database

from air.utils import overrides
from air.filters.trade_filter import *
from air.indicators.reversal import RSI 
from air.indicators.trend import ADX
from air.setups.signal import TradeDirection 

#deprecate?
class RSIFilterSlow(LateralIndicatorFilter):
	
	_days_back_buffer = 7 #the larger the slower but the more accurate
	_bounds = 0.2

	
	#this is painfully slow 
	def get_candles_for_signal(self,index, trade_signal): 
	#use this func to get partial candle & rest of candle from initial data read
		self.candle_data_tool._dbcursor.con.rollback()
		self.candle_data_tool.end_date = trade_signal.the_date 
		self.candle_data_tool.start_date = trade_signal.the_date - datetime.timedelta(days=self._days_back_buffer)
		self.candle_data_tool.read_data_from_instruments([trade_signal.instrument],3)
		tsd = self.candle_data_tool.get_trade_signalling_data()		
		return tsd.np_candles
		
	@overrides(LateralIndicatorFilter)
	def filter(self, trade_signals):
		
		cursor = Database(cache=False,commit=False)		
		self.candle_data_tool._dbcursor = cursor #prevent opening/closing connections everytime
		
		#load partial candles 
		
		rsi_op = RSI()
		#period?
		
		filtered_signals = [] 
		dbtime = 0
		intime = 0 
		
		#pdb.set_trace()
		
		
		for i,ts in tqdm(list(enumerate(trade_signals))):
			
			ttt = time.time() 
			np_candles = self.get_candles_for_signal(i,ts)
			dbtime += (time.time() - ttt)
			
			ttt = time.time()
			rsi_result = rsi_op._perform(np_candles)[0,-1,0]
			intime += (time.time() - ttt)
			
			if ts.direction == TradeDirection.BUY and rsi_result < (1 - self._bounds):
				filtered_signals.append(ts)
			
			if ts.direction == TradeDirection.SELL and rsi_result > self._bounds:
				filtered_signals.append(ts)
		
		cursor.close() 
		
		print('database time: '+str(dbtime))
		print('indicator time: '+str(intime))
		
		return filtered_signals

class ADXFilter(PartialIndicatorFilter):
	
	_strong_trend = 0.25
	
	def filter(self,trade_signals):
		
		adx_op = ADX() 
		
		filtered_signals = []
		
		np_candles = self._get_candle_streams(trade_signals)
		
		adx_result = adx_op._perform(np_candles)
		end_results = adx_result[:,-1,0]
		
		for ts,adxval in zip(trade_signals, end_results):
			if adxval > self._strong_trend:
				filtered_signals.append(ts)
		
		return filtered_signals
		
		
class RSIFilter(PartialIndicatorFilter):
	
	_bounds = 0.3 #rsi bounds
		
	def filter(self,trade_signals):

		#loaded partial candles 
		rsi_op = RSI()
		
		filtered_signals = [] 
		
		np_candles = self._get_candle_streams(trade_signals)
		
		rsi_result = rsi_op._perform(np_candles)
		end_results = rsi_result[:,-1,0]
		
		for ts,rsival in zip(trade_signals, end_results):
			if ts.direction == TradeDirection.BUY and rsival < (1 - self._bounds):
				filtered_signals.append(ts)
			
			if ts.direction == TradeDirection.SELL and rsival > self._bounds:
				filtered_signals.append(ts) 
		
		return filtered_signals
		
	














## setups are trades that have been produced from signals from various sources. A TradeSetup class finds trades on a given date 
#that have a high probabily of winning based on their backtest results.  TradeSetup classes need to be backtestable 
#all implementations are in subclasses to this file - it is not possible to import indicator based stuff (circular import?)
from datetime import datetime,timedelta
from typing import Optional, List
import numpy as np
import scipy.signal
import scipy.optimize

import pdb

from utils import ListFileReader, Database, DataComposer, PipHandler
from utils import overrides, deprecated
import charting.chart_viewer as chv 
from charting import candle_stick_functions as csf
#from charting.chart_pattern import ChartPattern - unable to import any indicator related stuff here 

from indicators.indicator import CandleSticks, CandleType
from indicators.volatility import ATR

from setups.signal import *

from setups.setup_tools import ATRStop



#global space function for handling the base cases 
def blank_result(trade_signalling_data,blank_val=None): #blank val can be a 0 or np.nan if needed
	np_candles = trade_signalling_data.np_candles
	result = np.full(np_candles.shape[:2],blank_val) 
	return result, result



class TradeSetup:	#this not just an indicator - does not have calculate() etc. It is its own thing that finds trade signals 	
	
	grace_period = 10 #number of candles to go back to get an accurate reading at start_date
	stop_calculator = ATRStop() #by default, all trade setups use ATR but for bespoke stops, we can create a new stop tool 
	#and set this to an instance 
	setup_name = None
	
	#by default, get the setups and turn to -1s and 1s?
	def detect(self, trade_signalling_data : TradeSignallingData) -> np.array:# - for AI - 0s and 1s or similar delivered from  get_setups()
		"""
		Generate a list of numbers (per instrument) between -1 and 1 where -1 is very bearish and 1 is very bullish with high confidence 
		A value close to 0 has low confidence and might be best not to be used. 
		
		Note: 
		This function can be used to generate filters but it is computationally expensive - it has to create setups first then turn them
		back into a numpy array. Therefore, it might be best to implement the filter directly using the indicators. An alternative is to 
		override this function within the base to create a faster version
		
		Parameters
		---------
		start_date : datetime 
			The date in which to start looking for setups 
		end_date : datetime 
			The date in which to end looking for setups 
		
		Returns
		-------
		numpy.array 
			A large array (one per instrument) indicating where the buy (positive numbers) and sell (negative numbers) setups were
		"""
		#even though a tradesetup generates trades on the timeframe, they can still be used as filters! just use this detect() method 
		raise NotImplementedError('This method must be overridden') #use get_setups() ! 
	
	#TODO : allow for exit signals in backtester and in strategy
	def get_exits(self, trade_signalling_data):
		return blank_result(trade_signalling_data)
	
	def get_entries(self, trade_signalling_data):
		return blank_result(trade_signalling_data)
		
	#def get_setups_and_confidence(self,start_date,end_date): # perhaps worth thinking about later
	
	def get_entry_cuts(self, trade_signalling_data, extra=None):	
		return blank_result(trade_signalling_data)
	
	def get_name(self): #get full qualified name for backtesting purposes 
		return self.__class__.__module__ + '.' + self.__class__.__name__ if self.setup_name is None else self.setup_name 
	
	def get_setups(self, trade_signalling_data : TradeSignallingData) -> List[TradeSignal]:
		"""
		Generate a set of trade signals from this setup generator
		
		Parameters
		---------
		trade_signalling_data : TradeSignallingData 
			A bundle of data that is used + grown to create the signals 
		
		Returns:
		-------
		list(TradeSignal) 
			A bunch of trade signals that were found in the date range 
		"""
		trade_signalling_data.name = self.get_name()
		trade_signalling_data.bullish.signals, trade_signalling_data.bearish.signals = self.detect(trade_signalling_data)
		trade_signalling_data.bullish.entries, trade_signalling_data.bearish.entries = self.get_entries(trade_signalling_data)
		trade_signalling_data.bullish.entry_cuts,trade_signalling_data.bearish.entry_cuts = self.get_entry_cuts(trade_signalling_data)
		(bullish_tp, bearish_tp), (bullish_sl, bearish_sl) = self.stop_calculator.get_stops(trade_signalling_data)
		trade_signalling_data.bullish.take_profit_distances = bullish_tp
		trade_signalling_data.bearish.take_profit_distances = bearish_tp  
		trade_signalling_data.bullish.stop_loss_distances = bullish_sl
		trade_signalling_data.bearish.stop_loss_distances = bearish_sl
		
		#asserts here? 
		
		return self.make_trade_signals(trade_signalling_data)
		
	
	def make_trade_signals(self,signal_data_extra):	
		trade_signals = []
		
		#export these? would be much faster for any further computation such as filtering...
		buy_coords = np.stack(np.where(signal_data_extra.bullish.signals),axis=1)
		sell_coords = np.stack(np.where(signal_data_extra.bearish.signals),axis=1)
		
		strategy_ref = signal_data_extra.name if signal_data_extra.name else 'Please set the name to this setup to something more meaningful!' 
		
		entry_expire = TradeSignal.entry_expire
		
		for (instrument_index,timeline_index) in buy_coords:
			timeline_index += 1 #push forward by 1 candle to prevent look ahead bias 
			if signal_data_extra.timeline[timeline_index] < signal_data_extra.start_date:
				continue
			instrument = signal_data_extra.instruments[instrument_index]
			the_date = signal_data_extra.timeline[timeline_index]
			direction = TradeDirection.BUY
			entry = signal_data_extra.bullish.entries[instrument_index,timeline_index]  
			entry_cut = signal_data_extra.bullish.entry_cuts[instrument_index,timeline_index]  
			take_profit_distance = signal_data_extra.bullish.take_profit_distances[instrument_index,timeline_index]
			stop_loss_distance = signal_data_extra.bullish.stop_loss_distances[instrument_index,timeline_index]
			ts = TradeSignal.from_full(the_date,instrument,strategy_ref,direction,entry,entry_cut,entry_expire,take_profit_distance,stop_loss_distance)
			trade_signals.append(ts)
		
		for (instrument_index,timeline_index) in sell_coords:
			timeline_index += 1 #push forward by 1 candle to prevent look ahead bias 
			if signal_data_extra.timeline[timeline_index] < signal_data_extra.start_date:
				continue
			instrument = signal_data_extra.instruments[instrument_index]
			the_date = signal_data_extra.timeline[timeline_index]
			direction = TradeDirection.SELL
			entry = signal_data_extra.bearish.entries[instrument_index,timeline_index]  
			entry_cut = signal_data_extra.bearish.entry_cuts[instrument_index,timeline_index]  
			take_profit_distance = signal_data_extra.bearish.take_profit_distances[instrument_index,timeline_index]
			stop_loss_distance = signal_data_extra.bearish.stop_loss_distances[instrument_index,timeline_index]
			ts = TradeSignal.from_full(the_date,instrument,strategy_ref,direction,entry,entry_cut,entry_expire,take_profit_distance,stop_loss_distance)
			trade_signals.append(ts)
		
		return trade_signals
	
	@deprecated
	def get_latest(self,age_limit : int = 240) -> List[TradeSignal]: #- for signals right now (short cut to not call for a backtest) 
		"""
		Generate a set of trade signals from this setup generator, returning only the latest trades per instrument
		
		Returns:
		-------
		list(TradeSignal) 
			A bunch of trade signals that were found from now up to age_limit minutes ago. 
		"""
		end_date = datetime.now() 
		start_date = datetime.now() - timedelta(minutes=age_limit) 
		start_date = start_date - timedelta(minutes=self.grace_period * self.timeframe)  #use grace period too to ensure quality signals 
		return self.get_setups(start_date,end_date)
	
	#method similar to indicator, but this should show a bunch of signals instead & run a separate drawing tool for the underlying indicators etc used 
	def draw_snapshot(self,trade_signalling_data : TradeSignallingData) -> chv.ChartView: #-add all chart views together. Consider what to do with start_date and end_date  
		"""
		Generate a ChartView object that can be plotted and looked at for inspecting the signals generated from this setup.
		All of  the indicators etc used should be plotted on this chart in this method. Start and end dates are needed to 
		gauge the chart size for the trade setup. If the trade signal is not provided, the chart should still be drawn with
		the underlying indicators and methods used.
		
		Parameters
		-----------
		start_date : datetime
			the start date to draw the chart from 
		end_date : datetime
			the end date to draw the chart from
		trade_signal : TradeSignal (optional)  
			the trade signal to draw on the chart (complete with the trading box!)
		
		Returns 	
		-------
		chv.ChartView  
			A chart view object of the drawing of this indicator 		"""
		raise NotImplementedError('This method must be overridden')  #--incorrect? this needs to return a chart view with the trading rectangle 
	
		
	#caching tool - not needed here
	@deprecated
	def get_initial_data(self,chartbase,mask=None,return_flat=None,return_np_candles=True):
		np_candles, timeline = chartbase._construct(candlesticks)
		init_dict = chartbase.get_initial_data(np_candles,mask,return_flat)
		if return_np_candles:
			return init_dict, np_candles
		return init_dict
		
	#this is in the wrong place 
	@deprecated
	def get_candlesticks(self,start_date,end_date,block=False,volumes=False,query_params={}):
		days_back = self.get_days_back(start_date,end_date)
		candle_result = None
		with Database(commit=False, cache=False) as cursor: 
			composer = DataComposer(cursor) #.candles(params).call()...
			composer.call('get_candles'+('_volumes_' if volumes else '_') + 'from_currencies',{'currencies':self.currencies,'this_date':end_date,'days_back':days_back})
			candle_result = composer.result(as_json=True)
		
		instruments = self.instruments 
		
		candles = None
		if volumes:
			candles = DataComposer.as_candles_volumes(candle_result,instruments)
		else:
			candles = DataComposer.as_candles(candle_result,instruments)
		
		if block:#turn into an npblock of numbers instead of a bunch of streams 
			candle_block = np.array([candles[instr] for instr in instruments if candles.get(instr)])
			instruments = [instr for instr in instruments if candles.get(instr)]
			candles = candle_block
		return candles, instruments

	
	
	@deprecated
	def get_candlestick_data(self,start_date,end_date,block=False,query_params={}):
		candles = []
		
		days_back = self.get_days_back(start_date,end_date) 
		
		instruments = self.instruments
		parameters = {
			'the_date':end_date,
			'instruments':self.instruments, #redundant but probably useful later when doing stocks 
			'currencies':self.currencies, #perhaps going to be a pain in the arse when doing stocks 
			'days_back':days_back,
			'chart_resolution':self.timeframe,
			'candle_offset':0
		}
		parameters.update(query_params)
		with Database(commit=False,cache=True) as cursor:
			with open('queries/candle_stick_selector.sql','r') as f:
				query = f.read()
				cursor.execute(query,parameters)
				candles = cursor.fetchcandles(instruments)
		
		if block:#turn into an npblock of numbers instead of a bunch of streams 
			candle_block = np.array([candles[instr] for instr in instruments if candles.get(instr)])
			instruments = [instr for instr in instruments if candles.get(instr)]
			candles = candle_block
		return candles, instruments
	





















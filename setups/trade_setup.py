## setups are trades that have been produced from signals from various sources. A TradeSetup class finds trades on a given date 
#that have a high probabily of winning based on their backtest results.  TradeSetup classes need to be backtestable 
#all implementations are in subclasses to this file - it is not possible to import indicator based stuff (circular import?)
from datetime import datetime,timedelta
from typing import Optional, List
import numpy as np
import scipy.signal
import scipy.optimize

import pdb

from utils import ListFileReader, Database, DataComposer
from utils import overrides#, deprecated
import charting.chart_viewer as chv 
from charting import candle_stick_functions as csf
#from charting.chart_pattern import ChartPattern - unable to import any indicator related stuff here 

from indicators.indicator import CandleSticks
from indicators.volatility import ATR

from setups.signal import *


bullish = 0 
bearish = 1

class TradeSetup:	#this not just an indicator - does not have calculate() etc. It is its own thing that finds trade signals 	
	
	timeframe = 15 #15 min chart by default
	instruments = [] #what trading instruments are we interested in?
	#criteria = [] #assume blank for now but we might be able to generalise the setup into criteria for use with auto calculating proquant style
	currencies = []
	grace_period = 10 #number of candles to go back to get an accurate reading at start_date
	
	_timeline = [] 
	_available_instruments = []
	
	def __init__(self,instruments,timeframe=15):
		self.timeframe = timeframe
		self.instruments = instruments
		lfr = ListFileReader()
		self.currencies = lfr.read('fx_pairs/currencies.txt')
	
	#by default, get the setups and turn to -1s and 1s?
	def detect(self, candlesticks : list, extra : Optional[TradeSignalDataExtra] = None) -> np.array:# - for AI - 0s and 1s or similar delivered from  get_setups()
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
	
	def get_entries(self,candlesticks,extra):
		candlesticksfnc = CandleSticks()
		np_candles = candlesticksfnc.calculate_multiple(candlesticks)
		result = np.full(np_candles.shape[0:2],None) #leave blank
		return result, result
	
	def get_tpsls(self,candlesticks, tpsl_tool=None, extra=None):
		if tpsl_tool is not None:
			return tpsl_tool.get_stops(extra)
		return self.get_tpsls_specific(candlesticks,extra)
		
	
	def get_tpsls_specific(self,candlesticks,extra=None):
		#if there is no tool, defaul to 3,2 ATR
		average_true_range = ATR()
		average_true_range_values = average_true_range.calculate_multiple(candlesticks) [:,:,0]
		tp_distances = 3 * average_true_range_values
		sl_distances = 2 * average_true_range_values
		return (tp_distances, tp_distances), (sl_distances, sl_distances)  # tp/sl can be differnt in different directions
		
	#def get_setups_and_confidence(self,start_date,end_date): # perhaps worth thinking about later
	
	
	def get_name(self):
		return self.__class__.__name__
	
	def get_setups(self,start_date : datetime, end_date : datetime) -> List[TradeSignal]:
		"""
		Generate a set of trade signals from this setup generator
		
		Parameters
		---------
		start_date : datetime 
			The date in which to start looking for setups 
		end_date : datetime 
			The date in which to end looking for setups 
		
		Returns:
		-------
		list(TradeSignal) 
			A bunch of trade signals that were found in the date range 
		"""
		extra = TradeSignalDataExtra()
		extra.start_date = start_date
		extra.end_date = end_date 
		extra.name = self.get_name()
		candlesticks, extra.instruments = self.get_candlesticks(start_date,end_date,block=True)
		extra.timeline = self.get_timeline(candlesticks)
		extra.signals = self.detect(candlesticks,extra=extra)
		extra.entries = self.get_entries(candlesticks,extra=extra)
		extra.take_profit_distances, extra.stop_loss_distances = self.get_tpsls(candlesticks,extra=extra)
		
		#asserts here? 
		
		return self.make_trade_signals(extra)
		
	
	def make_trade_signals(self,signal_data_extra):	
		trade_signals = []
		
		#export these? would be much faster for any further computation such as filtering...
		buy_coords = np.stack(np.where(signal_data_extra.signals[bullish]),axis=1)
		sell_coords = np.stack(np.where(signal_data_extra.signals[bearish]),axis=1)
		
		strategy_ref = signal_data_extra.name if signal_data_extra.name else 'Please set the name to this setup to something more meaningful!' 
		
		for (instrument_index,timeline_index) in buy_coords:
			if signal_data_extra.timeline[timeline_index] < signal_data_extra.start_date:
				continue
			instrument = signal_data_extra.instruments[instrument_index]
			the_date = signal_data_extra.timeline[timeline_index]
			direction = TradeDirection.BUY
			entry = signal_data_extra.entries[bullish][instrument_index,timeline_index]  
			take_profit_distance = signal_data_extra.take_profit_distances[bullish][instrument_index,timeline_index]
			stop_loss_distance = signal_data_extra.stop_loss_distances[bullish][instrument_index,timeline_index]
			
			ts = TradeSignal.from_full(the_date,instrument,strategy_ref,direction,entry,take_profit_distance,stop_loss_distance)
			trade_signals.append(ts)
		
		for (instrument_index,timeline_index) in sell_coords:
			if signal_data_extra.timeline[timeline_index] < signal_data_extra.start_date:
				continue
			instrument = signal_data_extra.instruments[instrument_index]
			the_date = signal_data_extra.timeline[timeline_index]
			direction = TradeDirection.SELL
			entry = signal_data_extra.entries[bearish][instrument_index,timeline_index]  
			take_profit_distance = signal_data_extra.take_profit_distances[bearish][instrument_index,timeline_index]
			stop_loss_distance = signal_data_extra.stop_loss_distances[bearish][instrument_index,timeline_index]
			
			ts = TradeSignal.from_full(the_date,instrument,strategy_ref,direction,entry,take_profit_distance,stop_loss_distance)
			trade_signals.append(ts)
		
		return trade_signals
		
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
	def draw_snapshot(self,start_date : datetime, end_date :datetime, trade_signal : TradeSignal = None) -> chv.ChartView: #-add all chart views together. Consider what to do with start_date and end_date  
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
	
	def get_days_back(self, start_date,end_date):
		mins_in_day = 1440 
		mins_before_start = self.timeframe * self.grace_period 
		delta = end_date - start_date
		days_back = delta.days + 1
		days_back += int(mins_before_start / mins_in_day) + 1
		days_back += int(delta.days/7) * 2   #buffer period 
		days_back += 2
		return days_back
	
	def get_timeline(self,candlesticks):
		return candlesticks[0,:,-1] #1d
		
		
	def get_initial_data(self,candlesticks,chartbase,mask=None,return_flat=None,return_np_candles=True):
		np_candles, timeline = chartbase._construct(candlesticks)
		init_dict = chartbase.get_initial_data(np_candles,mask,return_flat)
		if return_np_candles:
			return init_dict, np_candles
		return init_dict
		
	#this is in the wrong place 
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

	
	
	#@deprecated
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
	
	
	#def get_data() #take in instruments, start and end date, volumes or not, extra query params? ) -> fucking data like above -> return candlesticks and available_instruments
			
	#refactor into an ATR setup tool - deprecate
	def generate_using_atr(self,candlesticks,available_instruments,start_date,buy_signals,sell_signals,tp_factor=5,sl_factor=3):
		from indicators.volatility import ATR
		from indicators.indicator import Typical
		timeline = self.get_timeline(candlesticks)
		
		#need to set up the TP and SL values! 
		average_true_range = ATR() #use for setting TP and SL - perhaps pull this into its own function 
		average_true_range_values = average_true_range.calculate_multiple(candlesticks)
		
		tp_distances = tp_factor * average_true_range_values[:,:,0]
		sl_distances = sl_factor * average_true_range_values[:,:,0]

		typical = Typical()
		typical_values = typical.calculate_multiple(candlesticks) #could be used for entry?
		entry_prices = typical_values[:,:,0]
		
		trade_signals = []
		
		#export these? would be much faster for any further computation such as filtering...
		buy_coords = np.stack(np.where(buy_signals),axis=1)
		sell_coords = np.stack(np.where(sell_signals),axis=1)
		
		#now build the signals!  --could go in its own function?
		for (instrument_index,timeline_index) in buy_coords:
			if timeline[timeline_index] < start_date:
				continue
			the_date = timeline[timeline_index]
			instrument = available_instruments[instrument_index]
			strategy_ref = self.__class__.__name__
			direction = TradeDirection.BUY
			entry = None #consider entry_prices[instrument_index,timeline_index]
			take_profit_distance = tp_distances[instrument_index,timeline_index]
			stop_loss_distance = sl_distances[instrument_index,timeline_index]
			
			ts = TradeSignal.from_full(the_date,instrument,strategy_ref,direction,entry,take_profit_distance,stop_loss_distance)
			trade_signals.append(ts)
		
		for (instrument_index,timeline_index) in sell_coords:
			if timeline[timeline_index] < start_date:
				continue
			the_date = timeline[timeline_index]
			instrument = available_instruments[instrument_index]
			strategy_ref = self.__class__.__name__
			direction = TradeDirection.SELL
			entry = None #consider entry_prices[instrument_index,timeline_index]
			take_profit_distance = tp_distances[instrument_index,timeline_index]
			stop_loss_distance = sl_distances[instrument_index,timeline_index]
			
			ts = TradeSignal.from_full(the_date,instrument,strategy_ref,direction,entry,take_profit_distance,stop_loss_distance)
			trade_signals.append(ts)
		
		return trade_signals


#divergence tools - check this for lookahead bias 
class MomentumDivergenceTool:
	
	signal1 = None #usually typical price action
	signal2 = None #usually RSI or Stochastic etc 
	candlestick_smudge = 2
	order = 7 #arbitraty order - ensure peaks are far apart enough 
	hill_tolerance = 2 #if the peaks/troughs are more than this candles apart, do not include it in the divergence calculation 
	grace_period = 50
	
	
	def set_signals(self,signal1,signal2):
		assert len(signal1.shape) == 2, f"signal1 must be of shape n by t (2 dimensions). Dimensions = {len(signal1.shape)}"
		assert len(signal2.shape) == 2, f"signal1 must be of shape n by t (2 dimensions). Dimensions = {len(signal2.shape)}"
		self.signal1 = signal1
		self.signal2 = signal2 
	
	def detect(self):
		assert self.signal1 is not None, "signal 1 is none"
		assert self.signal2 is not None, "signal 2 is none"
		
		#bearish reversals
		#max1s = scipy.signal.argrelmax(self.signal1[:,self.grace_period:],axis=1,order=self.order) #all peaks - when they are increasing check rsi is decreasing. 
		#max2s = scipy.signal.argrelmax(self.signal2[:,self.grace_period:],axis=1,order=self.order) #use this as the anchor then find peaks between in signal1
		#max1s = max1s[0],max1s[1]+self.grace_period #add back the grace period 
		#max2s = [max2s[0],max2s[1]+self.grace_period]
		
		#find mapping from max2s to max1s 
		
		#if maxs on signal 1 increase, and maxs on signal 2 decrease, bearish
		#if mins on signal 1 decrease, and mins on signal 2 increase, bullish
		
		
		#naiive way to start with - might not need to be very advanced for this stage? 
		result_array = np.full(self.signal1.shape,np.nan) 
		for ii,(price_action,momentum) in enumerate(zip(self.signal1,self.signal2)):
			
			regions_of_interest = []
			
			max_args = scipy.signal.argrelmax(price_action[self.grace_period:],order=self.order)[0]
			max_args += self.grace_period
			momentum_maxs = [np.max(momentum[m-self.hill_tolerance:m+self.hill_tolerance+1]) for m in max_args] #get close maximums in rsi/stoch etc 
			price_action_maxs = price_action[(max_args,)]
			tpmx = list(zip(max_args,price_action_maxs,momentum_maxs))
			for (tpm1,tpm2) in zip(tpmx[:-1],tpmx[1:]):
				if tpm1[1] < tpm2[1] and tpm1[2] > tpm2[2]:
					regions_of_interest.append((tpm2[0]+self.hill_tolerance,-1)) #add bearish region of interest
			
			
			min_args = scipy.signal.argrelmin(price_action[self.grace_period:],order=self.order)[0]
			min_args += self.grace_period
			momentum_mins = [np.min(momentum[m-self.hill_tolerance:m+self.hill_tolerance+1]) for m in min_args]
			price_action_mins = price_action[(min_args,)]
			tpmn = list(zip(min_args,price_action_mins,momentum_mins))
			for tpm1,tpm2 in zip(tpmn[:-1],tpmn[1:]):
				if tpm1[1] > tpm2[1] and tpm1[2] < tpm2[2]:
					regions_of_interest.append((tpm2[0]+self.hill_tolerance,1)) #add bullish region of interest
			
			for (ti,d) in sorted(regions_of_interest,key=lambda tid : tid[0]):
				result_array[ii,ti:ti+self.candlestick_smudge] = d
			
		return result_array
		#pdb.set_trace()
		
		#print('check divergences')
	
	#def _naive_closest_map(self,nums1, nums2):	
	#	#scipy.optimize.linear_sum_assignment ? 
	##	for n in nums1: 
	#		wheres = (nums2 - self.hill_tolerance >= n) & (nums2 + self.hill_tolerance <= n)
	#		close2s = nums2[wheres]


#refactor - trade stop tools -- eg from ATR, std (something for harmonics) etc 



##from instruments, timeline, bull/bear signals, bull/bear entries, sl and tp distances create a list of trade setups 
#class EntryStopTool:
#
#	def GenerateTradeSetups(self,trade_signal_data):
#		assert trade_signal_data.stop_loss_distances is not None , "Stop loss required here" 
#	





















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


bullish = 0 
bearish = 1

def blank_result(trade_signalling_data):
	candlesticksfnc = CandleSticks()
	np_candles = candlesticksfnc.calculate_multiple(trade_signalling_data.candlesticks)
	result = np.full(np_candles.shape[0:2],None) #leave blank
	return result, result

#trade stop tools -- eg from ATR, std (something for harmonics) etc 
class StopTool:	
	
	def get_stops(self,tradesignallingdata):
		raise NotImplementedError('This method must be overridden')

#used as default 
class ATRStop(StopTool):
	
	tpm = 3
	slm = 2
	
	def __init__(self,take_profit_mult=3,stop_loss_mult=2):
		self.tpm = take_profit_mult 
		self.slm = stop_loss_mult
	
	def get_stops(self,trade_signalling_data):
		average_true_range = ATR()
		average_true_range_values = average_true_range.calculate_multiple(trade_signalling_data.candlesticks) [:,:,0]
		tp_distances = self.tpm * average_true_range_values
		sl_distances = self.slm * average_true_range_values
		return (tp_distances, tp_distances), (sl_distances, sl_distances) #a stop can be differnet values in diff directions 

#more available at the bottom of this file 

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
	
	def get_name(self):
		return self.__class__.__name__ if self.setup_name is None else self.setup_name 
	
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
	

#divergence tool - check this for lookahead bias 
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

#strategy tools? 
#tool used for when we only want to get signals when a detection has gone from 0 to 1 
class Zero2OneTool:
	
	@staticmethod   #might be able to make this without loops ?
	def markup(detected):	
		result = np.full(detected.shape,False) 
		for i,ins_detected in enumerate(detected):
			for j, (b, a) in enumerate(zip(ins_detected[:-1],ins_detected[1:])):
				if b == 0 and a == 1:
					result[i,j+1] = True 
		return result 

class CandleDataTool: 
	
	volumes = False 
	instruments = [] 
	chart_resolution = 15
	candle_offset = 0 
	end_date = datetime.datetime.now()
	grace_period = 50 
	start_date =  datetime.datetime.now()#startdate is 
	ask_candles = False
	backtesting = False #if true, get the bid AND the ask candles into np_candles 
	
	
	_candlesticks = None  #data to be read 
	_instruments = None 
	_np_candles = None 
	_timeline = None 
	
	_dbcursor = None 
	
	
	def __init__(self,cursor=None):
		self._dbcursor = cursor 
	
	def __get_days_back(self, grace_period): #n candlesticks to be useful and have RSI setup or whatever 
		mins_in_day = 1440 
		mins_before_start = self.chart_resolution * grace_period 
		delta = self.end_date - self.start_date
		days_back = delta.days + 1
		days_back += int(mins_before_start / mins_in_day) + 1
		days_back += int(delta.days/7) * 2   #buffer period 
		days_back += 2
		return days_back
	
	def read_data_from_currencies(self,currencies,grace_period = 50):  #add soon for from instruments 
		
		if self._dbcursor is not None:  #check is open?
			self.__call_db_read_data_from_currencies(currencies,grace_period,self._dbcursor)
		else:
			with Database(cache=False,commit=False) as cursor:
				self.__call_db_read_data_from_currencies(currencies,grace_period,cursor)
	
	def read_data_from_instruments(self,instruments,grace_period = 50):
	
		if self._dbcursor is not None:  #check is open?
			self.__call_db_read_data_from_instruments(instruments,grace_period,self._dbcursor)
		else:
			with Database(cache=False,commit=False) as cursor:
				self.__call_db_read_data_from_instruments(instruments,grace_period,cursor)
	
	def __call_db_read_data_from_currencies(self,currencies,grace_period,cursor):
		days_back = self.__get_days_back(grace_period)
		composer = DataComposer(cursor,True) #.candles(params).call()...
		if not self.backtesting:
			composer.call('get_candles'+('_volumes_' if self.volumes else '_') + 'from_currencies',{
				'currencies':currencies,
				'this_date':self.end_date,
				'days_back':days_back,
				'chart_resolution':self.chart_resolution,
				'candle_offset':self.candle_offset,
				'ask_candles':self.ask_candles
			})
			candle_result = composer.result(as_json=True)
			candlesticks = DataComposer.as_candles_volumes(candle_result,self.instruments) if self.volumes else DataComposer.as_candles(candle_result,self.instruments)
			self._candlesticks = np.array([candlesticks[instr] for instr in self.instruments if candlesticks.get(instr)]) #always used a block 
			self._instruments = [instr for instr in self.instruments if candlesticks.get(instr)]
			
			candlesticks_pre = CandleSticks()
			if self.volumes:
				candlesticks_pre.candle_type = CandleType.CANDLE_VOLUME
			self._np_candles = candlesticks_pre.calculate_multiple(self._candlesticks)
			self._timeline = candlesticks_pre.timeline[:,0] #this is a 2d array make it 1d
		else:
			composer.call('get_full_from_currencies',{
				'currencies':currencies,
				'this_date':self.end_date,
				'days_back':days_back,
				'chart_resolution':self.chart_resolution,
				'candle_offset':self.candle_offset,
			})
			candle_result = composer.result(as_json=True)
			candlesticks = DataComposer.as_full_candles(candle_result,self.instruments)
			self._candlesticks = np.array([candlesticks[instr] for instr in self.instruments if candlesticks.get(instr)]) #always used a block 
			self._instruments = [instr for instr in self.instruments if candlesticks.get(instr)]
			candlesticks_pre = CandleSticks()
			candlesticks_pre.candle_type = CandleType.FULL_CANDLE
			bidaskcandles = candlesticks_pre.calculate_multiple(self._candlesticks)
			bidcandles = bidaskcandles[:,:,0:4]
			askcandles = bidaskcandles[:,:,4:8]
			self._np_candles = np.stack([bidcandles,askcandles],axis=2)
			self._timeline = candlesticks_pre.timeline[:,0] #this is a 2d array make it 1d
	
	def __call_db_read_data_from_instruments(self,instruments,grace_period,cursor):
		days_back = self.__get_days_back(grace_period)
		composer = DataComposer(cursor,True) #.candles(params).call()...
		if self.backtesting:
			composer.call('get_candles'+('_volumes_' if self.volumes else '_') + 'from_instruments',{
				'instruments':instruments,
				'this_date':self.end_date,
				'days_back':days_back,
				'chart_resolution':self.chart_resolution,
				'candle_offset':self.candle_offset
			})
		
			candle_result = composer.result(as_json=True)
			candlesticks = DataComposer.as_candles_volumes(candle_result,instruments) if self.volumes else DataComposer.as_candles(candle_result,instruments)
			self._candlesticks = np.array([candlesticks[instr] for instr in instruments if candlesticks.get(instr)]) #always used a block 
			self._instruments = [instr for instr in instruments if candlesticks.get(instr)]
			candlesticks_pre = CandleSticks()
			if self.volumes:
				candlesticks_pre.candle_type = CandleType.CANDLE_VOLUME
			self._np_candles = candlesticks_pre.calculate_multiple(self._candlesticks)
			self._timeline = candlesticks_pre.timeline[:,0] #this is a 2d array make it 1d
		else:
			composer.call('get_full_from_instruments',{
				'instruments':instruments,
				'this_date':self.end_date,
				'days_back':days_back,
				'chart_resolution':self.chart_resolution,
				'candle_offset':self.candle_offset
			})
		
			candle_result = composer.result(as_json=True)
			candlesticks = DataComposer.as_full_candles(candle_result,instruments)
			self._candlesticks = np.array([candlesticks[instr] for instr in instruments if candlesticks.get(instr)]) #always used a block 
			self._instruments = [instr for instr in instruments if candlesticks.get(instr)]
			candlesticks_pre = CandleSticks()
			candlesticks_pre.candle_type = CandleType.FULL_CANDLE
			idaskcandles = candlesticks_pre.calculate_multiple(self._candlesticks)
			bidcandles = bidaskcandles[:,:,0:4]
			askcandles = bidaskcandles[:,:,4:8]
			self._np_candles = np.stack([bidcandles,askcandles],axis=2)
			self._timeline = candlesticks_pre.timeline[:,0] #this is a 2d array make it 1d
	
	#use this to get a fresh TradeSignallingData that can be put into any setup
	def get_trade_signalling_data(self):
		
		assert self._candlesticks is not None #these fail if the data has not been read 
		assert self._np_candles is not None
		assert self._timeline is not None
		
		tradesignallingdata = TradeSignallingData()
		tradesignallingdata.start_date = self.start_date
		tradesignallingdata.end_date = self.end_date
		tradesignallingdata.instruments = self._instruments
		tradesignallingdata.candlesticks = self._candlesticks 
		tradesignallingdata.np_candles = self._np_candles
		tradesignallingdata.timeline = self._timeline 
		tradesignallingdata.chart_resolution = self.chart_resolution
		tradesignallingdata.grace_period = self.grace_period
		return tradesignallingdata



#class SmudgeTool
#class DelayTool


class PipStop(StopTool): #needs to return an np array.. 
	
	tpp = 30
	slp = 20 
	pip_handler = None 
	
	def __init__(self,take_profit_pips=30,stop_loss_pips=20,pips_file=None): 
		self.tpp = take_profit_pips
		self.slp = stop_loss_pips
		self.pip_handler = PipHandler(pips_file) if pips_file is not None else PipHandler() 
	
	def get_stops(self,trade_signalling_data):
		#pip_distances = [self.pip_handler.pip_map[inst] for inst in instrument else np.nan]  #ideally?
		unitpiplen = [self.pip_handler.pips2move(inst,1) for inst in trade_signalling_data.instruments]
		
		assert trade_signalling_data.np_candles.shape[0] == len(unitpiplen)
		
		candle_stream_length = trade_signalling_data.np_candles.shape[1]
		pip_distances = np.transpose(np.array([unitpiplen]*candle_stream_length))
		
		return (pip_distances * self.tpp, pip_distances * self.tpp), (pip_distances * self.slp, pip_distances * self.slp)  




















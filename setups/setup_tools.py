

#file for containing anything that is useful when finding setups 
# eg, divergence, 
#		smudge forwards
#		delay 
#		stops
#		instrument data 
#		anything else

from datetime import datetime,timedelta
import time

from typing import Optional, List
import numpy as np

import scipy.signal

from setups.signal import * #anyting signal data related

from utils import ListFileReader, Database, DataComposer, PipHandler
from utils import overrides, deprecated

import charting.candle_stick_functions as csf
from indicators.indicator import *
from indicators.trend import *


bullish = 0 
bearish = 1


def _sliding_windows(source,period,filler=0):
	start_padding = np.full((source.shape[0],period-1),filler)
	source_padded = np.concatenate([start_padding,source],axis=1)
	source_windows = np.lib.stride_tricks.sliding_window_view(source_padded,window_shape=period,axis=1)
	return source_windows 

#put any common functions for setup tools into here 
class SetupTool:  #abc? 
	
	period = 5 
	
	def __init__(self,period=5):
		self.period = period
	
	def draw_annotations(self,setup_view, trade_setup, instrument_index, trigger_indexs):
		#not sure how this is going to work yet... 
		return None #blank if the tool does not have any annotations to draw (eg cross tool)
		
	
	def markup(self,values : np.array): #use a two array for div tool 
		pass


#smudge triggers forward in time so they are relevant for longer 
class SmudgeTool(SetupTool):

	smudge_length = 5 
	
	def __init__(self,smudge_length= 5):
		self.smudge_length = smudge_length
	
	#might be able to make this without loops 
	def markup(self,detected):	 
		detected_windows = _sliding_windows(detected,self.smudge_length)
		return np.any(detected_windows,axis=2)
	
#strategy tools? 
#tool used for when we only want to get signals when a detection has gone from 0 to 1 to remove duplicates & get earliest 
#class Zero2OneTool(SetupTool):
#	
#	@staticmethod   #might be able to make this without loops ?
#	def markup(detected):	
#		result = np.full(detected.shape,False) 
#		for i,ins_detected in enumerate(detected):
#			for j, (b, a) in enumerate(zip(ins_detected[:-1],ins_detected[1:])):
#				if b == 0 and a == 1:
#					result[i,j+1] = True 
#		return result 

#tool used for getting something that prev happened to be now (eg, previous close) 
class DelayTool(SetupTool):
	
	delay_length = 1 
	def markup(self,detected):
		return np.concatenate([np.full((detected.shape[0],self.delay_length),False),detected[:,:-self.delay_length]],axis=1)

class CandleLagTool(SetupTool):
	
	lag_length = 1
	def markup(self,candles):
		return np.concatenate([np.full((candles.shape[0],self.lag_length,candles.shape[2]),np.nan),candles[:,:-self.lag_length,:]],axis=1)
		
class ValueLagTool(SetupTool):
	
	lag_length = 1
	
	
	def __init__(self,lag_length):
		self.lag_length = lag_length
	
	def markup(self,values):
		return np.concatenate([np.full((values.shape[0],self.lag_length),np.nan),values[:,:-self.lag_length]],axis=1)
		

#class ExpireTool #if an underlying signal (one used within a trigger) has been showing too long, expire after x candles 

#tool used for when we only want to get signals when a detection has gone from 0 to 1 to remove duplicates & get earliest 
class Zero2OneTool(SetupTool):
	
	@staticmethod 
	def markup(detected):
		dt = DelayTool() 
		prev = dt.markup(detected)
		return (prev)


class ExtremesTool(SetupTool): 
	
	extreme_window = 20
	order = 3
	chart = 'candlesticks' #where to draw the extreme points per window 
	
	direction_dict = {
		'max':scipy.signal.argrelmax,
		'min':scipy.signal.argrelmin
	}
	
	
	def __init__(self, extreme_window = 20, order = 3, chart='candlesticks'):
		self.extreme_window = extreme_window
		self.order = order
	
	def markup(self, values, direction='max'):
		#data = np.concatenate([self.momentum,self.priceaction],axis=2)
		#maxminimas 
		value_windows = _sliding_windows(values,self.extreme_window,np.nan)
		funcname = direction.lower()
		scipyf = self.direction_dict.get(funcname)
		if scipyf is None:
			raise ValueError(f'Unknown direction "{funcname}". Must be "min" or "max"')
		value_extremes = self.get_extremes(value_windows,self.order,scipyf)
		return value_extremes 
	
	@overrides(SetupTool)#perhaps not?
	def draw_annotations(self,setup_view, trade_setup, instrument_index, trigger_indexs):
		pass 
	
	#turn a set of windows into a list of max peaks per window 
	@staticmethod
	def get_extremes(value_windows,order,scipy_func):
		
		indexer = scipy_func(value_windows,axis=2,order=order)
		values = value_windows[indexer]
		values = values[:,np.newaxis]
		
		locators = np.stack(list(indexer),axis=1)
		points = np.concatenate([locators,values],axis=1)
		
		number_windows = value_windows.shape[1] #n per channel! 
		window_numbers = (number_windows * points[:,0]) + points[:,1]
		window_numbers = window_numbers[:,np.newaxis]
		
		points_labelled = np.concatenate([window_numbers,points],axis=1)
		
		sort_by_window = points_labelled[:,0]
		points_labelled = points_labelled[sort_by_window.argsort()]
		
		duplicate_window_index = points_labelled[:,0].astype(np.int)
		window_coords, counts = np.unique(duplicate_window_index,return_counts=True)
		max_extremes = np.max(counts)
		
		max_window_len = np.max(points_labelled[:,3]) + 1
		sort_by_window_then_time = (points_labelled[:,0] * max_window_len) + points_labelled[:,3] 
		points_labelled = points_labelled[sort_by_window_then_time.argsort()] 
		
		window_map_top = np.repeat(np.arange(value_windows.shape[0]),number_windows)
		window_map_bottom = np.concatenate([np.arange(number_windows)]*value_windows.shape[0])
		window_map = np.stack([window_map_top,window_map_bottom],axis=0)
		
		cum_counts = np.concatenate([np.array([0]), np.cumsum(counts)[:-1]])
		neg_array = np.repeat(cum_counts,counts)
		buffers = np.repeat(np.max(counts) - counts,counts) #buffers push the xtremes forwards so nan values are first
		xtreme_index = np.arange(points_labelled.shape[0]) - neg_array + buffers
		
		xtreme_windows = np.full((value_windows.shape[0] * value_windows.shape[1], np.max(counts) ,2),np.nan)  #each extreme point is a (timeval,priceval,type)
		xtreme_windows[(duplicate_window_index,xtreme_index)] = points_labelled[:,3:]
		
		rebuilt = np.full(list(value_windows.shape[0:2]) + list(xtreme_windows.shape[1:]),np.nan)
		rebuilt[window_map[0],window_map[1]] = xtreme_windows
		
		#pdb.set_trace()
		return rebuilt #print('now what?')
	
#find peaks/lows in a momentum result and in the price action and determine if divergence is happening 
class DivTool(ExtremesTool):
	
	extreme_window = 15
	order = 3
	hidden = False #if true, use hidden divergence detection method instead 
	zero_cross = True #TODO if false, mark all divs that cross over the 0 line as false (undetect) (rsi will require scaling) 
	
	
	def __init__(self, extreme_window = 15, order = 3, zero_cross= True, chart='candlesticks', other_chart='rsi14'): #default draw on rsi charts 
		#super().__init__(self,*args,*kwargs)
		self.other_chart = other_chart #where to draw the other lines 
		self.zero_cross = zero_cross
	
	def _produce_extremes(self,values):
		#data = np.concatenate([self.momentum,self.priceaction],axis=2)
		#maxminimas 
		price_action, momentum = values  #price_action drawn on chart, momentum drawn on other_chart
		price_action_windows = _sliding_windows(price_action,self.extreme_window,np.nan)
		momentum_windows = _sliding_windows(momentum,self.extreme_window,np.nan)		
		
		#tic = time.time() 
		price_peaks = self.get_extremes(price_action_windows,self.order,scipy.signal.argrelmax)
		momentum_peaks = self.get_extremes(momentum_windows,self.order,scipy.signal.argrelmax)
		
		price_pits = self.get_extremes(price_action_windows,self.order,scipy.signal.argrelmin)
		momentum_pits = self.get_extremes(momentum_windows,self.order,scipy.signal.argrelmin)
		
		return (price_peaks, momentum_peaks), (price_pits, momentum_pits)  
	
	def _determine_divergence(self, price_peaks, momentum_peaks, price_pits, momentum_pits ):
		price_highs = price_peaks[:,:,-1,1] < price_peaks[:,:,-2,1] if self.hidden else price_peaks[:,:,-1,1] > price_peaks[:,:,-2,1]
		momentum_highs = momentum_peaks[:,:,-1,1] > momentum_peaks[:,:,-2,1] if self.hidden else momentum_peaks[:,:,-1,1] < momentum_peaks[:,:,-2,1]
		
		price_lows = price_pits[:,:,-1,1] > price_pits[:,:,-2,1] if self.hidden else price_pits[:,:,-1,1] < price_pits[:,:,-2,1]
		momentum_lows = momentum_pits[:,:,-1,1] < momentum_pits[:,:,-2,1] if self.hidden else momentum_pits[:,:,-1,1] > momentum_pits[:,:,-2,1]
		
		#check proximity to the current time of the window 
		price_peaks_proxi = price_peaks[:,:,-1,0] > (self.extreme_window - self.order)
		price_pits_proxi = price_pits[:,:,-1,0] > (self.extreme_window - self.order)
		
		#pdb.set_trace()
		
		bullish = price_lows & momentum_lows & price_pits_proxi
		bearish = price_highs & momentum_highs & price_peaks_proxi 
		
		return bullish, bearish 
		
	
	def markup(self, values):
		(price_peaks, momentum_peaks), (price_pits, momentum_pits) = self._produce_extremes(values)
		return self._determine_divergence(price_peaks, momentum_peaks, price_pits, momentum_pits)
		
		
		
	@overrides(SetupTool)
	def draw_annotations(self,setup_view, trade_setup, instrument_index, trigger_indexs):
		np_candles = setup_view.trade_signalling_data.np_candles
		
		primary_data = np_candles[:,:,csf.close]
		if self.chart != 'candlesticks':
			indicator_instance = trade_setup.indicator_bag.get(self.chart)
			if indicator_instance is not None: 
				primary_data = indicator_instance(np_candles)[:,:,0]
		
		secondary_data = np_candles[:,:,csf.close]
		if self.other_chart != 'candlesticks':
			indicator_instance = trade_setup.indicator_bag.get(self.other_chart)
			if indicator_instance is not None: 
				secondary_data = indicator_instance(np_candles)[:,:,0]
		
		
		(primary_peaks,secondary_peaks), (primary_pits, secondary_pits) = self._produce_extremes([primary_data,secondary_data])
		bullish, bearish = self._determine_divergence(primary_peaks,secondary_peaks, primary_pits, secondary_pits)
		
		#now decypher the results to draw using all the indexs and bullish,bearish 
		
	

#eg get macd and signal line, get their diff (macd - signal) then this.markup(diff) gives bullish and bearish crossovers 
class CrossTool:
	
	@staticmethod
	def markup(posneg):	
		prev = np.concatenate([np.full((posneg.shape[0],1), np.nan),posneg[:,:-1]],axis=1)
		bullish = (prev < 0) & (posneg > 0)
		bearish = (prev > 0) & (posneg < 0)
		return bullish, bearish

class TimeframeHike:
	pass

#trade stop tools -- eg from ATR, std (something for harmonics) etc 
class StopTool:	
	
	risk_reward_ratio = 1.5 #use for calculating TP when SL is known
	
	def __init__(self,risk_reward_ratio=1.5):
		self.risk_reward_ratio = risk_reward_ratio
		
	
	def get_stops(self,trade_signalling_data):
		raise NotImplementedError('This method must be overridden')

#used as default in TradeSetup
class ATRStop(StopTool):

	tpm = 3
	slm = 2

	def __init__(self,take_profit_mult=3,stop_loss_mult=2):
		self.tpm = take_profit_mult
		self.slm = stop_loss_mult

	def get_stops(self,trade_signalling_data):
		average_true_range = ATR()
		average_true_range_values = average_true_range(trade_signalling_data.candlesticks) [:,:,0]
		tp_distances = self.tpm * average_true_range_values
		sl_distances = self.slm * average_true_range_values
		return (tp_distances, tp_distances), (sl_distances, sl_distances) #a stop can be differnet values in diff directions



class PipStop(StopTool): 
	
	tpp = 30
	slp = 20 
	pip_handler = None 
	
	def __init__(self,take_profit_pips=30,stop_loss_pips=20,pips_file=None,**kwargs): 
		super().__init__(**kwargs)
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

class RollingExtremeStop(StopTool):
	
	period = 5 #last 5 candles 
	
	def get_stops(self,trade_signalling_data):
		window_h = RunningHigh()
		window_l = RunningLow()
		
		window_h.period = self.period
		window_l.period = self.period
		
		np_candles = trade_signalling_data.np_candles
		current_close = np_candles[:,:,csf.close]
		high_r = window_h._perform(np_candles)[:,:,0]
		lows_r = window_l._perform(np_candles)[:,:,0]
		
		bull_sl = np.abs(lows_r - current_close)
		bear_sl = np.abs(high_r - current_close)
		
		rrr = self.risk_reward_ratio
		
		return (bull_sl * rrr , bull_sl) , (bear_sl * rrr, bear_sl)
		
		
		
		
###
#class SlidingWindowTool


##for easy/better access to the data 
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
	
	
	def __init__(self,cursor=None,*args,**kwargs):
		#period doesn't matter here 
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






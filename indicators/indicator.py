
from collections import namedtuple
from collections.abc import Sequence 
from typing import Optional
from enum import Enum

import numpy as np 

import pdb

#an indicator takes in a list of candles (usually with an index) and outputs list of values. There may of course be more than 1 value per indicator output (eg bollinger bands)
#so a keys dictionary is used to hold names of each channel of the indicator output 

import charting.chart_viewer as chv #get all chart viewing elements so we can also draw nice charts. The view can  be "added" to a candlestick chart where appropriate
import charting.candle_stick_functions as csf
from trade_setup import TradeSignal, TradeDirection
from utils import overrides 


SetupCriteria = namedtuple('SetupCriteria','key directon value') #if "x exceeds y"? need to figure this out :) 

class Indicator:
	
	"""
	A tool for taking in candle streams and outputting indicator values. The tool is able to be used for setups and for drawing charts.
	
	
	Attributes:
		channel_keys : dict - A dict for holding the keys to the output results, for easier querying from outside the class.
		timeline : list[datetime] - A list of datetime indicating all the datetimes from the candles. An error is raised if multiple streams are out of sync
		period : int  - Length of the lookback period on the indicator. Ignored if an indicator does not use the lookback period, or has more than 1 lookback period
		candle_channel : int - the channel to use from the candle (open, high, low or close, close default)
	"""
	channel_keys = {} 
	timeline = [] 
	period = 20
	candle_channel = csf.close
	
	#this method does not need to be implemented since we can just perfrom a calculate_multiple! :) 
	def calculate(self,candle_stream : list,candle_stream_index : Optional[int]=-1) -> np.array:
		"""
		Calculates all of the indicator values for the given set of candles 
		
		Parameters
		----------
		candle_stream : list of candles
			The set of candles that we want to calculate on 
		candle_stream_index : int
			The end point at which we want to "pretend" that we can't see passed. If None, the whole candle stream is used
		
		Returns 	
		-------
		np.array of shape (len(candles),1,len(channel_keys))
			All of the indicator results, with the last dimension in the order of channel_keys
		"""
		result = self.calculate_multiple([candle_stream],candle_stream_index)
		return result[0]
	
	def calculate_multiple(self,candle_streams : list,candle_stream_index:Optional[int]=-1) -> np.array:
		"""
		Calculates all of the indicator values for all channelts of candles 
		
		Parameters
		----------
		candle_streams :  list of list of candles
			The multipler sets of candles that we want to calculate on
		candle_stream_index : int
			The end point at which we want to "pretend" that we can't see passed. If None, the whole candle stream is used
		
		Returns 	
		-------
		np.array of shape (len(candles),len(candle_streams),len(channel_keys))
			All of the indicator results, with the last dimension in the order of channel_keys
		"""
		candle_streams, self.timeline = self._construct(candle_streams,candle_stream_index)
		return self._perform(candle_streams)
		
	def draw_snapshot(self,candle_stream : list ,snapshot_index : int = -1) -> chv.ChartView:
		"""
		Generates a ChartView object from the given set of candles so the indicator can be plotted. It is up to the user of the 
		indicator to know if the indicator should be plotted on a candle stick chart or whether it should be placed below it
		
		Parameters
		----------
		candle_stream : list of candles 
			The set of candles that we want to calculate on
		snapshot_index : int (Optional)
			The end point at which we want to "pretend" that we can't see passed. If None, the whole candle stream is used
		
		Returns 	
		-------
		chv.ChartView  
			A chart view object of the drawing of this indicator 
		"""
		
		result = self.calculate(candle_stream,snapshot_index)
		
		style_paths = {}
		
		chart_view = chv.ChartView()
		
		for key in self.channel_keys:
			style = self.channel_styles[key]
			channel_key = self.channel_keys[key]
			y_axis = result[:,channel_key]
			x_axis = np.arange(0,y_axis.shape[0])
			path = [chv.Point(x,y) for x,y in zip(x_axis,y_axis)]
			style_paths.setdefault(style,[]).extend(path + [chv.Point(None,None)])
		
		for style, path in style_paths.items():
			chart_view.draw('price_action '+style+' path',path)
		
		return chart_view
		
	def generate_setups(self,criteria : SetupCriteria) -> list:
		"""
		Generates trade setups in the form of TradeSignal from the set of candles and from given criteria. 
		
		Parameters
		----------
		candle_stream : list of candles 
			The set of candles that we want to calculate on
		candle_stream_index : int
			The end point at which we want to "pretend" that we can't see passed. If None, the whole candle stream is used
		criteria : list of SetupCriteria
			The criteria required for there to be a setup at any point in the streams & the indicator resuts 
		
		Returns 	
		-------
		list of TradeSignal
			A list of trade signals that are able to be passed to a backtester  
		"""
		raise NotImplementedError('This method must be overridden') #not sure how to do criteria yet 
	
	def detect(self,criteria : SetupCriteria) -> np.array:
		"""
		Generates trade setups in the form of -1,0,1 from the set of candles and from given criteria. 
		This format can be useful for ai related work
		
		Parameters
		----------
		candle_stream : list of candles 
			The set of candles that we want to calculate on
		candle_stream_index : int
			The end point at which we want to "pretend" that we can't see passed. If None, the whole candle stream is used
		criteria : list of SetupCriteria
			The criteria required for there to be a setup at any point in the streams & the indicator resuts 
		
		Returns 	
		-------
		np.array of int
			A list of trade signals that are able to be passed to a backtester  
		"""
		raise NotImplementedError('This method must be overridden') #not sure how to do criteria yet 
	
	
	
	#Repeated code - already availalbe in CandleStickPattern and should be used from that! 
	#@staticmethod
	#def to_candles(data,instruments) -> list:
	#	"""
	#	A static method that processes data into a list of list of candles (list of candle streams) based on the instruments passed
	#	
	#	Parameters
	#	----------
	#	data : list of tuples
	#		The data from the database or wherever that is going to be processed
	#	instruments : list of str
	#		The set of instruments we want to extract from the instruments. 
	#	
	#	Returns
	#	-------
	#
	#	"""
	
	
	#helper functions for all subclasses - these dont need to be doc'ed 
	#pull out the times from the candle streams but raise an error if any of the timelines don't match
	def _construct(self,candle_streams,candle_stream_index):
		assert len(candle_streams) > 0, "There are no candle streams"
		np_candle_streams = np.array(candle_streams)
		datetime_values = np_candle_streams[:,:,-1].T
		timeline = datetime_values[:,0:1]		
		assert np.all(datetime_values == np.broadcast_to(timeline, datetime_values.shape)), "timelines are out of sync" 
		np_candles = np_candle_streams[:,:,:4].astype(np.float64)
		return np_candles, timeline 
	
	def _pad_start(self,np_candles): #this is needed to preserve the length of the streams
		np_nones = np.full((np_candles.shape[0],self.period-1,np_candles.shape[-1]),np.nan) 
		return np.concatenate([np_nones,np_candles],axis=1)
	
	def _perform(self,candle_data : np.array) -> np.array:
		raise NotImplementedError('This method must be overridden') 
	
	def _sliding_windows(self,np_candles):
		np_candles = self._pad_start(np_candles)
		np_closes = np_candles[:,:,self.candle_channel]
		return np.lib.stride_tricks.sliding_window_view(np_closes,window_shape=self.period,axis=1)	
		
	#def _produce_block(self,candle_streams):
	#	pass#produce convenient block of numbers from 

class SMA(Indicator):
	
	channel_keys = {'SMA':0}
	channel_styles = {'SMA':'keyinfo'}

	@overrides(Indicator)
	def _perform(self,candles):
		
		windows = self._sliding_windows(candles)
		return np.nanmean(windows,axis=2)[:,:,np.newaxis]
		
		
class STDDEV(SMA):

	channel_keys = {'STDDEV':0}
	channel_styles = {'STDDEV':'keyinfo'}
	
	@overrides(Indicator)
	def _perform(self,candles):
		windows = self._sliding_windows(candles)
		return np.nanstd(windows,axis=2)[:,:,np.newaxis]
	

	
class EMA(Indicator):

	channel_keys = {'EMA':0}
	channel_styles = {'EMA':'keyinfo'}
	
	@overrides(Indicator)
	def _perform(self,candles):
		closes = candles[:,:,self.candle_channel].T #get sequence_len x n_sequences vec
		alpha = 1.0 / self.period
		emas = []
		for i in range(0,self.period):
			emas.append(np.mean(closes[0:i+1,:],axis=0))  #when we dont have enough values, approx with SMA
		current_value = emas[-1]
		for i in range(self.period,closes.shape[0]):
			new_value = alpha*closes[i,:] + (1.0-alpha)* current_value
			emas.append(new_value)
			current_value = new_value
		return np.stack(emas,axis=1)[:,:,np.newaxis]
		

	
	
class BollingerBands(Indicator):
	channel_keys = {'MIDDLE':0,'UPPER':1,'LOWER':2} #etc
	channel_styles = {'MIDDLE':'bullish','UPPER':'bearish','LOWER':'bearish'}
	k = 2
	
	@overrides(Indicator)
	def _perform(self,candles):
		
		sma = SMA()
		std = STDDEV() 
		sma.period = self.period
		std.period = self.period
		
		smas = sma._perform(candles)
		stds = std._perform(candles)
		upper = smas + (self.k * stds)
		lower = smas - (self.k * stds)
		pdb.set_trace()
		return np.concatenate([smas,upper,lower],axis=2)

class MultiMovingAverage(Indicator):
	
	channel_keys = {'MMA':0}
	channel_styles = {'MMA':'neutral'}
	MA = SMA #ema
	repeats = 3 #triple simple moving average by default 
	
	@overrides(Indicator)
	def _perform(self,candles):
		ma = self.MA()
		ma.period = self.period
		ma.candle_channel = self.candle_channel
		
		result = ma._perform(candles)
		ma_key = ma.channel_keys[ma.channel_keys.keys()[0]]
		
		ma.candle_channel = ma_key
		for i in range(self.repeats-1):
			result = ma._perform(result)
		return result 
	
class MACD(Indicator):
		
	channel_keys = {'MACD':0,'SIGNAL':1,'DEVIATION':2,'DIRECTION':3} 
	channel_styles = {'MACD':'keyinfo','SIGNAL':'bearish','DEVIATION':'neutral','DIRECTION':'neutral'}#requires specialist draw_snapshot anyway
	slow_period = 26
	fast_period = 12
	signal_period = 9
	
	@overrides(Indicator)
	def _perform(self,candles):
		slow = EMA()
		fast = EMA()
		signal = EMA()
		
		slow.period = self.slow_period
		fast.period = self.fast_period
		signal.period = self.signal_period
		slow.candle_channel = self.candle_channel
		fast.candle_channel = self.candle_channel
		signal.candle_channel = signal.channel_keys['EMA']
		
		slow_ema = slow._perform(candles)
		fast_ema = fast._perform(candles)
		
		macd = fast_ema - slow_ema
		
		signal_line = signal._perform(macd)
		deviation = macd - signal_line
		direction = np.sign(deviation[:,1:] - deviation[:,:-1])
		
		pad_0s = np.zeros((direction.shape[0],1,1))
		direction = np.concatenate([pad_0s,direction],axis=1) #add 0 at start
		return np.concatenate([macd,signal_line,deviation,direction],axis=2)
		

class ATR(Indicator):
	
	channel_keys = {'ATR':0} 
	channel_styles = {'ATR':'keyinfo'}
	period = 14
	
	@overrides(Indicator)
	def _perform(self,candles):
		high = candles[:,1:,csf.high]
		low = candles[:,1:,csf.low]
		close = candles[:,1:,csf.close]
		prev_close = candles[:,:-1,csf.close]
		
		true_range_ = np.max(np.stack([high-low , np.abs(high - prev_close), np.abs(low - prev_close ) ],axis=2),axis=2)[:,:,np.newaxis]
		
		pad_beginning = true_range_[:,0:1,:]
		true_range = np.concatenate([pad_beginning,true_range_],axis=1)
		sma = SMA()
		sma.period = self.period
		sma.candle_channel = 0 
		average_true_range = sma._perform(true_range)
		return average_true_range
		
	

class KeltnerChannel(Indicator):
	channel_keys = {'MIDDLE':0, 'UPPER':1, 'LOWER':2} 
	channel_styles = {'MIDDLE':'keyinfo', 'UPPER':'neutral', 'LOWER':'neutral'}
	period = 20
	k = 2
	atr_period = 10
	
	@overrides(Indicator)
	def _perform(self,candles):
		atr = ATR() 
		atr.period = self.atr_period
		atr.candle_channel = 0
		average_true_range = atr._perform(candles)
		ema = EMA()
		ema.period = self.period
		ema.candle_channel = self.candle_channel
		middle = ema._perform(candles)
		upper = middle + (self.k * average_true_range)
		lower = middle - (self.k * average_true_range)
		return np.concatenate([middle,upper,lower],axis=2)
	
#our RSI is between 0 and 1 for easier use with NNs 
class RSI(Indicator):
	
	channel_keys = {'RSI':0, 'OVERBOUGHT':1, 'OVERSOLD':2} 
	channel_styles = {'RSI':'bearish', 'OVERBOUGHT':'neutral', 'OVERSOLD':'neutral'}
	
	overbought = 0.8
	oversold = 0.2 
	
	period = 14
	
	@overrides(Indicator)
	def _perform(self,candles):
		closes = candles[:,:,self.candle_channel]
		rate_of_change = closes[:,1:] - closes[:,:-1]
		zeros = np.zeros(rate_of_change.shape)
		up_moves = np.maximum(rate_of_change,0)
		down_moves = np.abs(np.minimum(rate_of_change,0))
		ema = EMA()
		ema.period = self.period
		ema.candle_channel = 0 
		ave_up_move = ema._perform(up_moves[:,:,np.newaxis])
		ave_down_move = ema._perform(down_moves[:,:,np.newaxis])
		rsi = 1.0 - (1.0 / (1.0 + (ave_up_move / ave_down_move)))
		rsi[np.isnan(rsi)] = 1.0
		return np.concatenate([rsi,np.full(rsi.shape,self.overbought),np.full(rsi.shape,self.oversold)],axis=2)

	
	
class StochasticOscillator(Indicator):
	pass 

class MassIndex(Indicator):
	pass
	
class ADI(Indicator):
	pass

class Awesome(Indicator):
	pass
	












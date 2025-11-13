
from collections import namedtuple
from typing import Optional, List, Union
from enum import Enum

import numpy as np 

import pdb

#an indicator takes in a list of candles (usually with an index) and outputs list of values. There may of course be more than 1 value per indicator output (eg bollinger bands)
#so a keys dictionary is used to hold names of each channel of the indicator output 
#possibly organise/split this file into oscillators, volatility, trend followers and trend reversals ?
import charting.chart_viewer as chv #get all chart viewing elements so we can also draw nice charts. The view can  be "added" to a candlestick chart where appropriate
import charting.candle_stick_functions as csf
from setups.signal import TradeSignal, TradeDirection, SetupCriteria
from utils import overrides 

class CandleType(Enum):
	CANDLE = 0
	VOLUME = 1
	CANDLE_VOLUME = 2
	FULL_CANDLE = 3

class Indicator:
	
	"""
	A tool for taking in candle streams and outputting indicator values. The tool is able to be used for setups and for drawing charts.
	
	
	Attributes:
		channel_keys : dict - A dict for holding the keys to the output results, for easier querying from outside the class.
		timeline : list[datetime] - A list of datetime indicating all the datetimes from the candles. An error is raised if multiple streams are out of sync
		period : int  - Length of the lookback period on the indicator. Ignored if an indicator does not use the lookback period, or has more than 1 lookback period
		candle_channel : int - the channel to use from the candle (open, high, low or close, close default)
		candle_sticks : bool - True if the indicator is able to be plotted on top of a candlestick chart (if false, it should be plotted below)
	"""
	channel_keys = {} 
	timeline = [] 
	instrument_names = []
	period = 20
	candle_channel = csf.close
	_channel_str = 'close'
	candle_sticks = False
	candle_type = CandleType.CANDLE 
	time_viewing_index = -1 
	
	candle_type_dimension_map = {
		CandleType.CANDLE : 4,
		CandleType.VOLUME : 2,
		CandleType.CANDLE_VOLUME : 6,
		CandleType.FULL_CANDLE: 10
	}
	_candle_channels = {
		'open':csf.open,
		'high':csf.high,
		'low':csf.low,
		'close':csf.close
	}
	
	def __init__(self, channel='close', candle_type=CandleType.CANDLE): 
		self.candle_type = candle_type
		self._set_candle_channel(channel)
	
	def _set_candle_channel(self,channel):
		if type(channel) == str:
			channel = channel.lower().strip()
			if channel not in self._candle_channels:
				raise ValueError(f"{channel} is not a recognised candle channel")
			self.candle_channel = self._candle_channels[channel]
			self._channel_str = channel 
		elif type(channel) == int:
			self.candle_channel = channel 
			self._channel_str = 'col'+str(channel)
		else:
			raise ValueError(f"{channel} not a suitable candle channel")
	
	
	def pass_instrument_names(self,_instrument_names):
		self.instrument_names = _instrument_names
	
	##this method does not need to be implemented since we can just perfrom a calculate_multiple! :) 
	#def calculate(self,candle_stream : list,candle_stream_index : Optional[int]=-1) -> np.array:
	#	"""
	#	Calculates all of the indicator values for the given set of candles 
	#	
	#	Parameters
	#	----------
	#	candle_stream : list of candles
	#		The set of candles that we want to calculate on 
	#	candle_stream_index : int
	#		The end point at which we want to "pretend" that we can't see passed. If None, the whole candle stream is used
	#	
	#	Returns 	
	#	-------
	#	np.array of shape (len(candles),1,len(channel_keys))
	#		All of the indicator results, with the last dimension in the order of channel_keys
	#	"""
	#	result = self.calculate_multiple([candle_stream],candle_stream_index)
	#	return result[0]
	#
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
	
	#refactor to use np_candles instead 
	def draw_snapshot(self,np_candles : np.array, instrument_index : int, snapshot_index : Union[int , np.array] = -1) -> chv.ChartView:
		"""
		Generates a ChartView object from the given set of candles so the indicator can be plotted. 
		
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
		#candle_stream = np_candles[instrument_index]
		result_multi = self._perform(np_candles)
		result = result_multi[instrument_index]
		
		style_paths = {}
		
		chart_view = chv.ChartView()
		
		for key in self.channel_styles:
			style = self.channel_styles[key]
			channel_key = self.channel_keys[key]
			y_axis = result[:,channel_key]
			x_axis = np.arange(0,y_axis.shape[0])
			path = [chv.Point(x,y) for x,y in zip(x_axis,y_axis)]
			style_paths.setdefault(style,[]).extend(path + [chv.Point(None,None)])
		
		for style, path in style_paths.items():
			chart_view.draw('price_action '+style+' path',path)
		
		return chart_view
		
	#def generate_setups(self,criteria : list) -> list:
	#	"""
	#	Generates trade setups in the form of TradeSignal from the set of candles and from given criteria. 
	#	
	#	Parameters
	#	----------
	#	candle_stream : list of candles 
	#		The set of candles that we want to calculate on
	#	candle_stream_index : int
	#		The end point at which we want to "pretend" that we can't see passed. If None, the whole candle stream is used
	#	criteria : list of SetupCriteria
	#		The criteria required for there to be a setup at any point in the streams & the indicator resuts 
	#	
	#	Returns 	
	#	-------
	#	list of TradeSignal
	#		A list of trade signals that are able to be passed to a backtester  
	#	"""
	#	raise NotImplementedError('This method must be overridden') #not sure how to do criteria yet 
	#
	def detect(self,criteria : list=[]) -> np.array:
		"""
		Generates trade setups in the form of -1,0,1 from the set of candles and from given criteria. 
		This format can be useful for ai related work
		
		Parameters
		----------
		candle_stream : list of candles 
			The set of candles that we want to calculate on
		candle_stream_index : int
			The end point at which we want to "pretend" that we can't see passed. If None, the whole candle stream is used
		criteria : list of SetupCriteria (Optional)
			The criteria required for there to be a setup at any point in the streams & the indicator resuts. If a blank list is returned, all bullish and bearish setups are returned
		
		Returns 	
		-------
		np.array of int
			A list of trade signals that are able to be passed to a backtester  
		"""
		raise NotImplementedError('This method must be overridden') #not sure how to do criteria yet 
	#
	#
	
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
	
	
	#helper functions for all subclasses - these dont need to be doc'ed - but they do need to be moved 
	#pull out the times from the candle streams but raise an error if any of the timelines don't match
	def _construct(self,candle_streams,candle_stream_index=-1):
		assert len(candle_streams) > 0, "There are no candle streams"
		np_candle_streams = np.array(candle_streams)
		datetime_values = np_candle_streams[:,:,-1].T
		timeline = datetime_values[:,0:1]
		if not np.all(datetime_values == np.broadcast_to(timeline, datetime_values.shape)):
			pdb.set_trace()
		assert np.all(datetime_values == np.broadcast_to(timeline, datetime_values.shape)), "timelines are out of sync - try calculate_multiple" 
		candle_dim = self.candle_type_dimension_map[self.candle_type]
		#pdb.set_trace()
		np_candles = np_candle_streams[:,:,:candle_dim].astype(np.float64)
		return np_candles, timeline 
	
	def _pad_start(self,np_candles,period): #this is needed to preserve the length of the streams
		np_nones = np.full((np_candles.shape[0],period-1,np_candles.shape[-1]),np.nan) 
		return np.concatenate([np_nones,np_candles],axis=1)
	
	def _perform(self,candle_data : np.array) -> np.array:
		raise NotImplementedError('This method must be overridden') 
	
	def _sliding_windows(self,np_candles,period=None):
		if period is None:
			period = self.period
		np_candles = self._pad_start(np_candles,period)
		return np.lib.stride_tricks.sliding_window_view(np_candles,window_shape=period,axis=1)	
	
	def __call__(self,*args,**kwargs): #absorb args
		return self._perform(*args,**kwargs)
	
	#TODO: doc. 
	#of format RSI(period=14,overbought=0.8,oversold=0.2) 
	def title(self):
		raise NotImplementedError('This method must be overridden')
		return f"Indicator( error? )"

#some very simple indicator like objects for the basics 
class Typical(Indicator):
	
	channel_keys = {'TYPICAL':0} 
	channel_styles = {'TYPICAL':'neutral'}
	candle_sticks = True
	
	@overrides(Indicator)
	def _perform(self,candles):
		typical = (candles[:,:,csf.high] + candles[:,:,csf.low] + candles[:,:,csf.close]) / 3.0
		return typical[:,:,np.newaxis]
	
	@overrides(Indicator)
	def title(self):
		return f"{self.__class__.__name__} "
	


class Diff(Indicator):	
	
	channel_keys = {'OPEN':0,'HIGH':1,'LOW':2,'CLOSE':3} 
	channel_styles = {'OPEN':'neutral','HIGH':'neutral','LOW':'neutral','CLOSE':'neutral'}
	candle_sticks = False
	
	diff = 1 #delta?
	
	def __init__(self, diff=1, *args, **kwargs):
		self.diff = diff
		super().__init__(*args, **kwargs)
	
	@overrides(Indicator)
	def _perform(self,candles):	
		later = candles[:,self.diff:,:]
		earlier = candles[:,:-self.diff,:]
		padshape = (later.shape[0],self.diff,later.shape[2])
		return np.concatenate([np.zeros(padshape), later - earlier],axis=1)
	
	@overrides(Indicator)
	def title(self):
		return f"{self.__class__.__name__} ( {self.diff} ) "

class Change(Indicator):
	channel_keys = {'OPEN':0,'HIGH':1,'LOW':2,'CLOSE':3} 
	channel_styles = {'OPEN':'neutral','HIGH':'neutral','LOW':'neutral','CLOSE':'neutral'}
	candle_sticks = False
	
	diff = 1
	
	def __init__(self, diff=1, *args, **kwargs):#?
		self.diff = diff
		super().__init__(*args, **kwargs)
	
	@overrides(Indicator)
	def _perform(self,candles):	
		later = candles[:,self.diff:,:]
		earlier = candles[:,:-self.diff,:]
		padshape = (later.shape[0],self.diff,later.shape[2])
		return np.concatenate([np.zeros(padshape), (later - earlier) / np.abs(earlier)],axis=1)
	
	@overrides(Indicator)
	def title(self):
		return f"{self.__class__.__name__} ( {self.diff} )"

#these are actually provided in a toolkit with keras? - consider candle bounded 
class Bounded(Indicator):
	
	channel_keys = {'NORMED':0,'HIGHEST':1,'LOWEST':2} 
	channel_styles = {'NORMED':'neutral','HIGHEST':'bearish','LOWEST':'bullish'}
	candle_sticks = False

	period = 50
	
	def __init__(self, period=50, *args, **kwargs):#?
		self.period = period
		super().__init__(*args, **kwargs)
	
	@overrides(Indicator)
	def _perform(self,candles):
		values = candles[:,:,self.candle_channel,np.newaxis]
		windows = self._sliding_windows(values)
		maxs = np.nanmax(windows,axis=3)
		mins = np.nanmin(windows,axis=3)
		normed = (values - mins) / (maxs - mins)
		normed[np.isnan(normed)] = 0
		return np.concatenate([normed,maxs,mins],axis=2)
	
	@overrides(Indicator)
	def title(self):
		return f"{self.__class__.__name__}( {self.period}, {self._channel_str}) "
	
#class Standardisation(Indicator): 

class HeikinAshi(Indicator):  #more of a translator than indicator!
	
	channel_keys = None  #this data will override the candle stick data!
	channel_styles = None 
	candle_sticks = True #Damn straight! they ARE candlesticks. 
	
	@overrides(Indicator)
	def _perform(self,np_candles):
		closes = np.mean(np_candles[:,:,:],axis=2)
		#opens = np.concatenate([np.full((np_candles.shape[0],1),np.nan),np.mean(np_candles[:,:-1,[csf.open,csf.close]],axis=2)],axis=1) #WRONG
		opens = np.full(np_candles.shape[0:2],np.nan)
		opens[:,0] = np.mean(np_candles[:,0,[csf.high,csf.low]],axis=1) #use first actual as seed open 
		for i in range(1,np_candles.shape[1]): #(TODO figure how to do this without loop? fast though prob not worth it)
			opens[:,i] = (closes[:,i-1] + opens[:,i-1]) / 2
		
		highs = np.nanmax(np.stack([np_candles[:,:,csf.high],opens,closes],axis=2),axis=2)
		lows = np.nanmin(np.stack([np_candles[:,:,csf.low],opens,closes],axis=2),axis=2)
		times = np.array([self.timeline[:,0]] * np_candles.shape[0])
		return np.stack([opens,highs,lows,closes,times],axis=2)
	
	@overrides(Indicator)
	def draw_snapshot(self,np_candles,instrument_index,snapshot_index):
		raise NotImplementedError("Use ChartView.draw_candlesticks()") #to prevent 2 sets of candles being drawn on the same chart
	
	@overrides(Indicator)
	def title(self):
		return f"{self.__class__.__name__} "
	
	
#blank indicator returning the candlesticks 
class CandleSticks(Indicator):

	channel_keys = None  #this data will override the candle stick data!
	channel_styles = None 
	candle_sticks = True #Damn straight! they ARE candlesticks. 
	
	@overrides(Indicator)
	def _perform(self,np_candles):
		return np_candles 
	
	@overrides(Indicator)
	def draw_snapshot(self,np_candles,instrument_index,snapshot_index):
		raise NotImplementedError("Use ChartView.draw_candlesticks()") #to prevent 2 sets of candles being drawn on the same chart
	
	@overrides(Indicator)
	def title(self):
		return f"{self.__class__.__name__} "
	
class RunningHigh(Indicator):
	
	channel_keys = {'HIGH':0}	#this data will override the candle stick data!
	channel_styles = {'HIGH':'bearish'} 
	candle_sticks = True
	
	period = 14
	
	def __init__(self, period=14, channel='high', *args, **kwargs):#?
		self.period = period
		super().__init__(*args, **kwargs)
	
	@overrides(Indicator)
	def _perform(self,np_candles):
		highs = np_candles[:,:,self.candle_channel,np.newaxis]
		windows = self._sliding_windows(highs)
		running_highs = np.nanmax(windows,axis=3)
		return running_highs
		
	@overrides(Indicator)
	def title(self):
		return f"{self.__class__.__name__} ( {self.period}, {self._channel_str} )"

class RunningLow(Indicator):
	
	channel_keys = {'LOW':0}	#this data will override the candle stick data!
	channel_styles = {'LOW':'bullish'} 
	candle_sticks = True
	
	period = 14
	
	def __init__(self, period=14, channel='low', *args, **kwargs):#?
		self.period = period
		super().__init__(*args, **kwargs)
	
	
	@overrides(Indicator)
	def _perform(self,np_candles):
		lows = np_candles[:,:,self.candle_channel,np.newaxis]
		windows = self._sliding_windows(lows)
		running_lows = np.nanmin(windows,axis=3)
		return running_lows
	
	@overrides(Indicator)
	def title(self):
		return f"{self.__class__.__name__} ( {self.period}, {self._channel_str} )"




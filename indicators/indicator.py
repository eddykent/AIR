
from collections import namedtuple
from typing import Optional, List

import numpy as np 

import pdb

#an indicator takes in a list of candles (usually with an index) and outputs list of values. There may of course be more than 1 value per indicator output (eg bollinger bands)
#so a keys dictionary is used to hold names of each channel of the indicator output 
#possibly organise/split this file into oscillators, volatility, trend followers and trend reversals ?
import charting.chart_viewer as chv #get all chart viewing elements so we can also draw nice charts. The view can  be "added" to a candlestick chart where appropriate
import charting.candle_stick_functions as csf
from setups.trade_setup import TradeSignal, TradeDirection, SetupCriteria
from utils import overrides 


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
	candle_sticks = False
	
	def pass_instrument_names(self,_instrument_names):
		self.instrument_names = _instrument_names
	
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
		
		result = self.calculate(candle_stream,snapshot_index)
		
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
		
	def generate_setups(self,criteria : list) -> list:
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
		assert np.all(datetime_values == np.broadcast_to(timeline, datetime_values.shape)), "timelines are out of sync - try calculate_multiple" 
		np_candles = np_candle_streams[:,:,:4].astype(np.float64)
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
		

	

#some very simple indicator like objects for the basics 
class Typical(Indicator):
	
	channel_keys = {'TYPICAL':0} 
	channel_styles = {'TYPICAL':'neutral'}
	candle_sticks = True
	
	def _perform(self,candles):
		typical = (candles[:,:,csf.high] + candles[:,:,csf.low] + candles[:,:,csf.close]) / 3.0
		return typical[:,:,np.newaxis]


class Diff(Indicator):	
	
	channel_keys = {'OPEN':0,'HIGH':1,'LOW':2,'CLOSE':3} 
	channel_styles = {'OPEN':'neutral','HIGH':'neutral','LOW':'neutral','CLOSE':'neutral'}
	candle_sticks = False
	
	diff = 1
	
	def _perform(self,candles):	
		later = candles[:,self.diff:,:]
		earlier = candles[:,:-self.diff,:]
		padshape = (later.shape[0],self.diff,later.shape[2])
		return np.concatenate([np.zeros(padshape), later - earlier],axis=1)

#these are actually provided in a toolkit with keras? 
#class Normalisation(Indicatior):
#	
#	channel_keys = {'NORMED':0,'HIGHEST':1,'LOWEST':2} 
#	channel_styles = {'NORMED':'neutral','HIGHEST':'bearish','LOWEST':'bullish'}
#	candle_sticks = False
#
#	normalisation_window = 50
#	candle_channel = csf.close
#	
#	def _perform(self,candles):
#		pass
#	
#class Standardisation(Indicator):
	



















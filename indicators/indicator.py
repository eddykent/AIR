
from collections import namedtuple
from typing import Optional, List
from enum import Enum

import numpy as np 

import pdb

#an indicator takes in a list of candles (usually with an index) and outputs list of values. There may of course be more than 1 value per indicator output (eg bollinger bands)
#so a keys dictionary is used to hold names of each channel of the indicator output 
#possibly organise/split this file into oscillators, volatility, trend followers and trend reversals ?
import charting.chart_viewer as chv #get all chart viewing elements so we can also draw nice charts. The view can  be "added" to a candlestick chart where appropriate
import charting.candle_stick_functions as csf
from setups import TradeSignal, TradeDirection, SetupCriteria
from utils import overrides 


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
	instrument_names = []
	period = 20
	candle_channel = csf.close
	
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
		
		
	#def _produce_block(self,candle_streams):
	#	pass#produce convenient block of numbers from 

class SMA(Indicator):
	
	channel_keys = {'SMA':0}
	channel_styles = {'SMA':'bearish'}

	@overrides(Indicator)
	def _perform(self,candles):
		windows = self._sliding_windows(candles)[:,:,self.candle_channel,:] #select the correct candle channel
		return np.nanmean(windows,axis=2)[:,:,np.newaxis]
		
		
class STDDEV(SMA):

	channel_keys = {'STDDEV':0}
	channel_styles = {'STDDEV':'keyinfo'}
	
	@overrides(Indicator)
	def _perform(self,candles):
		windows = self._sliding_windows(candles)[:,:,self.candle_channel,:]
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
	
	
class Stochastic(Indicator):
	
	channel_keys = {'K':0, 'D':1, 'SLOW_K':1, 'SLOW_D':2, 'OVERBOUGHT':3, 'OVERSOLD':4}  #d = slow_k
	channel_styles = {'K':'keyinfo', 'SLOW_K':'bullish', 'SLOW_D':'bearish', 'OVERBOUGHT':'neutral', 'OVERSOLD':'neutral'}
	
	period = 14	
	slow_k_period = 3
	d_period = 3
	
	overbought = 0.8
	oversold = 0.2
	
	@overrides(Indicator)
	def _perform(self,candles):
		closes = candles[:,:,csf.close]
		windows = self._sliding_windows(candles)
		highs = np.nanmax(windows[:,:,csf.high,:],axis=2)
		lows = np.nanmin(windows[:,:,csf.low,:],axis=2)
		
		percent_k = (closes - lows) / (highs - lows) #without percent
		ema = EMA()
		ema.period = self.slow_k_period
		ema.candle_channel = 0
		
		percent_k = percent_k[:,:,np.newaxis]
		slow_k = ema._perform(percent_k)
		ema.period = self.d_period
		percent_d = ema._perform(slow_k)
		
		return np.concatenate([percent_k,slow_k,percent_d],axis=2)

class StochasticRSI(Indicator):
	
	period = 14
	channel_keys = {'STOCHASTIC_RSI':0, 'OVERBOUGHT':1, 'OVERSOLD':2}
	channel_styles = {'STOCHASTIC_RSI':'bearish', 'OVERBOUGHT':'neutral', 'OVERSOLD':'neutral'}
	
	@overrides(Indicator)
	def _perform(self,candles):
		rsi = RSI()
		rsi_result = rsi._perform(candles)
		
		rsi_windows = self._sliding_windows(rsi_result)[:,:,rsi.channel_keys['RSI'],:] #confirm shape = (28, 346, 14)?
		rsi_maxs = np.nanmax(rsi_windows,axis=2)
		rsi_mins = np.nanmin(rsi_windows,axis=2)
		stochastic_rsi = (rsi_result[:,:,rsi.channel_keys['RSI']] - rsi_mins) / (rsi_maxs - rsi_mins)
		stochastic_rsi[np.isnan(stochastic_rsi)] = 0.5 
		stochastic_rsi = stochastic_rsi[:,:,np.newaxis]
		overbought = np.full(stochastic_rsi.shape,self.overbought)
		oversold = np.full(stochastic_rsi.shape,self.oversold)
		return np.concatenate([stochastic_rsi,overbought,oversold],axis=2)
		
		
class MassIndex(Indicator):
	
	period = 9
	channel_keys = {'MASS':0}
	channel_styles = {'MASS':'neutral'}
	mass_period = 25
	
	@overrides(Indicator)
	def _perform(self,candles):
		diffs = candles[:,:,csf.high] - candles[:,:,csf.low]
		ema = EMA()
		ema.period = self.period 
		ema.candle_channel = 0
		ema_1 = ema._perform(diffs[:,:,np.newaxis])
		ema_2 = ema._perform(ema_1)
		ratios = ema_1 / ema_2
		mass = np.nansum(self._sliding_windows(ratios)[:,:,0,:],axis=2)
		return mass[:,:,np.newaxis]
		
#this is buggy - ADX should not range to 100 and pdi and ndi should not go below 0 
class ADX(Indicator):
	
	period = 14
	channel_keys = {'ADX':0,'PDI':1,'NDI':2}
	channel_styles = {'ADX':'keyinfo','PDI':'bullish','NDI':'bearish'}
	
	@overrides(Indicator)
	def _perform(self,candles):
		atr = ATR()
		ema = EMA()
		atr.period = self.period
		ema.period = self.period
		ema.candle_channel = 0
		
		atrs = atr._perform(candles)
		
		upmoves = candles[:,1:,csf.high] - candles[:,:-1,csf.high]
		downmoves = candles[:,:-1,csf.low] - candles[:,1:,csf.low]
		
		#pdm and ndm have 1 less - so repeat first value
		upmoves = np.concatenate([upmoves[:,0:1],upmoves],axis=1)
		downmoves = np.concatenate([downmoves[:,0:1],downmoves],axis=1)
		
		pdm = np.copy(upmoves)
		ndm = np.copy(downmoves)
		
		pdm[pdm < 0] = 0
		ndm[ndm < 0] - 0
		
		pdm[np.where(upmoves < downmoves)] = 0  #fill with 0s at points where pdm < ndm or pdm is 0
		ndm[np.where(downmoves < upmoves)] = 0
		
		
		pdi = ema._perform(pdm[:,:,np.newaxis]) / atrs
		ndi = ema._perform(ndm[:,:,np.newaxis]) / atrs
		di = np.abs((pdi - ndi) / (pdi + ndi))
		
		pdi = pdi * 100
		ndi = ndi * 100
		
		adx = ema._perform(di) * 100
		return np.concatenate([adx,pdi,ndi],axis=2)
		

class Awesome(Indicator):
	
	fast_period = 5
	slow_period = 24
	channel_keys = {'AWESOME':0}
	channel_styles = {'AWESOME':'keyinfo'}
	
	@overrides(Indicator)
	def _perform(self,candles):
		medians = (candles[:,:,csf.high] + candles[:,:,csf.low]) / 2.0
		medians = medians[:,:,np.newaxis]
		sma = SMA()
		sma.candle_channel = 0
		sma.period = self.fast_period
		fast_sma = sma._perform(medians)
		sma.period = self.slow_period
		slow_sma = sma._perform(medians)
		return fast_sma - slow_sma


class Accelerator(Indicator):

	fast_period = 5
	slow_period = 24
	period = 5
	channel_keys = {'ACCELERATOR':0}
	channel_styles = {'ACCELERATOR':'keyinfo'} 
	
	@overrides(Indicator)
	def _perform(self,candles):
		awesome = Awesome()
		sma = SMA()
		awesome.fast_period = self.fast_period
		awesome.slow_period = self.slow_period
		sma.candle_channel = 0
		sma.period = self.period
		
		ao = awesome._perform(candles)
		return ao - sma._perform(ao)


class Momentum(Indicator):
	
	period = 12
	channel_keys = {'MOMENTUM':0}
	channel_styles = {'MOMENTUM':'bearish'}
	
	@overrides(Indicator)
	def _perform(self,candles):
		
		momentum = candles[:,self.period:,csf.close] / candles[:,:-self.period,csf.close]
		#pad with ones 
		pad = np.ones((candles.shape[0],self.period))
		momentum = np.concatenate([pad,momentum],axis=1)
		return momentum[:,:,np.newaxis]
	
class Aroon(Indicator):
	
	period = 25
	channel_keys = {'AROON':0,'AROON_UP':1,'AROON_DOWN':2}
	channel_styles = {'AROON':'neutral','AROON_UP':'bullish','AROON_DOWN':'bearish'}
	
	@overrides(Indicator)
	def _perform(self,candles):
		windows = self._sliding_windows(candles)
		aroon_up = np.nanargmax(windows[:,:,csf.high,:],axis=2) / (self.period-1)
		aroon_down = np.nanargmin(windows[:,:,csf.low,:],axis=2) / (self.period-1)
		aroon = aroon_up - aroon_down
		aroon = (aroon / 2.0) + 0.5  #scale
		return np.stack([aroon,aroon_up,aroon_down],axis=2)

class CCI(Indicator):
	
	period = 5
	channel_keys = {'CCI':0}
	channel_styles = {'CCI':'bearish'}
	
	@overrides(Indicator)
	def _perform(self,candles):
		typical = np.mean(np.stack([candles[:,:,csf.high],candles[:,:,csf.low],candles[:,:,csf.close]],axis=2),axis=2)
		typical = typical[:,:,np.newaxis]
		sma = SMA()
		sma.period = self.period
		ma = sma._perform(candles)
		deviation = np.abs(typical - ma)
		sma.candle_channel = 0
		mean_deviation = sma._perform(deviation)
		cci = (typical - ma) / (1.5 * mean_deviation)  #use closer to 1.0 than 100 
		return cci
	
#same as macd with subtle difference - macd / long period
class PPO(Indicator):
	
	channel_keys = {'PPO':0,'SIGNAL':1,'DEVIATION':2,'DIRECTION':3} 
	channel_styles = {'PPO':'keyinfo','SIGNAL':'bearish'}#,'DEVIATION':'neutral','DIRECTION':'neutral'}#requires specialist draw_snapshot anyway
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
		
		macd = (fast_ema - slow_ema) / slow_ema
		
		signal_line = signal._perform(macd)
		deviation = macd - signal_line
		direction = np.sign(deviation[:,1:] - deviation[:,:-1])
		
		pad_0s = np.zeros((direction.shape[0],1,1))
		direction = np.concatenate([pad_0s,direction],axis=1) #add 0 at start
		return np.concatenate([macd,signal_line,deviation,direction],axis=2)
		
#bug when switch to uptrend -draw to see! 
class ParabolicSAR(Indicator):
	
	channel_keys = {'UPTREND':0, 'DOWNTREND':1}
	channel_styles = {'UPTREND':'bullish', 'DOWNTREND':'bearish'}  #consider using a different view with points/stars 
	
	acceleration_step = 0.02
	acceleration_max = 0.2
	period = 5
	
	@overrides(Indicator)
	def _perform(self,candles):
		
		#init
		highs = candles[:,:,csf.high]
		lows = candles[:,:,csf.low]
		
		psars = candles[:,0:1,csf.high]
		eps = candles[:,0:1,csf.low]
		eps_m_psars = eps - psars
		acc = np.full(psars.shape,self.acceleration_step)
		eps_m_psars_a = eps_m_psars * acc
		trend = np.full(psars.shape,1)
		n_channels = candles.shape[0]
		
		for row_index in range(1,candles.shape[1]):	
			prev_eps = eps[:,row_index-1:row_index]
			prev_trend = trend[:,row_index-1:row_index]
			prev_acc = acc[:,row_index-1:row_index]
			prev_psars = psars[:,row_index-1:row_index]
			prev_eps_m_psars = eps_m_psars[:,row_index-1:row_index]
			prev_eps_m_psars_a = eps_m_psars_a[:,row_index-1:row_index]
			current_highs = highs[:,row_index:row_index+1]
			current_lows = lows[:,row_index:row_index+1]
			
			assert prev_eps.shape == (n_channels,1)
			assert prev_trend.shape == (n_channels,1)
			assert prev_acc.shape == (n_channels,1)
			assert prev_psars.shape == (n_channels,1)
			assert prev_eps_m_psars.shape == (n_channels,1)
			assert prev_eps_m_psars_a.shape == (n_channels,1)
			
			assert current_highs.shape == (n_channels,1)
			assert current_lows.shape == (n_channels,1)
			
			
			new_eps = np.zeros(prev_eps.shape)
			higher_highs = (prev_trend == 1) & (prev_eps < current_highs)
			same_highs = (prev_trend == 1) & (prev_eps >= current_highs)
			lower_lows = (prev_trend == -1) & (prev_eps > current_lows)
			same_lows = (prev_trend == -1) & (prev_eps <= current_lows)
			
			assert higher_highs.shape == (n_channels,1)
			assert same_highs.shape == (n_channels,1)
			assert lower_lows.shape == (n_channels,1)
			assert same_lows.shape == (n_channels,1)
			
			assert higher_highs.dtype == bool
			assert same_highs.dtype == bool
			assert lower_lows.dtype == bool
			assert same_lows.dtype == bool
			
			
			#pdb.set_trace()
			new_eps[same_highs | same_lows] = prev_eps[same_highs | same_lows]
			new_eps[higher_highs] = current_highs[higher_highs]
			new_eps[lower_lows] = current_lows[lower_lows]			
			
			
			current_psars = prev_psars + prev_eps_m_psars_a
			uptrend = prev_trend == 1 
			downtrend = prev_trend == -1
			
			uptrending_switch = current_psars > current_lows
			downtrending_switch = current_psars < current_highs
			
			switch = (uptrend & uptrending_switch) | (downtrend & downtrending_switch)
			
			new_psars = np.copy(current_psars)
			new_psars[switch] = prev_eps[switch]
			
			
			new_eps_m_psars = new_eps - new_psars
			
			new_trend = np.zeros(prev_trend.shape)
			new_trend[prev_psars < current_highs] = 1
			new_trend[prev_psars > current_lows] = -1
			
			same_trend = prev_trend == new_trend 
			
			uptrend_highs = new_eps > prev_eps #unsure  about this step... 
			downtrend_lows = new_eps < prev_eps
			
			not_exceed = prev_trend < self.acceleration_max
			
			increase_acc_up = 	same_trend & uptrend & 	uptrend_highs & not_exceed
			increase_acc_down = same_trend & downtrend & downtrend_lows & not_exceed
			increase_acc = increase_acc_up | increase_acc_down
			
			new_acc = np.copy(prev_acc)
			new_acc[increase_acc] = prev_acc[increase_acc] + self.acceleration_step
			new_acc[~same_trend] = self.acceleration_step #start again with low acc
			
			new_eps_m_psars_a = new_eps_m_psars * new_acc
			
			#update everything 
			psars 			= np.concatenate([psars,new_psars],axis=1)	
			eps				= np.concatenate([eps,new_eps],axis=1)
			eps_m_psars		= np.concatenate([eps_m_psars,new_eps_m_psars],axis=1)
			acc				= np.concatenate([acc,new_acc],axis=1)
			eps_m_psars_a	= np.concatenate([eps_m_psars_a,new_eps_m_psars_a],axis=1)
			trend			= np.concatenate([trend,new_trend],axis=1)
			
		#trend = np.concatenate([trend[:,1:],np.full((trend.shape[0],1),0)],axis=1) #trend fix -doesnt work :(
		
		uptrends = np.copy(psars)
		downtrends = np.copy(psars)
		
		#delete as appropriate
		uptrends[trend==-1] = np.nan
		uptrends[trend==0] = np.nan
		downtrends[trend==1] = np.nan
		downtrends[trend==0] = np.nan
		return np.stack([uptrends,downtrends],axis=2)
			
	

class IchimokuCloud(Indicator):
	
	channel_keys = {'CONVERSION':0, 'BASE':1, 'SPAN_A':2, 'SPAN_B':3, 'LAG': 4}
	channel_styles = {'CONVERSION':'bullish', 'BASE':'bearish', 'SPAN_A':'neutral', 'SPAN_B':'neutral', 'LAG': 'keyinfo'}  #consider using a different view with cloud drawn in!
	
	conversion_period = 9 
	base_period = 26 
	span_period = 52
	lag_period = 26
	lead_period = 26
	
	trim = True #TODO: if true, we trim the cloud so it does not overlap the end of the candle chart
	
	@overrides(Indicator)
	def _perform(self,candles):
		conversion_windows = self._sliding_windows(candles,self.conversion_period)
		base_windows = self._sliding_windows(candles,self.base_period)
		span_windows = self._sliding_windows(candles,self.span_period)
		
		conversion = (np.nanmax(conversion_windows[:,:,csf.high,:],axis=2) + np.nanmin(conversion_windows[:,:,csf.low,:],axis=2)) / 2.0
		base = (np.nanmax(base_windows[:,:,csf.high,:],axis=2) + np.nanmin(base_windows[:,:,csf.low,:],axis=2)) / 2.0
		span_b = (np.nanmax(span_windows[:,:,csf.high,:],axis=2) + np.nanmin(span_windows[:,:,csf.low,:],axis=2)) / 2.0
		span_a = (conversion + base) / 2.0
		
		cloud_a = np.concatenate([np.full((candles.shape[0],self.lag_period),np.nan),span_a],axis=1)
		cloud_b = np.concatenate([np.full((candles.shape[0],self.lag_period),np.nan),span_b],axis=1)
		cloud_a = cloud_a[:,:span_a.shape[1]] #trim off front
		cloud_b = cloud_b[:,:span_b.shape[1]] #trim off front
		
		lag = np.concatenate([candles[:,self.lag_period:,csf.close],np.full((candles.shape[0],self.lag_period),np.nan)],axis=1)
		return np.stack([conversion, base, cloud_a, cloud_b, lag],axis=2)

#https://www.investopedia.com/terms/r/relative_vigor_index.asp
class RVI(Indicator):
	
	channel_keys = {'RVI':0,'SIGNAL':1}
	channel_styles = {'RVI':'keyinfo','SIGNAL':'bearish'}
	period  = 14
	
	@overrides(Indicator)
	def _perform(self,candles):
		windows = self._sliding_windows(candles,4) 
		a = windows[:,:,csf.close,3] - windows[:,:,csf.open,3]
		b = windows[:,:,csf.close,2] - windows[:,:,csf.open,2]
		c = windows[:,:,csf.close,1] - windows[:,:,csf.open,1]
		d = windows[:,:,csf.close,0] - windows[:,:,csf.open,0]
		
		e = windows[:,:,csf.high,3] - windows[:,:,csf.low,3]
		f = windows[:,:,csf.high,2] - windows[:,:,csf.low,2]
		g = windows[:,:,csf.high,1] - windows[:,:,csf.low,1]
		h = windows[:,:,csf.high,0] - windows[:,:,csf.low,0]
		
		numerator = (a + (2.0 * b) + (2.0 * c) + d) / 6.0
		denominator = (e + (2.0 * f) + (2.0 * g) + h) / 6.0
		
		sma = SMA()
		sma.period = self.period
		sma.candle_channel = 0
		
		rvi = (sma._perform(numerator[:,:,np.newaxis]) / sma._perform(denominator[:,:,np.newaxis]))
		rvi_window = self._sliding_windows(rvi,4)
		
		rvi = rvi_window[:,:,0,3]
		i = rvi_window[:,:,0,2]
		j = rvi_window[:,:,0,1]
		k = rvi_window[:,:,0,0]
		
		signal = (rvi + (2.0 * i) + (2.0 * j) + k) / 6.0
		return np.stack([rvi,signal],axis=2)
		
	

class DonchianChannel(Indicator):
	
	channel_keys = {'MIDDLE':0,'UPPER':1,'LOWER':2}
	channel_styles = {'MIDDLE':'bearish','UPPER':'neutral','LOWER':'neutral'}
	period  = 20
	
	@overrides(Indicator)
	def _perform(self,candles):
		windows = self._sliding_windows(candles)
		upper = np.nanmax(windows[:,:,csf.high,:],axis=2)
		lower = np.nanmin(windows[:,:,csf.low,:],axis=2)
		middle = (upper + lower) / 2.0
		return np.stack([middle,upper,lower],axis=2)
	
#bug: doesnt seem to line up with T212
class WilliamsPercentRange(Indicator):
	
	channel_keys = {'VALUE':0,'OVERBOUGHT':1,'OVERSOLD':2}
	channel_styles = {'VALUE':'bearish','OVERBOUGHT':'neutral','OVERSOLD':'neutral'}
	period  = 5
	
	overbought = 0.8
	oversold = 0.2
	
	@overrides(Indicator)
	def _perform(self,candles):
		windows = self._sliding_windows(candles)
		highs = np.nanmax(windows[:,:,csf.high,:],axis=2)
		lows = np.nanmin(windows[:,:,csf.low,:],axis=2)
		closes = candles[:,:,csf.close]
		williams = (highs - closes) / (highs - lows)
		overbought = np.full(williams.shape,self.overbought)
		oversold = np.full(williams.shape,self.oversold)
		return np.stack([williams,overbought,oversold],axis=2)
		
		
#todo if desired: - this is buggy 
class SuperTrend(Indicator):
	
	channel_keys = {'LOWER':0}#,'UPPER':1}
	channel_styles = {'LOWER':'bullish'}#,'UPPER':'bearish'}
	period = 10 
	atr_period = 14
	multiplier = 2
	
	@overrides(Indicator)
	def _perform(self,candles):
		atr = ATR()
		atr.period = self.atr_period
		atr_values = atr._perform(candles)[:,:,0] #shave off one dim
		
		midpoints = (candles[:,:,csf.high] + candles[:,:,csf.low]) / 2.0
		basic_upper = midpoints + (atr_values*self.multiplier)
		basic_lower = midpoints - (atr_values*self.multiplier)
		
		final_upper = basic_upper[:,0:1]
		final_lower = basic_lower[:,0:1]
		super_trend = basic_lower[:,0:1]
		
		upper_conditions = np.full(final_upper.shape,1==0)
		lower_conditions = np.full(final_lower.shape,1==0)
		
		for row_index in range(1,candles.shape[1]):
			prev_final_upper = final_upper[:,row_index-1:row_index]
			prev_final_lower = final_lower[:,row_index-1:row_index]
			current_basic_upper = basic_upper[:,row_index:row_index+1]
			current_basic_lower = basic_lower[:,row_index:row_index+1]
			
			prev_close = 	candles[:,row_index-1:row_index,csf.close]
			current_close = candles[:,row_index:row_index+1,csf.close]
			
			prev_super_trend = super_trend[:,row_index-1:row_index]
			
			preserve_basic_upper = (current_basic_upper < prev_final_upper) | (prev_close > prev_final_upper)
			preserve_basic_lower = (current_basic_lower > prev_final_lower) | (prev_close < prev_final_lower)
			
			new_final_upper = np.full(prev_final_upper.shape,np.nan)
			new_final_lower = np.full(prev_final_lower.shape,np.nan)
			
			new_final_upper[preserve_basic_upper] = current_basic_upper[preserve_basic_upper]
			new_final_upper[~preserve_basic_upper] = prev_final_upper[~preserve_basic_upper]
			
			new_final_lower[preserve_basic_lower] = current_basic_lower[preserve_basic_lower]
			new_final_lower[~preserve_basic_lower] = prev_final_lower[~preserve_basic_lower]
			
			final_upper = np.concatenate([final_upper,new_final_upper],axis=1)
			final_lower = np.concatenate([final_lower,new_final_lower],axis=1)
			
			upper_cond1 = (prev_super_trend == prev_final_upper) & (current_close < new_final_upper)
			upper_cond2 = (prev_super_trend == prev_final_lower) & (current_close < new_final_lower)
			
			lower_cond1 = (prev_super_trend == prev_final_upper) & (current_close > new_final_upper)
			lower_cond2 = (prev_super_trend == prev_final_lower) & (current_close > new_final_lower)
			
			
			upper_cond = upper_cond1 & upper_cond2
			lower_cond = lower_cond1 & lower_cond2
			
			new_super_trend = np.full(prev_super_trend.shape,np.nan)
			new_super_trend = np.full(prev_super_trend.shape,np.nan)
			new_super_trend[upper_cond] = new_final_upper[upper_cond]
			new_super_trend[lower_cond] = new_final_lower[lower_cond]
			
			super_trend = np.concatenate([super_trend,new_super_trend],axis=1)
			upper_conditions = np.concatenate([upper_conditions,upper_cond],axis=1)
			lower_conditions = np.concatenate([lower_conditions,lower_cond],axis=1)
		
		#delete as appropriate
		#pdb.set_trace()
		final_upper[lower_conditions] = np.nan
		final_lower[upper_conditions] = np.nan
		#return np.stack([final_upper,final_lower],axis=2)
		return super_trend[:,:,np.newaxis]
	


#class Alligator(Indicator):
#	channel_keys = {'VALUE':0,'OVERBOUGHT':1,'OVERSOLD':2}
#	channel_styles = {'VALUE':'bearish','OVERBOUGHT':'neutral','OVERSOLD':'neutral'}
#	period  = 5
#	pass



























import numpy as np 

from air.utils import overrides

from air.indicators.indicator import Indicator, RunningHigh, RunningLow
from air.indicators.moving_average import SMA, EMA
from air.charting import candle_stick_functions as csf


class STDDEV(SMA):
	channel_keys = {'STDDEV':0}
	channel_styles = {'STDDEV':'keyinfo'}
	candle_sticks = False
	
	period = 10
	
	def __init__(self,period=10,*args,**kwargs):
		self.period = period 
		super().__init__(*args,**kwargs)
	
	@overrides(Indicator)
	def _perform(self,candles):
		windows = self._sliding_windows(candles)[:,:,self.candle_channel,:]
		return np.nanstd(windows,axis=2)[:,:,np.newaxis]
	
	@overrides(Indicator)
	def title(self):
		return f"{self.__class__.__name__} ( {self.period}, {self._channel_str} ) "


class BollingerBands(Indicator):
	channel_keys = {'MIDDLE':0,'UPPER':1,'LOWER':2} #etc
	channel_styles = {'MIDDLE':'bullish','UPPER':'bearish','LOWER':'bearish'}
	candle_sticks = True
	
	candle_channel = csf.close
	
	period = 20
	k = 2
	
	def __init__(self,period=20,k=2,*args,**kwargs):
		self.period = period 
		self.k = k
		super().__init__(*args,**kwargs)
	
	@overrides(Indicator)
	def _perform(self,candles):
		
		sma = SMA()
		std = STDDEV() 
		sma.period = self.period
		std.period = self.period
		sma.candle_channel = self.candle_channel
		std.candle_channel = self.candle_channel
		
		smas = sma._perform(candles)
		stds = std._perform(candles)
		upper = smas + (self.k * stds)
		lower = smas - (self.k * stds)
		
		return np.concatenate([smas,upper,lower],axis=2)
	
	@overrides(Indicator)
	def title(self):
		return f"{self.__class__.__name__} ( {self.period}, {self.k}, {self._channel_str} ) "


class ATR(Indicator):
	channel_keys = {'ATR':0} 
	channel_styles = {'ATR':'keyinfo'}
	candle_sticks = False
	
	period = 14
	
	def __init__(self,period=10,*args,**kwargs):
		self.period = period 
		super().__init__(*args,**kwargs)
	
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
	
	@overrides(Indicator)
	def title(self):
		return f"{self.__class__.__name__} ( {self.period} ) "

class KeltnerChannel(Indicator):
	channel_keys = {'MIDDLE':0, 'UPPER':1, 'LOWER':2} 
	channel_styles = {'MIDDLE':'keyinfo', 'UPPER':'neutral', 'LOWER':'neutral'}
	candle_sticks = True
	
	period = 20
	k = 2
	atr_period = 10
	
	def __init__(self,period=20,k=2,atr_period=10,*args,**kwargs):
		self.period = period 
		super().__init__(*args,**kwargs)
	
	@overrides(Indicator)
	def _perform(self,candles):
		atr = ATR() 
		atr.period = self.atr_period
		average_true_range = atr._perform(candles)
		ema = EMA()
		ema.period = self.period
		ema.candle_channel = self.candle_channel
		middle = ema._perform(candles)
		upper = middle + (self.k * average_true_range)
		lower = middle - (self.k * average_true_range)
		return np.concatenate([middle,upper,lower],axis=2)
	
	@overrides(Indicator)
	def title(self):
		return f"{self.__class__.__name__} ( {self.period}, {self.k}, {self.atr_period} ) "

class DonchianChannel(Indicator):
	channel_keys = {'MIDDLE':0,'UPPER':1,'LOWER':2}
	channel_styles = {'MIDDLE':'bearish','UPPER':'neutral','LOWER':'neutral'}
	candle_sticks = True
	
	period  = 20
	
	def __init__(self,period=10,*args,**kwargs):
		self.period = period 
		super().__init__(*args,**kwargs)
	
	@overrides(Indicator)
	def _perform(self,candles):
		windows = self._sliding_windows(candles)
		upper = np.nanmax(windows[:,:,csf.high,:],axis=2)
		lower = np.nanmin(windows[:,:,csf.low,:],axis=2)
		middle = (upper + lower) / 2.0
		return np.stack([middle,upper,lower],axis=2)
	
	@overrides(Indicator)
	def title(self):
		return f"{self.__class__.__name__} ( {self.period} ) "

class ChoppinessIndex(Indicator):
	channel_keys = {'CHOP':0, 'TREND':1, 'CONSOLIDATION':2}
	channel_styles = {'CHOP':'bearish','TREND':'neutral','CONSOLIDATION':'neutral'} 
	candle_sticks = False 
	
	trend_value = 0.382
	consolidation_value = 0.618
	
	period = 14
	
	@overrides(Indicator)
	def _perform(self,candles):	
		atr = ATR()
		atr.period  = self.period
		atr_result = atr._perform(candles) 
		true_ranges = atr_result[:,:,atr.channel_keys['ATR']] * self.period 
		highs = RunningHigh()
		lows = RunningLow() 
		highs.period = self.period
		lows.period = self.period
		high_vals = highs._perform(candles)[:,:,highs.channel_keys['HIGH']]
		low_vals = lows._perform(candles)[:,:,lows.channel_keys['LOW']]
		chop = np.log10((true_ranges / (high_vals - low_vals))) / np.log10(self.period)
		return np.stack([chop,np.full(chop.shape,self.trend_value),np.full(chop.shape,self.consolidation_value)],axis=2)
		
		
		
	
	










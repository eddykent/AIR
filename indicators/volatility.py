
import numpy as np 

from utils import overrides

from indicators.indicator import Indicator
from indicators.moving_average import SMA, EMA
from charting import candle_stick_functions as csf


class STDDEV(SMA):
	channel_keys = {'STDDEV':0}
	channel_styles = {'STDDEV':'keyinfo'}
	candle_sticks = False
	
	@overrides(Indicator)
	def _perform(self,candles):
		windows = self._sliding_windows(candles)[:,:,self.candle_channel,:]
		return np.nanstd(windows,axis=2)[:,:,np.newaxis]


class BollingerBands(Indicator):
	channel_keys = {'MIDDLE':0,'UPPER':1,'LOWER':2} #etc
	channel_styles = {'MIDDLE':'bullish','UPPER':'bearish','LOWER':'bearish'}
	candle_sticks = True
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


class ATR(Indicator):
	channel_keys = {'ATR':0} 
	channel_styles = {'ATR':'keyinfo'}
	candle_sticks = False
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
	candle_sticks = True
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


class DonchianChannel(Indicator):
	channel_keys = {'MIDDLE':0,'UPPER':1,'LOWER':2}
	channel_styles = {'MIDDLE':'bearish','UPPER':'neutral','LOWER':'neutral'}
	candle_sticks = True
	period  = 20
	
	@overrides(Indicator)
	def _perform(self,candles):
		windows = self._sliding_windows(candles)
		upper = np.nanmax(windows[:,:,csf.high,:],axis=2)
		lower = np.nanmin(windows[:,:,csf.low,:],axis=2)
		middle = (upper + lower) / 2.0
		return np.stack([middle,upper,lower],axis=2)






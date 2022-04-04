

import numpy as np

from utils import overrides
from indicators.indicator import Indicator
from charting import candle_stick_functions as csf


class SMA(Indicator):
	channel_keys = {'SMA':0}
	channel_styles = {'SMA':'bearish'}
	candle_sticks = True

	@overrides(Indicator)
	def _perform(self,candles):
		windows = self._sliding_windows(candles)[:,:,self.candle_channel,:] #select the correct candle channel
		return np.nanmean(windows,axis=2)[:,:,np.newaxis]
		

class EMA(Indicator):
	channel_keys = {'EMA':0}
	channel_styles = {'EMA':'keyinfo'}
	candle_sticks = True
	
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


class MultiMovingAverage(Indicator):
	channel_keys = {'MMA':0}
	channel_styles = {'MMA':'neutral'}
	candle_sticks = True
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


#weighted? other moving average types







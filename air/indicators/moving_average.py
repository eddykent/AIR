

import numpy as np

from air.utils import overrides
from air.indicators.indicator import Indicator,  Diff
from air.charting import candle_stick_functions as csf

import pdb

class SMA(Indicator):
	channel_keys = {'SMA':0}
	channel_styles = {'SMA':'bearish'}
	candle_sticks = True

	def __init__(self,period=20,*args,**kwargs):
		self.period = period 
		super().__init__(*args,**kwargs)
	
	@overrides(Indicator)
	def _perform(self,candles):
		windows = self._sliding_windows(candles)[:,:,self.candle_channel,:] #select the correct candle channel
		return np.nanmean(windows,axis=2)[:,:,np.newaxis]
	
	@overrides(Indicator)
	def title(self):
		return f"{self.__class__.__name__} ( {self.period}, {self._channel_str} ) "
	

class EMA(Indicator):
	channel_keys = {'EMA':0}
	channel_styles = {'EMA':'keyinfo'}
	candle_sticks = True
	
	def __init__(self,period=20,*args,**kwargs):
		self.period = period 
		super().__init__(*args,**kwargs)
	
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

	@overrides(Indicator)
	def title(self):
		return f"{self.__class__.__name__} ( {self.period}, {self._channel_str} ) "


class MultiMovingAverage(Indicator):
	channel_keys = {'MMA':0}
	channel_styles = {'MMA':'neutral'}
	candle_sticks = True
	MA = SMA #ema
	repeats = 3 #triple simple moving average by default 
		
	def __init__(self,ma=SMA,period=20,repeats=3,*args,**kwargs):
		self.MA = ma
		self.period = period 
		self.repeats = repeats 
		super().__init__(*args,**kwargs)

	@overrides(Indicator)
	def _perform(self,candles):
		ma = self.MA(self.period)
		ma.candle_channel = self.candle_channel
		
		result = ma._perform(candles)
		ma_key_name = list(ma.channel_keys.keys())[0] #always first
		ma_key = ma.channel_keys[ma_key_name]
		
		ma.candle_channel = ma_key
		for i in range(self.repeats-1):
			result = ma._perform(result)
		return result 
	
	@overrides(Indicator)
	def title(self):
		return f"{self.__class__.__name__} ( {self.MA.__name__} ( {self.period}, {self._channel_str} ), {self.repeats} ) "


#ensure it is known that the start values will not be accurate (nan+nan+..+7*x1 + 8*x2) not (1*x1 + 2*x2 ...) 
class WMA(Indicator):
	channel_keys = {'WMA':0}
	channel_styles = {'WMA':'neutral'}
	candle_sticks = True
	
	def __init__(self,period=20,*args,**kwargs):
		self.period = period 
		super().__init__(*args,**kwargs)
	
	@overrides(Indicator)
	def _perform(self,candles):
		windows = self._sliding_windows(candles)[:,:,self.candle_channel,:] #select the correct candle channel
		#weights = ?
		weights_singular = np.arange(start=1,stop=self.period+1)
		weights = np.broadcast_to(weights_singular,shape=windows.shape)
		result = np.sum(windows*weights,axis=2)  / np.sum(weights,axis=2)
		return result[:,:,np.newaxis]
	
	@overrides(Indicator)
	def title(self):
		return f"{self.__class__.__name__} ( {self.period}, {self._channel_str} ) "

#double moving average
class DEMA(Indicator):
	channel_keys = {'DEMA':0}
	channel_styles = {'DEMA':'neutral'}
	candle_sticks = True
	
	MA = EMA #so we can change it to sma if we want
	
	def __init__(self,period=20,ma=EMA,*args,**kwargs):
		self.period = period 
		self.MA = EMA
		super().__init__(*args,**kwargs)
	
	@overrides(Indicator)
	def _perform(self,candles):
		closes = candles[:,:,self.candle_channel,np.newaxis]
		ma = self.MA()
		ma.candle_channel = 0
		ma1 = ma._perform(closes)
		ma2 = ma._perform(ma1)
		dema = (ma1 * 2)  - ma2
		return dema
	
	@overrides(Indicator)
	def title(self):
		return f"{self.__class__.__name__} ( {self.MA.__name__} ( {self.period}, {self._channel_str} ) )"

#triple moving average
class TEMA(Indicator):
	channel_keys = {'TEMA':0}
	channel_styles = {'TEMA':'neutral'}
	candle_sticks = True
	
	MA = EMA
	
	def __init__(self,period=20,ma=EMA,*args,**kwargs):
		self.period = period 
		self.MA = EMA
		super().__init__(*args,**kwargs)
	
	@overrides(Indicator)
	def _perform(self,candles):
		closes = candles[:,:,self.candle_channel,np.newaxis]
		ma = self.MA()
		ma.candle_channel = 0
		ma1 = ma._perform(closes)
		ma2 = ma._perform(ma1)
		ma3 = ma._perform(ma2)
		tema = (ma1 * 3)  - (ma2 * 3) + ma3
		return tema

	@overrides(Indicator)
	def title(self):
		return f"{self.__class__.__name__} ( {self.MA.__name__} ( {self.period}, {self._channel_str} ) )"
	
	
class ZLMA(Indicator):
	channel_keys = {'ZLMA':0}
	channel_styles = {'ZLMA':'neutral'}
	candle_sticks = True
	
	MA = EMA
	
	def __init__(self, period=20,ma=EMA,*args,**kwargs):
		self.period = period 
		self.MA = EMA
		super().__init__(*args,**kwargs)
	
	@overrides(Indicator)
	def _perform(self,candles):
		lag = (self.period - 1) // 2
		ma = self.MA()
		ma.period = self.period
		ma.candle_channel = 0
		diff = Diff() 
		diff.diff = lag
		diffed = diff._perform(candles)
		emadata = candles[:,:,self.candle_channel] + diffed[:,:,self.candle_channel]
		return ma._perform(emadata[:,:,np.newaxis])
		
	@overrides(Indicator)
	def title(self):
		return f"{self.__class__.__name__} ( {self.MA.__name__} ( {self.period}, {self._channel_str} ) )"

# - park for now
#trianglar moving average  -?? 
#class TMA(Indicator): 
#	channel_keys = {'TMA':0}
#	channel_styles = {'TMA':'neutral'}
#	candle_sticks = True
#	
#	@overrides(Indicator)
#	def _perform(self,candles):
#		return candles
#
#















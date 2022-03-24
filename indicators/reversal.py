
import numpy as np


from indicators.indicator import Indicator
from indicators.moving_average import SMA, EMA
from charting import candle_stick_functions as csf



#our RSI is between 0 and 1 for easier use with NNs  -
class RSI(Indicator):
	channel_keys = {'RSI':0, 'OVERBOUGHT':1, 'OVERSOLD':2} 
	channel_styles = {'RSI':'bearish', 'OVERBOUGHT':'neutral', 'OVERSOLD':'neutral'}
	candle_sticks = False
	
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
	candle_sticks = False
	
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
	channel_keys = {'STOCHASTIC_RSI':0, 'OVERBOUGHT':1, 'OVERSOLD':2}
	channel_styles = {'STOCHASTIC_RSI':'bearish', 'OVERBOUGHT':'neutral', 'OVERSOLD':'neutral'}
	candle_sticks = False
	
	period = 14
	
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


#bug: doesnt seem to line up with T212
class WilliamsPercentRange(Indicator):
	channel_keys = {'VALUE':0,'OVERBOUGHT':1,'OVERSOLD':2}
	channel_styles = {'VALUE':'bearish','OVERBOUGHT':'neutral','OVERSOLD':'neutral'}
	candle_sticks = False
	
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



class MassIndex(Indicator):
	channel_keys = {'MASS':0}
	channel_styles = {'MASS':'neutral'}
	candle_sticks = False
	
	mass_period = 25
	period = 9
	
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



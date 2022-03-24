#split into momentum.py and reversal.py?
import numpy as np 


from indicators.indicator import Indicator
from indicators.moving_average import SMA, EMA
from charting import candle_stick_functions as csf


class MACD(Indicator):	
	channel_keys = {'MACD':0,'SIGNAL':1,'DEVIATION':2,'DIRECTION':3} 
	channel_styles = {'MACD':'keyinfo','SIGNAL':'bearish','DEVIATION':'neutral','DIRECTION':'neutral'}#requires specialist draw_snapshot anyway
	candle_sticks = False
	
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
		

class Awesome(Indicator):
	channel_keys = {'AWESOME':0}
	channel_styles = {'AWESOME':'keyinfo'}
	candle_sticks = False
	
	fast_period = 5
	slow_period = 24
	
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
	channel_keys = {'ACCELERATOR':0}
	channel_styles = {'ACCELERATOR':'keyinfo'} 
	candle_sticks = False
	
	fast_period = 5
	slow_period = 24
	period = 5
	
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
	channel_keys = {'MOMENTUM':0}
	channel_styles = {'MOMENTUM':'bearish'}
	candle_sticks = False
	
	period = 12
	
	@overrides(Indicator)
	def _perform(self,candles):
		
		momentum = candles[:,self.period:,csf.close] / candles[:,:-self.period,csf.close]
		#pad with ones 
		pad = np.ones((candles.shape[0],self.period))
		momentum = np.concatenate([pad,momentum],axis=1)
		return momentum[:,:,np.newaxis]


#same as macd with subtle difference - macd / long period
class PPO(Indicator):
	channel_keys = {'PPO':0,'SIGNAL':1,'DEVIATION':2,'DIRECTION':3} 
	channel_styles = {'PPO':'keyinfo','SIGNAL':'bearish'}#,'DEVIATION':'neutral','DIRECTION':'neutral'}#requires specialist draw_snapshot anyway
	candle_sticks = False
	
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
		

	
#https://www.investopedia.com/terms/r/relative_vigor_index.asp
class RVI(Indicator):
	channel_keys = {'RVI':0,'SIGNAL':1}
	channel_styles = {'RVI':'keyinfo','SIGNAL':'bearish'}
	candle_sticks = False
	
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
		
	
		



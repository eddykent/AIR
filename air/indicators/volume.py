import numpy as np


from air.utils import overrides, TimeHandler

from air.indicators.indicator import Indicator, Diff, Typical, CandleType, Bounded 
from air.indicators.moving_average import SMA, EMA
from air.charting import candle_stick_functions as csf



import pdb 

csf.bid_volume = 4 #this allowed? 
csf.ask_volume = 5

bid_volume = 0
ask_volume = 1

class VolumeIndicator(Indicator):
	candle_type = CandleType.CANDLE_VOLUME

class VolumeOnlyIndicator(Indicator):
	candle_type = CandleType.VOLUME  #probably never used

class VWAP(VolumeIndicator): 
	channel_keys = {'VWAP':0}
	channel_styles = {'VWAP':'keyinfo'}
	candle_sticks = True
	
	def __init__(self,period=14,*args,**kwargs):
		self.period = period 
		super().__init__(*args,**kwargs)
	
	@overrides(VolumeIndicator)
	def _perform(self,candles):	
		volumes = candles[:,:,csf.bid_volume] + candles[:,:,csf.ask_volume]
		closes = candles[:,:,self.candle_channel,np.newaxis]  #typical! 
		close_windows = self._sliding_windows(closes) 
		volume_windows = self._sliding_windows(volumes[:,:,np.newaxis])
		#check - might be easier to do element-wise mutiplication
		#vwap = np.tensordot(volume_windows,close_windows,axis=3) / np.sum(volume_windows,axis=3)
		vwap = np.sum(volume_windows * close_windows, axis=3) / np.sum(volume_windows,axis=3)
		
		return vwap
	
	@overrides(Indicator)
	def title(self):
		return f"{self.__class__.__name__} ( {self.period}, {self._channel_str} ) "

		
class VWAPDaily(VolumeIndicator): #similar to VWAP but reset each day
	channel_keys = {'VWAP':0}
	channel_styles = {'VWAP':'keyinfo'}
	candle_sticks = True
	
	def __init__(self,period=14,*args,**kwargs):
		self.period = period 
		super().__init__(*args,**kwargs)
	
	@overrides(VolumeIndicator)
	def _perform(self,candles):	
		volumes = (candles[:,:,csf.bid_volume] + candles[:,:,csf.ask_volume])[:,:,np.newaxis]
		closes = candles[:,:,csf.close,np.newaxis]  #typical! 
		
		day_indexs = np.array(TimeHandler.day_grouping(self.timeline[:,0])) 
		mdx = np.max(day_indexs)+1
		chunks = [] 
		for di in range(mdx):	
			#dayvol = np.concatenate([lpad,volumes[:,day_indexs==di]])
			#dayclo = np.concatenate([lpad,closes[:,day_indexs==di]])
			p = np.sum(day_indexs==di)
			volume_windows = self._sliding_windows(volumes[:,day_indexs==di,:],p)
			close_windows = self._sliding_windows(closes[:,day_indexs==di,:],p)
			vwap = np.nansum(volume_windows * close_windows, axis=3) / np.nansum(volume_windows,axis=3)
			chunks.append(vwap)
		
		vwap_daily = np.concatenate(chunks,axis=1)
		#vwap = np.sum(volume_windows * close_windows, axis=3) / np.sum(volume_windows,axis=3)
		#pdb.set_trace() #check dims 
		return vwap_daily
	
	@overrides(Indicator)
	def title(self):
		return f"{self.__class__.__name__} ( {self.period}, {self._channel_str} ) "

class BidAskVWAP(VolumeIndicator):
	channel_keys = {'BID_VWAP':0,'ASK_VWAP':1}
	channel_styles = {'BID_VWAP':'bearish','ASK_VWAP':'bullish'}
	candle_sticks = True
	
	def __init__(self,period=14,*args,**kwargs):
		self.period = period 
		super().__init__(*args,**kwargs)
	
	@overrides(Indicator)
	def _perform(self,candles):	
		bid_volumes = candles[:,:,csf.bid_volume]
		ask_volumes = candles[:,:,csf.ask_volume]
		closes = candles[:,:,csf.close,np.newaxis]  #typical! 
		close_windows = self._sliding_windows(closes) 
		bid_volume_windows = self._sliding_windows(bid_volumes[:,:,np.newaxis])
		ask_volume_windows = self._sliding_windows(ask_volumes[:,:,np.newaxis])
		#check - might be easier to do element-wise mutiplication
		#vwap = np.tensordot(volume_windows,close_windows,axis=3) / np.sum(volume_windows,axis=3)
		bid_vwap = np.sum(bid_volume_windows * close_windows, axis=3) / np.sum(bid_volume_windows,axis=3)
		ask_vwap = np.sum(ask_volume_windows * close_windows, axis=3) / np.sum(ask_volume_windows,axis=3)
		return np.concatenate([bid_vwap,ask_vwap],axis=2)
	
	@overrides(Indicator)
	def title(self):
		return f"{self.__class__.__name__} ( {self.period}, {self._channel_str} ) "

class MVWAP(VolumeIndicator): #(VWAP?)
	pass 

class TVI(VolumeIndicator):
	pass
	
class Delta(VolumeIndicator): #?
	pass

class OBV(VolumeIndicator):
	pass


class ClientSentimentRatio(VolumeIndicator):
	channel_keys = {'LONG':0,'SHORT':1}
	channel_styles = {'LONG':'bullish','SHORT':'bearish'}
	candle_sticks = False
	
	diff = 0 #default
	
	def __init__(self,period=14,*args,**kwargs):
		self.period = period 
		super().__init__(*args,**kwargs)
	
	@overrides(Indicator)
	def _perform(self,volumes):	
		later = volumes[:,self.diff:,:]
		earlier = volumes[:,:-self.diff,:] if self.diff else later
		padshape = (later.shape[0],self.diff,2)
		
		bid_volume = later[:,:,csf.bid_volume]
		ask_volume = later[:,:,csf.ask_volume]
		total_volume = earlier[:,:,csf.bid_volume] + earlier[:,:,csf.ask_volume]
		
		bid_ratio = bid_volume / total_volume
		ask_ratio = ask_volume / total_volume
		result = np.stack([bid_ratio,ask_ratio], axis=2)
		
		return np.concatenate([np.zeros(padshape), result],axis=1) 
	
	@overrides(Indicator)
	def title(self):
		return f"{self.__class__.__name__} ( {self.diff} ) "

#class VolumeInterest(VolumeIndicator): ?
#	pass


#first, get the ratios   
#next, normalise over a long period (eg 100)
#finally, take the short period (self.period) 
#ema 
#change when a better model is thought of 
class ClientSentiment(VolumeIndicator):
	channel_keys = {'LONG':0,'SHORT':1}
	channel_styles = {'LONG':'bullish','SHORT':'bearish'}
	candle_sticks = False
	
	diff = 0
	period = 6
	normalisation_window = 50 #arbitrary
	
	def __init__(self,period=14, diff=0, window=50, *args,**kwargs):
		self.period = period 
		self.diff = diff
		self.normalisation_window = window
		super().__init__(*args,**kwargs)
	
	@overrides(Indicator)
	def _perform(self,volumes):
		csr = ClientSentimentRatio()
		csr.diff = self.diff #1 makes it far too sensitive for longer time frames - people trade in the day not in the night
		bound = Bounded()
		bound.period = self.normalisation_window
		bound.candle_channel = 0
		csr_result = csr._perform(volumes)
		long_bound = bound._perform(csr_result[:,:,0,np.newaxis])
		short_bound = bound._perform(csr_result[:,:,1,np.newaxis])
		ema = EMA()
		ema.period = self.period
		ema.candle_channel = 0
		long_bound_ema = ema._perform(long_bound)
		short_bound_ema = ema._perform(short_bound)
		return np.concatenate([long_bound_ema,short_bound_ema],axis=2)

	@overrides(Indicator)
	def title(self):
		return f"{self.__class__.__name__} ( {self.period}, {self.diff}, {self.normalisation_window} ) "

class ChaikinMoneyFlow(VolumeIndicator):
	
	channel_keys = {'CMF':0}
	channel_styles = {'CMF':'bullish'}
	candle_sticks = False
	
	period = 21
	
	def __init__(self,period=21, *args,**kwargs):
		self.period = period 
		super().__init__(*args,**kwargs)
	
	@overrides(Indicator)
	def _perform(self,np_candles):	
		volume = np_candles[:,:,csf.bid_volume] + np_candles[:,:,csf.ask_volume]
		open = np_candles[:,:,csf.open]
		high = np_candles[:,:,csf.high]
		low = np_candles[:,:,csf.low]
		close = np_candles[:,:,csf.close]
		
		mfm = ((close - low) - (high - close)) / (high - low)
		mfmv = volume * mfm 
		
		sma = SMA() 
		sma.period = self.period 
		sma.candle_channel = 0
		
		mfmva = sma(mfmv[:,:,np.newaxis])[:,:,0]
		va = sma(volume[:,:,np.newaxis])[:,:,0]
		
		return mfmva / va
		
	@overrides(Indicator)
	def title(self):
		return f"{self.__class__.__name__} ( {self.period} ) "

#our RSI is between 0 and 1 for easier use with NNs  - bug - missing a value...
class MoneyFlowIndex(Indicator):
	channel_keys = {'MFI':0, 'OVERBOUGHT':1, 'OVERSOLD':2} 
	channel_styles = {'MFI':'bearish', 'OVERBOUGHT':'neutral', 'OVERSOLD':'neutral'}
	candle_sticks = False
	
	overbought = 0.8
	oversold = 0.2 
	
	period = 14
	
	def __init__(self,period=14, overbought=0.8, oversold=0.2, *args,**kwargs):
		self.period = period 
		self.overbought = overbought
		self.oversold = oversold 
		super().__init__(*args,**kwargs)
	
	@overrides(Indicator)
	def _perform(self,candles):
		
		volume = candles[:,:,csf.bid_volume] + candles[:,:,csf.ask_volume]
		
		diff = Diff()
		diff.diff = 1
		differences = diff._perform(candles)
		rate_of_change = (differences[:,:,csf.close] + differences[:,:,csf.high] + differences[:,:,csf.low]) / 3.0
		
		rate_of_change = rate_of_change * volume
		
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

	@overrides(Indicator)
	def title(self):
		return f"{self.__class__.__name__} ( {self.period}, {self.overbought}, {self.oversold} ) "


















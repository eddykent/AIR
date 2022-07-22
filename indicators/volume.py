import numpy as np


from utils import overrides, TimeHandler

from indicators.indicator import Indicator, Diff, Typical, CandleType, Bounded 
from indicators.moving_average import SMA, EMA
from charting import candle_stick_functions as csf



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
	
	@overrides(VolumeIndicator)
	def _perform(self,candles):	
		volumes = candles[:,:,csf.bid_volume] + candles[:,:,csf.ask_volume]
		closes = candles[:,:,csf.close,np.newaxis]  #typical! 
		close_windows = self._sliding_windows(closes) 
		volume_windows = self._sliding_windows(volumes[:,:,np.newaxis])
		#check - might be easier to do element-wise mutiplication
		#vwap = np.tensordot(volume_windows,close_windows,axis=3) / np.sum(volume_windows,axis=3)
		vwap = np.sum(volume_windows * close_windows, axis=3) / np.sum(volume_windows,axis=3)
		
		return vwap

		
class VWAPDaily(VolumeIndicator): #similar to VWAP but reset each day
	channel_keys = {'VWAP':0}
	channel_styles = {'VWAP':'keyinfo'}
	candle_sticks = True
	
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
			volume_windows = self._sliding_windows(volumes[:,day_indexs==di,:])
			close_windows = self._sliding_windows(closes[:,day_indexs==di,:])
			vwap = np.nansum(volume_windows * close_windows, axis=3) / np.nansum(volume_windows,axis=3)
			chunks.append(vwap)
		
		vwap_daily = np.concatenate(chunks,axis=1)
		#vwap = np.sum(volume_windows * close_windows, axis=3) / np.sum(volume_windows,axis=3)
		pdb.set_trace()
		return vwap_daily
	
	
		

class BidAskVWAP(VolumeIndicator):
	channel_keys = {'BID_VWAP':0,'ASK_VWAP':1}
	channel_styles = {'BID_VWAP':'bearish','ASK_VWAP':'bullish'}
	candle_sticks = True
	
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
























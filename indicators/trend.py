
import numpy as np 

from utils import overrides

from indicators.indicator import Indicator
from indicators.moving_average import SMA, EMA
from indicators.volatility import ATR
from charting import candle_stick_functions as csf


#bug when switch to uptrend -draw to see! 
class ParabolicSAR(Indicator):
	channel_keys = {'UPTREND':0, 'DOWNTREND':1}
	channel_styles = {'UPTREND':'bullish', 'DOWNTREND':'bearish'}  #consider using a different view with points/stars 
	candle_sticks = True
	
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
	candle_sticks = True
	
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


#todo if desired: - this is buggy 
class SuperTrend(Indicator):
	channel_keys = {'LOWER':0}#,'UPPER':1}
	channel_styles = {'LOWER':'bullish'}#,'UPPER':'bearish'}
	candle_sticks = True
	
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
	

class Aroon(Indicator):
	channel_keys = {'AROON':0,'AROON_UP':1,'AROON_DOWN':2}
	channel_styles = {'AROON':'neutral','AROON_UP':'bullish','AROON_DOWN':'bearish'}
	candle_sticks = False
	
	period = 25
	
	@overrides(Indicator)
	def _perform(self,candles):
		windows = self._sliding_windows(candles)
		aroon_up = np.nanargmax(windows[:,:,csf.high,:],axis=2) / (self.period-1)
		aroon_down = np.nanargmin(windows[:,:,csf.low,:],axis=2) / (self.period-1)
		aroon = aroon_up - aroon_down
		aroon = (aroon / 2.0) + 0.5  #scale
		return np.stack([aroon,aroon_up,aroon_down],axis=2)


class CCI(Indicator):
	channel_keys = {'CCI':0}
	channel_styles = {'CCI':'bearish'}
	candle_sticks = False
	
	period = 5
	
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


#this is buggy - ADX should not range to 100 and pdi and ndi should not go below 0 
class ADX(Indicator):
	channel_keys = {'ADX':0,'PDI':1,'NDI':2}
	channel_styles = {'ADX':'keyinfo','PDI':'bullish','NDI':'bearish'}
	candle_sticks = False
	
	period = 14
	
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








	
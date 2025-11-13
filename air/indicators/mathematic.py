

import numpy as np


from utils import overrides

from indicators.indicator import Indicator

from charting import candle_stick_functions as csf


import pdb 

#convert the signals into a fourier series, then chop off high frequencies and inadequate frequencies and convert back to get 
#a smoothed curve whose gradient might indicate price movement 
#example idea: if a price is below the fft price and the fft price gradient is positive, this indicates a buy 
class FourierGradient(Indicator):
	channel_keys = {'GRADIENT':0, 'PRICE_DIFF':1} #fft_price - price (bullish if positive)
	channel_styles = {'GRADIENT':'neutral', 'PRICE_DIFF': 'neutral'}
	
	candle_sticks = False
	
	period = 100
	end_zeros = 50 #how many terms to chop off at the end 
	std_multiplier = 1.5#how many std the freq needs to  be above the mean to remain part of the fft price
	
	def __init__(self,period=100,zeros=50,std_multiplier=1.5,*args,**kwargs):
		self.period = period 
		self.end_zeros = zeros
		self.std_multiplier = std_multiplier
		super().__init__(*args,**kwargs)
	
	
	@overrides(Indicator)
	def _perform(self,np_candles):
		windows = self._sliding_windows(np_candles)
		window_closes = windows[:,:,self.candle_channel,:]
		fft_result = np.fft.fft(window_closes,self.period,axis=2)
		psd = fft_result * np.conj(fft_result) / self.period #power spectrum density - kind of does abs and removes img part
		psd_real = np.real(psd)
		
		skip=2 #first freq are very large, always so always keep them 
		stds = np.nanstd(psd_real[:,:,skip:],axis=2)
		means = np.nanmean(psd_real[:,:,skip:],axis=2)
		
		ub = means + self.std_multiplier*stds 
		
		freq_filter = psd_real > ub[:,:,np.newaxis] #remove any frequences that are lower than the lower bound
		freq_filter[:,:,(self.period - self.end_zeros):] = False #remove any high frequences (top third)
		
		fft_result_filtered = fft_result * freq_filter
		ifft_result = np.fft.ifft(fft_result_filtered,axis=2) 
		
		window_result = np.real(ifft_result)
		
		end_gradients = window_result[:,:,-1] - window_result[:,:,-2] #if the gradient is positive and the price is below the denoised, 
		price_difference = window_result[:,:,-1] - window_closes[:,:,-1]
		
		return np.stack([end_gradients,price_difference],axis=2)
	
	@overrides(Indicator)
	def title(self):
		return f"{self.__class__.__name__} ( {self.period}, {self.end_zeros}, {self.std_multiplier}, {self._channel_str} ) "



#nested correlation? eg how much stuff correlates at this point & what the correls say
#class CorrelationAnalysis(Indicator):
#	
#	channel_keys = {'INFLUENCE':0, 'AVG_COR':1, 'N_HITS':2}
#	channel_styles = {'INFLUENCE':'neutral', 'AVG_COR': 'neutral', 'N_HITS':'neutral'}
#	
#	candle_sticks = False
#	period = 30
#	candle_channel = csf.close
#
#	@overrides(Indicator)
#	def _perform(self,np_candles):
#
#
#
#class MarkovRegimes 
#	eg:	statsmodels.api.tsa.MarkovRegression(endog=prices_percent_change,k_regimes=2,trend='c',switching_variance=True)
#
#
#class StatsTest?
#











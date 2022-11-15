

import numpy as np


from utils import overrides

from indicators.indicator import Indicator

from charting import candle_stick_functions as csf


#import pdb 

#convert the signals into a fourier series, then chop off high frequencies and inadequate frequencies and convert back to get 
#a smoothed curve whose gradient might indicate price movement 
#example idea: if a price is below the fft price and the fft price gradient is positive, this indicates a buy 
class FourierGradient(Indicator):
	channel_keys = {'GRADIENT':0, 'PRICE_DIFF':1} #fft_price - price (bullish if positive)
	channel_styles = {'GRADIENT':'neutral', 'PRICE_DIFF': 'neutral'}
	
	candle_sticks = False
	
	period = 200
	end_zeros = 50 #how many terms to chop off at the end 
	std_multiplier = 2#how many std the freq needs to  be above the mean to remain part of the fft price

	@overrides(Indicator)
	def _perform(self,np_candles):
		windows = self._sliding_windows(np_candles)
		window_closes = windows[:,:,csf.close,:]
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
	



#nested correlation? eg how much stuff correlates at this point 


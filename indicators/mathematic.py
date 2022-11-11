

import numpy as np


from utils import overrides

from indicators.indicator import Indicator

from charting import candle_stick_functions as csf


import pdb 

#convert the signals into a fourier series, then chop off high frequencies and inadequate frequencies and convert back to get 
#a smoothed curve whose gradient might indicate price movement
class FourierAnalyser(Indicator):
	channel_keys = {'SMOOTHED':0} 
	channel_styles = {'SMOOTHED':'neutral'}
	candle_sticks = False

	@overrides(Indicator)
	def _perform(self,np_candles):
		pdb.set_trace()
		fft_vals = np.fft.fft(np_candles[:,:,csf.close],axis=1)
		#use sliding windows for predictions to prevent look ahead bias
		print('test?')
	



#nested correlation? eg how much stuff correlates at this point 


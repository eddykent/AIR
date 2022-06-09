
import time
import numpy as np
import scipy.signal 
import pandas as pd

import tqdm

from charting.candle_stick_pattern import * 
import charting.candle_stick_functions as csf
from indicators.indicator import Indicator



import logging 
log = logging.getLogger(__name__)



from utils import overrides

#similar to the candle stick pattern - but we want to take note of all the extreme points first before sliding
# and perhaps other things like curve fits or something else that is done globally across the whole dataset, not
# just in the chart window of _required_candles
class ChartPattern(Indicator):
	
	_required_candles = 100 # a chart pattern is a long pattern of extreme points
	#_xtremes = np.array([]) # and it has all the extreme points cached ready for use in shapes & trends 
	_xtreme_degree = 1 #number of times to apply extreme finding algorithm. Need to figure out how to do degree > 1
	
	#number of candles to start the detected pattern from 
	_tail_reaction_candles = 4 #too large => old news. too small => no breakout
	
	_precandles = None #use if you want to use an indicator to create the initial candles (eg typical or high/low prices or even ema) 
	
	MAX=1
	MIN=0
	
	
	#precalculated values 
	_window_index = None 
	
	#@overrides(Indicator)
	def explain(self):
		return """
		A chart pattern is an arrangement of extreme points from a selection of candles or values. 
		When they are arranged in a particular way they form a pattern. 
		"""
	
	@overrides(Indicator)
	def _perform(self,np_candles):   #allow for caching / inserting the extreme points or something so other chart patterns can be initalised with 1 dataset
		np_highs = np_candles[:,:,csf.high] 
		np_lows = np_candles[:,:,csf.low]
		
		if callable(self._precandles):
			pass #swap this out to be something to get highs and lows from np_candles (eg typical price)
		
		if self._xtreme_degree > 1:
			log.warning("_xtreme_degree of more than 1 has not yet been implemented. Change some stuff around below and add a for loop to get it working. ")
		
		assert self._xtreme_degree > 0, f"Extreme points need to be calculated for chart patterns to work. degree = {self._xtreme_degree}"
		#assert self._min_required_candles >= 0, f"How is the minimum required candles below 0? ({self._min_required_candles})"
		#assert self._min_required_candles <= self._required_candles, f"Minimum required candles ({self._min_required_candles}) must be smaller than the required candles ({self._required_candles})."
		
		#left_pad_n = self._required_candles - self._min_required_candles   -makes it too complex. add later if needed
		#if left_pad_n > 0: #we can start from earlier than the required candles window, so lets add padding to do so 
		#	left_pad = np.full((np_candles.shape[0],left_pad_n),np.nan)
		#	np_highs = np.concatenate([left_pad,np_highs],axis=1)
		#	np_lows = np.concatenate([left_pad,np_lows],axis=1)
			
		#now stride trick
		high_windows = np.lib.stride_tricks.sliding_window_view(np_highs,window_shape=self._required_candles,axis=1)
		low_windows = np.lib.stride_tricks.sliding_window_view(np_lows,window_shape=self._required_candles,axis=1)
		
		number_windows = np_candles.shape[1] - self._required_candles + 1
		assert high_windows.shape[1] == number_windows, "number of windows is not accurate"
		assert low_windows.shape[1] == number_windows, "number of windows is not accurate"
		#highs_masked = np.copy(high_windows)
		#lows_masked = np.copy(low_windows)
		
		#maxima = None
		#minima = None
		
		#for _ in range(0,self._xtreme_degree):  #add this back in and remove log.warning 
			
		#the_highs = np.full(high_windows.shape,np.nan) #put into new array 
		#the_lows = np.full(low_windows.shape,np.nan)
		
		maxima = scipy.signal.argrelmax(high_windows,axis=2)
		minima = scipy.signal.argrelmax(low_windows,axis=2)
		
		#the_highs[maxima] = highs_masked[maxima]
		#the_lows[minima] = lows_masked[minima]
			
		#highs_masked = np.copy(the_highs) #update the masks (in other words, nan out all the non-extremes)
		#lows_masked = np.copy(the_lows)
			
		#del the_highs #free up space incase py persists these in memory after the loop 
		#del the_lows  
			
		#pdb.set_trace()
		max_vals = high_windows[maxima]
		min_vals = low_windows[minima]
		
		max_vals = max_vals[:,np.newaxis]
		min_vals = min_vals[:,np.newaxis]
		
		maxima_tups = np.stack(list(maxima),axis=1)
		minima_tups = np.stack(list(minima),axis=1)
		
		max_labels = np.full((max_vals.shape[0],1),1)
		min_labels = np.full((min_vals.shape[0],1),0)
		
		
		#add end candles as maxima/minima? 
		maximum_points = np.concatenate([maxima_tups,max_vals,max_labels],axis=1)
		minimum_points = np.concatenate([minima_tups,min_vals,min_labels],axis=1)
		
		all_extr = np.concatenate([minimum_points,maximum_points])
		
		window_numbers = (number_windows * all_extr[:,0]) + all_extr[:,1]
		
		
		all_extr_windows_labeled = np.concatenate([window_numbers[:,np.newaxis],all_extr],axis=1)
		sort_by_window = all_extr_windows_labeled[:,0]
		all_extr_windows_labeled = all_extr_windows_labeled[sort_by_window.argsort()]
		
		#error here - sort by window, then by time for ordering to work
		#duplicate_window_indexs = all_extr[:,0:2]
		duplicate_window_index = all_extr_windows_labeled[:,0].astype(np.int)
		window_coords, counts = np.unique(duplicate_window_index,return_counts=True)
		max_extremes = np.max(counts)
		
		sort_by_window_then_time = (all_extr_windows_labeled[:,0] * number_windows) + all_extr_windows_labeled[:,3]
		all_extr_windows_labeled = all_extr_windows_labeled[sort_by_window_then_time.argsort()] 
		
		#pdb.set_trace()
		#adjust time indexs to be of the same as the np_candles time axis  something like this:? 
		all_extr_windows_labeled[:,3] = all_extr_windows_labeled[:,2] + all_extr_windows_labeled[:,3]
		
		
		cum_counts = np.concatenate([np.array([0]), np.cumsum(counts)[:-1]])
		neg_array = np.repeat(cum_counts,counts)
		buffers = np.repeat(np.max(counts) - counts,counts) #buffers push the xtremes forwards so nan values are first
		xtreme_index = np.arange(duplicate_window_index.shape[0]) - neg_array + buffers
		
		
		#extreme_indexs = #np.arange(duplicate_window_index.shape[0]) - (duplicate_window_index * number_windows) #incorrectb 
		
		#pdb.set_trace() #perhaps this part could be sped up 
		print('time the window write') #takes around 2 seconds 
		t0 = time.time()
		xtreme_windows = np.full((number_windows * np_candles.shape[0], np.max(counts) ,3),np.nan)  #each extreme point is a (timeval,priceval,type)
		extr_windows_flat = all_extr_windows_labeled[:,3:]
		for (dwi, xi, rhs) in zip(duplicate_window_index,xtreme_index,extr_windows_flat):
			#pdb.set_trace()
			xtreme_windows[dwi,xi,:] = rhs
		time_took = time.time() - t0
		print(f"write to windows took {time_took}s")		
		#window_indexer, counts = np.unique(duplicate_window_indexs,axis=0,return_counts=True)
		

		#now padd with the min_required candles?
		#if self._min_required_candles < self._required_candles:
		#	left_pad = np.full(np.nan,shape=(np_candles.shape[0],self._min_required_candles,self._required_candles))
			
		
		#then make a flat list of the views up to the extrema with n candle gap? 
		#might not want to make it as windows for now...

		#chart_windows = self._sliding_windows(np_candles) #ouch! this surely will break the ram?  
		#could change it to only slide on extreme point coordinates & dos some fancy tricks with the candles in the chart_perform
		
		
		
		chart_result = self._chart_perform(xtreme_windows, np_candles) 
		
		#TODO: 
		#turn chart_result back into [instrument,timeline,...]
		
	
	def _chart_perform(self,xtreme_windows, np_candles=None): 
		raise NotImplementedError('This method must be overridden')
	
	
	@overrides(Indicator)
	def detect(self,candle_stream,candle_stream_index=-1,criteria=[]): #for now, ignore criteria 
		return self.calculate(candle_stream,candle_stream_index)


class SupportAndResistance(ChartPattern):  #group together points along the price line, show resistance/support lines where there are significant groups 
	
	_required_candles = 100
	
	@overrides(ChartPattern)
	def _chart_perform(self, xtreme_windows, np_candles = None):			
		#for each window find the values & collect/group. 
		#use the group of values to determine support/resistance areas 
		#use the support/resistance to see if price bounced. 
		#return bullish/bearish/none rating and also things like quality etc which might be useful 
		return np.zeros((xtreme_windows.shape[0],1))

#class PivotPoints(ChartPattern)


















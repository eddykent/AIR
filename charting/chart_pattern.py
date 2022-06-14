
import time
import numpy as np
import scipy.signal 
import gc

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
	_breakout_candles = 3 #surely this should be for use AFTER the chart pattern?
	#_breakout_offset = 2 #how many steps forward/back to go to place the breakout candles 
	
	
	_precandles = None #use if you want to use an indicator to create the initial candles (eg typical or high/low prices or even ema) 
	
	#precalculated values 
	_window_index = None 
	
	
	#@overrides(Indicator)
	def explain(self):
		return """
		A chart pattern is an arrangement of extreme points from a selection of candles or values. 
		When they are arranged in a particular way they form a pattern. 
		"""
	
	
	@overrides(Indicator)
	def _perform(self,np_candles,mask=None):   #allow for caching / inserting the extreme points or something so other chart patterns can be initalised with 1 dataset
		np_opens = np_candles[:,:,csf.open]
		np_highs = np_candles[:,:,csf.high] 
		np_lows = np_candles[:,:,csf.low]
		np_closes = np_candles[:,:,csf.close]
		
		if callable(self._precandles):
			pass #swap this out to be something to get highs and lows from np_candles (eg typical price)
		
		if self._xtreme_degree > 1:
			log.warning("_xtreme_degree of more than 1 has not yet been implemented. Change some stuff around below and add a for loop to get it working. ")
		
		assert self._breakout_candles > 0, f"There must be at least one breakout candle for chart detection to work. breakout = {self._breakout_candles}"
		assert self._xtreme_degree > 0, f"Extreme points need to be calculated for chart patterns to work. degree = {self._xtreme_degree}"
		#assert self._min_required_candles >= 0, f"How is the minimum required candles below 0? ({self._min_required_candles})"
		#assert self._min_required_candles <= self._required_candles, f"Minimum required candles ({self._min_required_candles}) must be smaller than the required candles ({self._required_candles})."
		
		#left_pad_n = self._required_candles - self._min_required_candles   -makes it too complex. add later if needed
		#if left_pad_n > 0: #we can start from earlier than the required candles window, so lets add padding to do so 
		#	left_pad = np.full((np_candles.shape[0],left_pad_n),np.nan)
		#	np_highs = np.concatenate([left_pad,np_highs],axis=1)
		#	np_lows = np.concatenate([left_pad,np_lows],axis=1)
			
		#now stride trick
		high_windows = np.lib.stride_tricks.sliding_window_view(np_highs[:,:-self._breakout_candles],window_shape=self._required_candles,axis=1)
		low_windows = np.lib.stride_tricks.sliding_window_view(np_lows[:,:-self._breakout_candles],window_shape=self._required_candles,axis=1)
		
		
		
		
		number_windows = np_candles.shape[1] - self._required_candles + 1 - self._breakout_candles
		assert high_windows.shape[1] == number_windows, "number of windows is not accurate"
		assert low_windows.shape[1] == number_windows, "number of windows is not accurate"
		#highs_masked = np.copy(high_windows)
		#lows_masked = np.copy(low_windows)
		
		#set up the breakout windows
		bo_open_windows = np.lib.stride_tricks.sliding_window_view(np_opens,window_shape=self._breakout_candles,axis=1)
		bo_high_windows = np.lib.stride_tricks.sliding_window_view(np_highs,window_shape=self._breakout_candles,axis=1)
		bo_low_windows = np.lib.stride_tricks.sliding_window_view(np_lows,window_shape=self._breakout_candles,axis=1)
		bo_close_windows = np.lib.stride_tricks.sliding_window_view(np_closes,window_shape=self._breakout_candles,axis=1)
		
		breakout_windows = np.stack([bo_open_windows,bo_high_windows,bo_low_windows,bo_close_windows],axis=3)
		breakout_clip = breakout_windows.shape[1] - number_windows
		breakout_windows = breakout_windows[:,breakout_clip:,:,:]
		breakout_windows = breakout_windows.reshape((breakout_windows.shape[0]*breakout_windows.shape[1],breakout_windows.shape[2],breakout_windows.shape[3]))
		
		#maxima = None
		#minima = None
		
		#for _ in range(0,self._xtreme_degree):  #add this back in and remove log.warning 
		maxima = scipy.signal.argrelmax(high_windows,axis=2)
		minima = scipy.signal.argrelmax(low_windows,axis=2)
		
		#maxima/minima reducing algorithm 
		#for _ in range (0,self._xtreme_degree-1):
		#	local_maxima 
		#	local_minima 
			
		
		
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
		
		all_extr = np.concatenate([minimum_points,maximum_points]) #all extremes 
		
		window_numbers = (number_windows * all_extr[:,0]) + all_extr[:,1]
		
		all_extr_windows_labeled = np.concatenate([window_numbers[:,np.newaxis],all_extr],axis=1)
		sort_by_window = all_extr_windows_labeled[:,0]
		all_extr_windows_labeled = all_extr_windows_labeled[sort_by_window.argsort()]
		
		duplicate_window_index = all_extr_windows_labeled[:,0].astype(np.int)
		window_coords, counts = np.unique(duplicate_window_index,return_counts=True)
		max_extremes = np.max(counts)
		
		sort_by_window_then_time = (all_extr_windows_labeled[:,0] * number_windows) + all_extr_windows_labeled[:,3] #check
		all_extr_windows_labeled = all_extr_windows_labeled[sort_by_window_then_time.argsort()] 
		
		#adjust time indexs to be of the same as the np_candles time axis  something like this:? 
		all_extr_windows_labeled[:,3] = all_extr_windows_labeled[:,2] + all_extr_windows_labeled[:,3] 
		
			
			
		duplicate_window_map = np.stack([all_extr_windows_labeled[:,1],all_extr_windows_labeled[:,2]], axis=1).astype(np.int)
		window_map = np.unique(duplicate_window_map,axis=0).T #takes some time to get uniques...
		
		
		cum_counts = np.concatenate([np.array([0]), np.cumsum(counts)[:-1]])
		neg_array = np.repeat(cum_counts,counts)
		buffers = np.repeat(np.max(counts) - counts,counts) #buffers push the xtremes forwards so nan values are first
		xtreme_index = np.arange(duplicate_window_index.shape[0]) - neg_array + buffers
		
		#pdb.set_trace() #perhaps this part could be sped up somehow?
		#print('time the window write') #takes around 2 seconds 
		#t0 = time.time()
		xtreme_windows = np.full((number_windows * np_candles.shape[0], np.max(counts) ,3),np.nan)  #each extreme point is a (timeval,priceval,type)
		#extr_windows_flat = all_extr_windows_labeled[:,3:]
		#for (dwi, xi, rhs) in zip(duplicate_window_index,xtreme_index,extr_windows_flat):
			#pdb.set_trace()
		#	xtreme_windows[dwi,xi,:] = rhs
		#pdb.set_trace()
		xtreme_windows[(duplicate_window_index,xtreme_index)] = all_extr_windows_labeled[:,3:]
		
		pdb.set_trace() 
		#mask = self.create_mask(np_candles,[0,1,3],[1,3,4,5,6])
		
		if mask is not None:
			this_mask = mask[:,-number_windows:] #1 mask per window - chop off useless first ones
			instrument_indexs, window_indexs = np.where(this_mask) 
			select_indexs = (number_windows * instrument_indexs) + window_indexs
			
			xtreme_windows = xtreme_windows[select_indexs]
			window_map = window_map[:,select_indexs]
			breakout_windows = breakout_windows[select_indexs]
		
		
		#time_took = time.time() - t0
		#print(f"write to windows took {time_took}s")		
		#window_indexer, counts = np.unique(duplicate_window_indexs,axis=0,return_counts=True)
		

		#now padd with the min_required candles?
		#if self._min_required_candles < self._required_candles:
		#	left_pad = np.full(np.nan,shape=(np_candles.shape[0],self._min_required_candles,self._required_candles))
			
		
		#then make a flat list of the views up to the extrema with n candle gap? 
		#might not want to make it as windows for now...

		#chart_windows = self._sliding_windows(np_candles) #ouch! this surely will break the ram?  
		#could change it to only slide on extreme point coordinates & dos some fancy tricks with the candles in the chart_perform
		
		#consider masking here to reduce the number of xtreme_windows to pass
		chart_result = self._chart_perform(xtreme_windows, breakout_windows) 
		
		#then unmasking/expanding here - needs to be shaped properly since we might not have all the windows
		result_space = np.full((np_candles.shape[0],number_windows,chart_result.shape[-1]),np.nan)
		result_space[window_map[0],window_map[1]] = chart_result
		
		
		#result = chart_result.reshape((np_candles.shape[0],number_windows,chart_result.shape[-1])) #incorrect 
		pad_len = np_candles.shape[1] - number_windows
		pad_depth = chart_result.shape[-1]
		pad_height = np_candles.shape[0]
		padding = np.zeros((pad_height,pad_len,pad_depth))
		
		return np.concatenate([padding,result_space],axis=1)
		
	
	
	#def _generate_xtreme_windows() #use for getting the extreme points for each window 
	
	
	def _chart_perform(self,xtreme_windows, breakout_windows): 
		raise NotImplementedError('This method must be overridden')
	
	
	
	@overrides(Indicator)
	def detect(self,candle_stream,candle_stream_index=-1,criteria=[]): #for now, ignore criteria 
		return self.calculate(candle_stream,candle_stream_index)
	
	@overrides(Indicator)
	def draw_snapshot(self,np_candles,snapshot_index,instrument_index):
		mask = self._create_mask(np_candles,instrument_index,snapshot_index)
		
		windows = self.generate_xtreme_windows(xtreme_degree=1)
		#draw each window extreme points onto the chart 
		
		
	
	def create_mask(self,np_candles,instrument_index,time_index=None): #produces a mask with true on the indexs we want
		
		mask = np.full(np_candles.shape[0:2],0)
		number_windows = np_candles.shape[1] - self._required_candles + 1 - self._breakout_candles
		
		#feels like a hack here... 
		mask[instrument_index,:] = mask[instrument_index,:] + 1
		if time_index is None:
			mask = mask * 2 
		else:
			mask[:,time_index] = mask[:,time_index] + 1
		
		#pdb.set_trace()
		mask[mask < 2] = 0 
		mask[mask == 2] = 1
		
		return mask
		
	

class SupportAndResistance(ChartPattern):  #group together points along the price line, show resistance/support lines where there are significant groups 
	
	_required_candles = 100
	_number_buckets = 10 #increase for resolution/accuracy? 
	_early_influence = 0.4 #how much should earlier points count towards the bucket count 
	
	@overrides(ChartPattern)
	def _chart_perform(self, xtreme_windows, breakout_windows):			
		#for each window find the values & collect/group. 
		#use the group of values to determine support/resistance areas 
		#use the support/resistance to see if price bounced. 
		#return bullish/bearish/none rating and also things like quality etc which might be useful 
		
		assert self._early_influence >= 0 and self._early_influence <= 1,f"The early influence factor should be a number between 0 and 1, Got {self._early_influence}"
		

		values = xtreme_windows[:,:,1] #time,value,type 
		
		#consider putting in own function?
		maxs = np.nanmax(values,axis=1)
		mins = np.nanmin(values,axis=1)
		ranges = maxs - mins
		steps = ranges / self._number_buckets
		lower_bounds = np.outer(steps,np.arange(0,self._number_buckets)) + np.broadcast_to(mins,shape=(self._number_buckets,mins.shape[0])).T
		upper_bounds = np.outer(steps,np.arange(1,self._number_buckets+1)) + np.broadcast_to(mins,shape=(self._number_buckets,mins.shape[0])).T
		
		medians = (upper_bounds + lower_bounds) / 2
		
		lowers = np.stack([lower_bounds]*xtreme_windows.shape[1],axis=1)
		uppers = np.stack([upper_bounds]*xtreme_windows.shape[1],axis=1)
		value_buckets = np.stack([values]*self._number_buckets,axis=2)
		bucket_mask = (lowers <= value_buckets) & (value_buckets <= uppers) #this tells us for each bucket, if a value belongs in it or not 
		
		bucket_multipliers = np.stack([np.arange(xtreme_windows.shape[1])]*xtreme_windows.shape[0],axis=0)
		bucket_multipliers = bucket_multipliers / (xtreme_windows.shape[1]) #values now are between 0 and 1
		
		bucket_multipliers = (bucket_multipliers * self._early_influence) + (1 - self._early_influence)
		bucket_multipliers = np.stack([bucket_multipliers]*self._number_buckets,axis=2) #put one for each bucket
		
		bucket_values = np.sum(bucket_mask * bucket_multipliers,axis=1)
		
		#this tells us on every window where the support/resistance is 
		window_index, bucket_index  = scipy.signal.argrelmax(bucket_values,axis=1)
		_, sr_counts = np.unique(window_index,return_counts=True)
		
		max_sr_count = np.max(sr_counts)
		window_srs = np.full((xtreme_windows.shape[0],max_sr_count),np.nan)  #values of support and resistance lines
		
		cum_counts = np.concatenate([np.array([0]), np.cumsum(sr_counts)[:-1]])
		neg_array = np.repeat(cum_counts,sr_counts)
		sr_index = np.arange(neg_array.shape[0])  - neg_array  #don't care about trailing nans 
		
		window_srs[window_index,sr_index] = medians[window_index,bucket_index]
		
		#now need to figure out how to measure the quality of the breakout/if one has happened.
		#think of a number of tests that can be done for each window using the breakout candles. 
		# touching test 
		# fuck-through test 
		# else?
		
		print('do something with xtreme_windows')
		pdb.set_trace()
		
		return np.zeros((xtreme_windows.shape[0],4)) #eg 4 results per entry

#not sure if this really belongs here 
class PivotPoints(ChartPattern):
	
	_breakout_candles = 1 #only need to see where the current candle is to see if we are
	#close to a pivot point or not. 
	
	def _day_indices(self):
		
		t0 = time.time() 
		timeline = self.timeline[:,0]
		
		np_timeline = np.empty((timeline.shape[0],6))
		
		fyears = lambda dt : dt.year 
		fmonths = lambda dt : dt.month
		fdays = lambda dt : dt.day
		fhours = lambda dt : dt.hour
		fmins = lambda dt : dt.minute
		
		for i,td in enumerate(timeline):	
			np_timeline[i,0] = fyears(td)
			np_timeline[i,1] = fmonths(td)
			np_timeline[i,2] = fdays(td)
			np_timeline[i,3] = fhours(td)
			np_timeline[i,4] = fmins(td)
			np_timeline[i,5] = td.weekday() #get the day of week on the end for helping merge fri and sun
		
		np_timeline = np_timeline.astype(np.int)
		print(f"timeline iteration generation took {time.time() - t0}s")
		
		pdb.set_trace()
		print('use np_timeline to find the days. (merge fri/sunday night)?')
		
		
		
	@overrides(ChartPattern)
	def _perform(self,np_candles):
		day_indexs = self._day_indices()
		
		
		
	
	
	
	

















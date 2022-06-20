
import time
import numpy as np
import scipy.signal 
import gc

import tqdm

from charting.candle_stick_pattern import * 
import charting.candle_stick_functions as csf
from indicators.indicator import Indicator

import charting.chart_viewer as chv

import logging 
log = logging.getLogger(__name__)



from utils import overrides

#similar to the candle stick pattern - but we want to take note of all the extreme points first before sliding
# and perhaps other things like curve fits or something else that is done globally across the whole dataset, not
# just in the chart window of _required_candles
class ChartPattern(Indicator):
	
	_required_candles = 100 # a chart pattern is a long pattern of extreme points
	#_xtremes = np.array([]) # and it has all the extreme points cached ready for use in shapes & trends 
	
	_xtreme_degree = 1 #number of times to apply extreme finding algorithm. Need to figure out how to do degree > 1 - warning 
	#- a high degree might chop off relevant max/min and some windows may have 0 hits 
	
	
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
	def _perform(self,np_candles,mask=None,return_flat=False):   #allow for caching / inserting the extreme points or something so other chart patterns can be initalised with 1 dataset
		
		xtreme_windows, window_map = self._generate_xtreme_windows(np_candles,mask,self._xtreme_degree,self._precandles)
		breakout_windows = self._get_breakout_windows(np_candles,mask,self._precandles)
		x_start_positions = self._get_x_positions(np_candles,mask)
		
		chart_result = self._chart_perform(xtreme_windows, breakout_windows, x_start_positions) 
		
		if return_flat:
			return np.concatenate([window_map,chart_result],axis=1) #return the flat list of the results we have 
		
		number_windows = np_candles.shape[1] - self._required_candles + 1 - self._breakout_candles
		
		#then unmasking/expanding here - needs to be shaped properly since we might not have all the windows
		result_space = np.full((np_candles.shape[0],number_windows,chart_result.shape[-1]),np.nan)
		result_space[window_map[0],window_map[1]] = chart_result
		
		
		#result = chart_result.reshape((np_candles.shape[0],number_windows,chart_result.shape[-1])) #incorrect 
		pad_len = np_candles.shape[1] - number_windows
		pad_depth = chart_result.shape[-1]
		pad_height = np_candles.shape[0]
		padding = np.zeros((pad_height,pad_len,pad_depth))
		
		return np.concatenate([padding,result_space],axis=1)
	
	def _get_x_positions(self,np_candles,mask):
		
		number_windows = np_candles.shape[1] - self._required_candles + 1 - self._breakout_candles
		
		x_positions_singular = np.arange(self._required_candles,number_windows + self._required_candles)
		x_positions = np.concatenate([x_positions_singular]*np_candles.shape[0])
		
		
		if mask is not None:
			this_mask = mask[:,-number_windows:] #1 mask per window - chop off useless first ones
			instrument_indexs, window_indexs = np.where(this_mask) 
			select_indexs = (number_windows * instrument_indexs) + window_indexs
			
			x_positions = x_positions[select_indexs]
		
		return x_positions
	
	#get the max and min points and repeat if desired to get "less local" points 
	def _get_maxs_mins(self,high_windows,low_windows,xtreme_degree):
		#if xtreme_degree > 1:
		#	log.warning("_xtreme_degree of more than 1 has not yet been implemented. Change some stuff around below and add a for loop to get it working. ")
		
		assert high_windows.shape[1] == low_windows.shape[1], "Windows changed between lowers and highers "
		number_windows = high_windows.shape[1]
		
		maxima = scipy.signal.argrelmax(high_windows,axis=2)
		minima = scipy.signal.argrelmin(low_windows,axis=2)
		
		index_map = np.stack([np.arange(self._required_candles)]*number_windows,axis=0)
		index_map = np.stack([index_map]*high_windows.shape[0],axis=0)
		
		#index_map = np.copy(index_map)
		#mimimum_index_map = np.copy(index_map)
		
		for _ in range(1,xtreme_degree):
				
			#handle max change 
			max_vals = high_windows[maxima]	
			max_vals = max_vals[:,np.newaxis]
			
			maxima_tups = np.stack(maxima,axis=1)
			maximum_points = np.concatenate([maxima_tups,max_vals],axis=1)
			
			max_window_numbers = (number_windows * maximum_points[:,0]) + maximum_points[:,1]
			
			re_maximum_points = np.concatenate([max_window_numbers[:,np.newaxis],maximum_points],axis=1)
			window_coords, counts = np.unique(re_maximum_points[:,0],return_counts=True)
			max_extr_count = np.max(counts) 
			
			these_maximums = np.full((high_windows.shape[0],number_windows,max_extr_count),np.nan)
			new_max_index_map = np.full((high_windows.shape[0],number_windows,max_extr_count),np.nan)
			
			
			cum_counts = np.concatenate([np.array([0]), np.cumsum(counts)[:-1]])
			neg_array = np.repeat(cum_counts,counts)
			max_index = np.arange(neg_array.shape[0]) - neg_array
			#pdb.set_trace()
			
			these_maximums[maxima[0],maxima[1],max_index] = high_windows[maxima]
			new_max_index_map[maxima[0],maxima[1],max_index] = index_map[maxima]
			
			new_maxima = scipy.signal.argrelmax(these_maximums,axis=2) #map back somehow... 
			new_maxima_end = new_max_index_map[new_maxima].astype(np.int)
			maxima = (new_maxima[0],new_maxima[1],new_maxima_end)
			
			
			
			
			#handle min change
			min_vals = low_windows[minima]	
			min_vals = min_vals[:,np.newaxis]
			
			minima_tups = np.stack(minima,axis=1)
			minimum_points = np.concatenate([minima_tups,min_vals],axis=1)
			
			min_window_numbers = (number_windows * minimum_points[:,0]) + minimum_points[:,1]
			
			re_minimum_points = np.concatenate([min_window_numbers[:,np.newaxis],minimum_points],axis=1)
			window_coords, counts = np.unique(re_minimum_points[:,0],return_counts=True)
			min_extr_count = np.max(counts) 
			
			these_minimums = np.full((low_windows.shape[0],number_windows,min_extr_count),np.nan)
			new_min_index_map = np.full((low_windows.shape[0],number_windows,min_extr_count),np.nan)
			
			
			cum_counts = np.concatenate([np.array([0]), np.cumsum(counts)[:-1]])
			neg_array = np.repeat(cum_counts,counts)
			min_index = np.arange(neg_array.shape[0]) - neg_array
			#pdb.set_trace()
			
			these_minimums[minima[0],minima[1],min_index] = low_windows[minima]
			new_min_index_map[minima[0],minima[1],min_index] = index_map[minima]
			
			new_minima = scipy.signal.argrelmin(these_minimums,axis=2) #map back somehow... 
			new_minima_end = new_min_index_map[new_minima].astype(np.int)
			minima = (new_minima[0],new_minima[1],new_minima_end)
			
			
			
		return maxima, minima 
	
	
	def _generate_xtreme_windows(self,np_candles,mask=None,xtreme_degree=1,precandles=None): #use for getting the extreme points for each window 

		
			
		number_windows = np_candles.shape[1] - self._required_candles + 1 - self._breakout_candles
		
		np_highs = np_candles[:,:,csf.high] 
		np_lows = np_candles[:,:,csf.low]
		
		if callable(precandles):
			#np_candles_again = precandles._perform(np_candles)
			pass # perform precandles on np_candles 
		
		#now stride trick
		high_windows = np.lib.stride_tricks.sliding_window_view(np_highs[:,:-self._breakout_candles],window_shape=self._required_candles,axis=1)
		low_windows = np.lib.stride_tricks.sliding_window_view(np_lows[:,:-self._breakout_candles],window_shape=self._required_candles,axis=1)
		
		assert high_windows.shape[1] == number_windows, "number of windows is not accurate"
		assert low_windows.shape[1] == number_windows, "number of windows is not accurate"
		
		
		maxima,minima = self._get_maxs_mins(high_windows, low_windows, xtreme_degree)
		
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
		
		if mask is not None:
			this_mask = mask[:,-number_windows:] #1 mask per window - chop off useless first ones
			instrument_indexs, window_indexs = np.where(this_mask) 
			select_indexs = (number_windows * instrument_indexs) + window_indexs
			
			xtreme_windows = xtreme_windows[select_indexs]
			window_map = window_map[:,select_indexs]
		
		return xtreme_windows, window_map 
		
		
	
	def _get_breakout_windows(self,np_candles,mask=None,precandles=None):
		
		if callable(precandles):
			pass 
		
		np_opens = np_candles[:,:,csf.open]
		np_highs = np_candles[:,:,csf.high] 
		np_lows = np_candles[:,:,csf.low]
		np_closes = np_candles[:,:,csf.close]
		
		bo_open_windows = np.lib.stride_tricks.sliding_window_view(np_opens,window_shape=self._breakout_candles,axis=1)
		bo_high_windows = np.lib.stride_tricks.sliding_window_view(np_highs,window_shape=self._breakout_candles,axis=1)
		bo_low_windows = np.lib.stride_tricks.sliding_window_view(np_lows,window_shape=self._breakout_candles,axis=1)
		bo_close_windows = np.lib.stride_tricks.sliding_window_view(np_closes,window_shape=self._breakout_candles,axis=1)
		
		number_windows = np_candles.shape[1] - self._required_candles + 1 - self._breakout_candles
		
		breakout_windows = np.stack([bo_open_windows,bo_high_windows,bo_low_windows,bo_close_windows],axis=3)
		breakout_clip = breakout_windows.shape[1] - number_windows
		breakout_windows = breakout_windows[:,breakout_clip:,:,:]
		breakout_windows = breakout_windows.reshape((breakout_windows.shape[0]*breakout_windows.shape[1],breakout_windows.shape[2],breakout_windows.shape[3]))
		
		if mask is not None:
			this_mask = mask[:,-number_windows:] #1 mask per window - chop off useless first ones
			instrument_indexs, window_indexs = np.where(this_mask) 
			select_indexs = (number_windows * instrument_indexs) + window_indexs
			
			breakout_windows = breakout_windows[select_indexs]
		
		return breakout_windows 
	
	
	#This function should operate on an np list of windows, independently of the time frame and the instrument. 
	#the mapping is taken care of in perform 
	def _chart_perform(self,xtreme_windows, breakout_windows, x_start_pos): 
		raise NotImplementedError('This method must be overridden')
	
	
	
	@overrides(Indicator)
	def detect(self,candle_stream,candle_stream_index=-1,criteria=[]): #for now, ignore criteria 
		return self.calculate(candle_stream,candle_stream_index)
	
	@overrides(Indicator)
	def draw_snapshot(self,np_candles,snapshot_index,instrument_index):
		mask = self._create_mask(np_candles,instrument_index,snapshot_index)
		xtreme_windows, _ = self._generate_xtreme_windows(np_candles,mask,xtreme_degree=self._xtreme_degree,precandles=self._precandles)
		
		#draw each window extreme points onto the chart 
		this_view = chv.ChartView()
		for xw in xtreme_windows:	
			
			min_points = [chv.Point(x,y) for (x,y,t) in xw if t == 0]
			max_points = [chv.Point(x,y) for (x,y,t) in xw if t == 1]
			this_view.draw('debug bullish points',min_points)
			this_view.draw('debug bearish points',max_points)
					
		return this_view
		
		
	def _create_mask(self,np_candles,instrument_index,time_index=None): #produces a mask with true on the indexs we want
		
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
	
	@staticmethod #use this method to place jagged masks along time into a new array 
	def _mask_to_flatlist(npw_array,mask,fill_value=np.nan,just_right=False):
		w_index, p_index = np.where(mask)
		return ChartPattern._premask_to_flatlist(npw_array,w_index,p_index,fill_value,just_right)
		
	@staticmethod
	def _premask_to_flatlist(npw_array,w_index, p_index,fill_value=np.nan,just_right=False):
		_, counts = np.unique(w_index,return_counts=True)
		max_counts = np.max(counts) 
		destination_shape = (npw_array.shape[0],max_counts,npw_array.shape[-1])
		destination = np.full((destination_shape),fill_value)
		cum_counts = np.concatenate([np.array([0]), np.cumsum(counts)[:-1]])
		neg_array = np.repeat(cum_counts,counts)
		if just_right:
			buffers = np.repeat(np.max(counts) - counts,counts) #buffers push the xtremes forwards so nan values are first
			neg_array = neg_array - buffers
		np_index = np.arange(w_index.shape[0]) - neg_array
		destination[w_index,np_index] = npw_array[w_index,p_index]
		return destination

class SupportAndResistance(ChartPattern):  #group together points along the price line, show resistance/support lines where there are significant groups 
	
	_required_candles = 200
	_number_buckets = 10 #increase for resolution/accuracy? 
	_early_influence = 0.4 #how much should earlier points count towards the bucket count 
	
	@overrides(ChartPattern)
	def _chart_perform(self, xtreme_windows, breakout_windows, x_start_pos):			
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
		
		#window_srs = self._premask_to_flatlist(medians,window_index, bucket_index) #experiment that went wrong (:
		
		#now need to figure out how to measure the quality of the breakout/if one has happened.
		#think of a number of tests that can be done for each window using the breakout candles. 
		# touching test 
		# fuck-through test 
		# else?
		
		#print('do something with xtreme_windows')
		pdb.set_trace()
		
		return np.zeros((xtreme_windows.shape[0],4)) #eg 4 results per entry
	
	#@overrides(Indicator)
	#def draw_snapshot(self,np_candles,snapshot_index,instrument_index):
	#	pass
	
	
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
		
		
		
		
	
	
	
	

















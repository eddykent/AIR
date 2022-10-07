
import numpy as np 
#import scipy


import pdb

import time

import charting.chart_viewer as chv 
import charting.candle_stick_functions as csf
from setups.signal import TradeSignal, TradeDirection
from utils import overrides 

from charting.chart_pattern import ChartPattern



class ShapePattern(ChartPattern):
	
	_shape_levels = [[2,1,3,1,2]]
	_group_width = 1 #atr distance? 
	_group_distance = 1.2 #distance between averages in each group 
	_order = 7
	_shape_direction = TradeDirection.SELL #VOID  
	
	@overrides(ChartPattern)
	def _chart_perform(self, xtreme_bundle):
		
		xtreme_windows = xtreme_bundle.xtreme_windows
		breakout_windows = xtreme_bundle.breakout_windows
		x_start_pos = xtreme_bundle.x_start_positions
		
		time_start = time.time()
		shape_levels = self._shape_levels[0] #append results of every shape later. also for now assume shape_levels array is well behaved 
		
		shape_length = len(shape_levels) 
		n_groups = np.max(shape_levels) + 1
		n_windows = xtreme_windows.shape[0]
		
		shapes = xtreme_windows[:,-shape_length:,:] 
		
		window_indexs = np.repeat(np.arange(n_windows),(n_groups*shape_length))
		group_indexs = np.array(shape_levels*(n_windows*n_groups))
		shape_indexs = np.array(list(range(shape_length))*(n_windows*n_groups))
		
		group_values = np.full((xtreme_windows.shape[0],n_groups,shape_length),np.nan)
		
		#now populate
		group_values[window_indexs,group_indexs,shape_indexs] = shapes[window_indexs,shape_indexs,1]
		
		group_mins = np.nanmin(group_values,axis=2)
		group_maxs = np.nanmax(group_values,axis=2)
		group_aves = np.nanmean(group_values,axis=2)
		
		gap = 0 #change later
		level_dev = 1 #not sure how to use this yet - is the max width/deviation allowed from the meean of each level 
		
		group_names = list(range(n_groups)) 
		groups_paired = zip(group_names[0:-1],group_names[1:])
		groups_arranged = np.all([ (group_maxs[:,f] + gap) < group_mins[:,s] for (f,s) in groups_paired],axis=0)
		groups_thin = np.all(np.maximum(np.abs(group_aves-group_mins),np.abs(group_aves-group_maxs)) < level_dev,axis=1) 
		
		time_taken = time.time() - time_start
		
		print('time taken was '+str(time_taken))
		pdb.set_trace()
		print('how to check groups? ') 
		
	
		
	def _test_shapes(self,shapes):
		for shape_levels in self._shape_levels:
			for level in shape_levels:
				pass
		
		

class DoubleExtreme(ShapePattern):
	
	_shape_levels = [[2,1,2]] 
	_shape_direction = TradeDirection.SELL
	

class HeadAndShoulders(ShapePattern):
	_shape_levels = [[1,0,2,0,1]]





#class HeadAndShoulders, TeacupHandle, TwoTopBottom, ThreeTopBottom etc 












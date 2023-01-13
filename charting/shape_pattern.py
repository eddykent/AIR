
import numpy as np 
#import scipy


import pdb

import time
from collections import namedtuple
from enum import Enum

import charting.chart_viewer as chv 
import charting.candle_stick_functions as csf
from setups.signal import TradeSignal, TradeDirection
from utils import overrides 

from charting.chart_pattern import ChartPattern

#should this shape be at the top/bottom of a window?
class WindowConstraint(Enum):
	TOP = 1
	NONE = 0
	BOTTOM = -1

ShapeDescription = namedtuple('ShapeDescription','levels direction window_constraint level_deviation gap_width note')


class ShapePattern(ChartPattern):
	
	_shapes = []#[[2,1,3,1,2]]
	_order = 7 #default 
	_breakout_candles = 2
	
	#window constraints 
	_ignore_window_constraints = False 
	_max_window_extreme_ago = 5
  
	
	@overrides(ChartPattern)
	def _chart_perform(self, xtreme_bundle):
		
		xtreme_windows = xtreme_bundle.xtreme_windows
		breakout_windows = xtreme_bundle.breakout_windows
		x_start_pos = xtreme_bundle.x_start_positions
		relative_gap = xtreme_bundle.average_true_ranges
		 
		#time_start = time.time()
		
		shape_result = self._test_all_shapes(xtreme_windows,relative_gap,x_start_pos)
				
		#time_taken = time.time() - time_start
		
		#print('time taken was '+str(time_taken))
		#pdb.set_trace()
		#remember this returns the detection first then the rest of the details afterwards  
		#what else should be added to shape result? 
		return shape_result
	
	
	def _test_all_shapes(self,xtreme_windows,relative_gap,x_pos):
		
		result_buys = np.stack([self._test_shape(xtreme_windows,shape,relative_gap,TradeDirection.BUY,x_pos) for shape in self._shapes],axis=1)
		result_sells = np.stack([self._test_shape(xtreme_windows,shape,relative_gap,TradeDirection.SELL,x_pos) for shape in self._shapes],axis=1)
		
		all_results = result_buys.astype(np.int) - result_sells.astype(np.int)  #array of -1,0,1
		shape_indexs = np.argmax(np.abs(all_results),axis=1)
		
		bias = all_results[np.arange(shape_indexs.shape[0]),shape_indexs]
		shape_indexs[bias == 0] = -1 
		return np.stack([bias,shape_indexs],axis=1)
		
		
	
	def _test_shape(self,xtreme_windows,shape_description,relative_gap,direction,pattern_end): #
		
		assert len(relative_gap)
		#pdb.set_trace()
		
		shape_levels = self._get_levels(shape_description,direction) #we can assume levels is well behaved here
		shape_length = shape_levels.shape[0]
		n_groups = np.max(shape_levels) + 1
		n_windows = xtreme_windows.shape[0]
		
		xtreme_length = xtreme_windows.shape[1]
		values = xtreme_windows[:,:,1]
		
		nan_rows = np.all(np.isnan(values),axis=1)
		low_rows = (xtreme_length - np.sum(np.isnan(values),axis=1)) < shape_length
		
		last_extreme = xtreme_windows[:,-1,0]
		
		shapes = xtreme_windows[:,-shape_length:,:] 
				
		window_indexs = np.repeat(np.arange(n_windows),(n_groups*shape_length))
		#group_indexs = np.array(shape_levels.tolist()*(n_windows*n_groups))  #hack since i dont know how to repeat this correclty 
		#shape_indexs = np.array(list(range(shape_length))*(n_windows*n_groups))
		group_indexs = np.tile(shape_levels,(n_windows*n_groups))
		shape_indexs = np.tile(np.arange(shape_length),(n_windows*n_groups))
		group_values = np.full((xtreme_windows.shape[0],n_groups,shape_length),np.nan)
		
		group_values[window_indexs,group_indexs,shape_indexs] = shapes[window_indexs,shape_indexs,1]
		
		group_result_shape = (group_values.shape[0],group_values.shape[1])
		group_mins = np.nanmin(group_values,axis=2)
		group_maxs = np.nanmax(group_values,axis=2)
		group_aves = np.nanmean(group_values,axis=2)
		
		gap = relative_gap * shape_description.gap_width
		level_dev = np.transpose([relative_gap * shape_description.level_deviation] * n_groups)
		
		group_names = list(range(n_groups)) 
		groups_paired = zip(group_names[0:-1],group_names[1:])
		groups_arranged = np.all([ (group_maxs[:,f] + gap) < group_mins[:,s] for (f,s) in groups_paired],axis=0)
		groups_thin = np.all(np.maximum(np.abs(group_aves-group_mins),np.abs(group_aves-group_maxs)) < level_dev,axis=1) 
		
		window_constraints = np.full(groups_thin.shape,True)
		
		if not self._ignore_window_constraints:
			
			window_constraints = np.full(groups_thin.shape,False)
					
			#pdb.set_trace()
			window_constraint_direction = self._get_window_constraint_direction(shape_description,direction)	
			if window_constraint_direction == WindowConstraint.TOP:
				#max is in the shape
				window_constraints[~nan_rows] = np.nanargmax(values[~nan_rows,:],axis=1) >= (xtreme_length - shape_length)
				
			
			if window_constraint_direction == WindowConstraint.BOTTOM:
				#min is in the shape
				window_constraints[~nan_rows] = np.nanargmin(values[~nan_rows,:],axis=1) >= (xtreme_length - shape_length)
			
			expired = last_extreme + self._max_window_extreme_ago < pattern_end
			window_constraints = window_constraints & (~expired)  #ensure the last extreme is not too long gone 
			
		result_ok = groups_arranged & groups_thin & window_constraints 
		result_ok[low_rows] = False
		return result_ok
	
	def _get_window_constraint_direction(self,shape_description,direction):
		window_constraint = shape_description.window_constraint
		if window_constraint == WindowConstraint.NONE:
			return WindowConstraint.NONE 
		if direction == TradeDirection.VOID:
			return WindowConstraint.NONE
		if self._ignore_window_constraints:
			return WindowConstraint.NONE 
		if shape_description.direction != direction: #flip since we are going in other direction 
			if window_constraint == WindowConstraint.TOP:
				window_constraint = WindowConstraint.BOTTOM 
			else:
				window_constraint = WindowConstraint.TOP
		return window_constraint
		
		
		
	
	def _get_levels(self,shape_description,direction):
		shape_levels = np.array(shape_description.levels)
		if direction == TradeDirection.VOID or shape_description.direction == TradeDirection.VOID:
			return []
		
		if direction != shape_description.direction:
			shape_levels = -shape_levels
		
		shape_levels = ShapePattern.dirtyrank(shape_levels)
		return shape_levels #change to ensure it is "well behaved" and flipped if the direction is wrong
	
	@overrides(ChartPattern)
	def draw_snapshot(self,np_candles,instrument_index,snapshot_index):
		mask = self._create_mask(np_candles,instrument_index,snapshot_index)
		xtreme_windows, _ = self._generate_xtreme_windows(np_candles,mask)
		atr = self._get_average_true_ranges(np_candles,mask)
		x_start_pos = self._get_x_positions(np_candles,mask)
		
		this_view = chv.ChartView()
		
		shape_result = self._test_all_shapes(xtreme_windows,atr,x_start_pos) #list of (bias, shapes_index) (if -1 then dont draw it) 
		#pdb.set_trace()
		for xwi,(bias,shape_index) in enumerate(shape_result):	
			if shape_index < 0: #if you want to draw any shape, get the first index 
				continue
			dirst = 'bullish' if bias > 0 else 'bearish'
			shapelen = len(self._shapes[shape_index].levels)
			xwindow = xtreme_windows[xwi,-shapelen:,0:2]
			path = [chv.Point(int(x),y) for x,y in xwindow]
			this_view.draw('patterns '+dirst+' path',path)
		
		return this_view
	
	@staticmethod
	def dirtyrank(numarray):
		values = numarray.copy().astype(np.float)
		ind = 0 
		result = np.zeros(values.shape).astype(np.int)
		while not np.isnan(values).all():
			min = np.nanmin(values)
			min_mask = np.where(values == min)
			values[min_mask] = np.nan
			result[min_mask] = ind
			ind = ind + 1
		return result 
		
		
class DoubleExtreme(ShapePattern):
	
	_order = 10
	
	_shapes = [
		ShapeDescription([1,0,1],TradeDirection.SELL,WindowConstraint.TOP,0.5,5,"tight large middle"),
		#ShapeDescription([1,0,1],TradeDirection.SELL,0.2,1,"tighter double top with large middle")
	] 
	
class TripleExtreme(ShapePattern):
	
	_order = 10
	
	_shapes = [
		ShapeDescription([2,1,2,0,2],TradeDirection.SELL,WindowConstraint.TOP,0.5,5,"unbalanced lows"),
		ShapeDescription([1,0,1,0,1],TradeDirection.SELL,WindowConstraint.TOP,0.5,5,"balanced lows"),
	]

class HeadAndShoulders(ShapePattern):
	
	_order = 7
	
	_shapes = [
		ShapeDescription([1,0,2,0,1],TradeDirection.SELL,WindowConstraint.TOP,0.5,3,"balanced neckline"), #balanced neckline
		#ShapeDescription([2,1,3,0,1],TradeDirection.SELL,0.5,1,"unbalanced neckline")  #declining neckline 
	]





#class HeadAndShoulders, TeacupHandle, TwoTopBottom, ThreeTopBottom etc 














import numpy as np
import datetime

from enum import Enum
from collections import namedtuple

import charting.candle_stick_functions as csf
from charting.candle_stick_pattern import CandleStickPattern
from charting.chart_pattern import *
import charting.chart_viewer as chv

#import charting.trend_line_functions as tlf
#from charting.trend_line_functions import TrendLine

ShapePoint = namedtuple('ShapePoint','x y')

#not sure how to do this yet - thinking get the levels and then number them then see if the price action hits them in the correct order (or similar) 
#we may want to use median price or typical price for these patterns not full candlesticks
class ShapePattern(SupportAndResistance):
	
	level_smudge_distance = 3 #if points are within this distance then treat them as one
	level_gap_multiplier = 0.75 #push levels more apart by this much
	shape_point_gap_multiplier = 0.2 #points must be at most this far awat from the level to be declared as on that level
	
	sma_window = 1
	
	walk_shapes= [[2,0,1,0,2]]#example
	
	def _calculate_local_extremes(self,candle_stream):	#local in the sense of a local minimum/maximum not the memory window 
		#find extreme points using the fractal approach
		_extreme_points = []
		
		#lets use typical price and smooth with sma(5) to get better results?
		typicals = [csf.typical(candle) for candle in candle_stream]
		smoothed_typicals = self._window_function(np.mean,typicals,self.sma_window)
		
		for index in range(self._fractal_size,len(smoothed_typicals)-self._fractal_size):
			smoothed_typical_block = smoothed_typicals[index-self._fractal_size:index+self._fractal_size+1]
			
			if self._fractal_up(smoothed_typical_block,self._fractal_size):
				_extreme_points.append(Extremity(ExtremityType.MINIMUM,min(smoothed_typical_block),index-1)) #index is at the middle of the fractal?
				
			elif self._fractal_down(smoothed_typical_block,self._fractal_size):
				_extreme_points.append(Extremity(ExtremityType.MAXIMUM,max(smoothed_typical_block),index-1))
				
		#then using a sliding window approach 
		#current_min = MAX_ERROR_VALUE
		#current_max = -1
		#for index in range(len(smoothed_typicals)):#- self._local_extreme_window_size):
		#	smoothed_typical_block = smoothed_typicals[index:index+self._local_extreme_window_size]
		#	#use a fractal to get rid of annoying sliding window errors 
		#	fractal = smoothed_typicals[max(0,index-1):min(index+2,len(smoothed_typicals))]  
		#	
		#	_high = max(smoothed_typical_block)
		#	_low = min(smoothed_typical_block)
		#	if _high > current_max:
		#		current_max = _high
		#	if _low < current_min:
		#		current_min = _low
		#	
		#	value = smoothed_typicals[index]
		#	if value == current_max:# and self.__fractal_down(fractal,1):
		#		_extreme_points.append(Extremity(ExtremityType.MAXIMUM,current_max,index-1))
		#		current_max = -1
		#	elif value == current_min:# and self.__fractal_up(fractal,1): 
		#		_extreme_points.append(Extremity(ExtremityType.MINIMUM,current_min,index-1))
		#		current_min = MAX_ERROR_VALUE
		
		#sort them in their index order so they are easy to iterate through
		self._extreme_points = sorted(set(_extreme_points),key=lambda p: p.index)
			
	
	#def _highers_lowers(self,candle_stream_index):
	#	extremes  = list(reversed(self._get_extremes(candle_stream_index - self.pattern_start_index))) #working backwards from current index 
	#	lows = [ep for ep in extremes if ep.type == ExtremityType.MINIMUM]
	#	highs  = [ep for ep in extremes if ep.type == ExtremityType.MAXIMUM]
	#	return highs,lows 
	
	def find_shape_points(self,candle_stream,candle_stream_index):
		#get some levels from the support and resistance pattern
		#trace back through each level and note down points that are very close to it 
		#group x values together that are consecutive and use the middle as the shape point 
		#return shape points for shape testing
		extreme_points  = list(reversed(self._get_extremes(candle_stream_index - self.pattern_start_index)))
		
		start_level = csf.median(candle_stream[max(candle_stream_index-self.pattern_start_index,0)])
		
		max_gap = self._rolling_range_mean[candle_stream_index]
		level_gap = self.level_gap_multiplier * max_gap
		levels = self._generate_levels(extreme_points,start_level,level_gap)
		
		if not levels:
			return []
		
		shape_point_gap = self.shape_point_gap_multiplier * max_gap
		
		shape_points = [] 
		for level in levels:
			smudge_points = []
			close_points = self._close_points_to_level(level,extreme_points,shape_point_gap)
			extreme_highs = 0
			extreme_lows = 0
			for close_point in close_points: #fix the level values 
				if not smudge_points or close_point.index <= smudge_points[0].index + self.level_smudge_distance: #we are working backwards!
					smudge_points.append(Extremity(close_point.type,level,close_point.index))
					if close_point.type == ExtremityType.MAXIMUM:
						extreme_highs += 1
					if close_point.type == ExtremityType.MINIMUM:
						extreme_lows += 1
				else:
					new_index = int(np.mean([smudge_point.index for smudge_point in smudge_points])) #floor it?
					extreme_type = ExtremityType.MAXIMUM if extreme_highs > extreme_lows else ExtremityType.MINIMUM if extreme_highs < extreme_lows else ExtremityType.VOID
					shape_points.append(Extremity(extreme_type,level,new_index))
					smudge_points.clear()
					extreme_highs,extreme_lows = 0,0
			if smudge_points:
				new_index = round(np.mean([smudge_point.index for smudge_point in smudge_points])) #floor it?
				extreme_type = ExtremityType.MAXIMUM if extreme_highs > extreme_lows else ExtremityType.MINIMUM if extreme_highs < extreme_lows else ExtremityType.VOID
				shape_points.append(Extremity(extreme_type,level,new_index))
		
		return shape_points#add some actual error value?
	
	
	def shape_match(self,points,walk):
		turning_points = self.turning_points(points)
		
		#there needs to be enough defined turning points 
		if len(turning_points) >= len(walk):
			#check approximate structure of turning points by collecting the turning points into walk-levels 
			turning_point_groups = []
			for walk_level in range(0,max(walk)+1):
				turning_point_group = []
				for footstep,turning_point in zip(walk,turning_points[:len(walk)]):
					if footstep == walk_level:
						turning_point_group.append(turning_point)
				turning_point_groups.append(turning_point_group)
			
			#now for each group, check if they are in order
			for ltpg,utpg in zip(turning_point_groups[:-1],turning_point_groups[1:]):
				if not all(ltp.value < utp.value for ltp in ltpg for utp in utpg):
					return False, [] 
			
			return True, turning_point_groups #not sure if bullish or bearish?
			
		return False, []  # for no match, 1 for bullish 0 for bearish. Need fitness parameter too? 
	
	def _determine(self,candle_stream_index,candle_stream):
		raise NotImplementedError('This method must be overridden')
	
	@staticmethod
	def _shape_inverse(walk_shape):
		m = max(walk_shape)
		return [m-s for s in walk_shape]
	
	#walk through walk and add points on every direction change. check the points for the pattern 
	@staticmethod
	def turning_points(points):
		if len(points) < 2:
			return []
		increasing = True
		turning_points = []
		prev_point = None
		for point in points:
			if increasing:
				if not prev_point or point.value < prev_point.value:  #we have changed direction!
					turning_points.append(prev_point)
					increasing = False
			else:
				if not prev_point or point.value > prev_point.value: #changed direction
					turning_points.append(prev_point)
					increasing = True
			prev_point = point
	

class TopAndBottom(ShapePattern):
	
	walk_shapes = [[0,2,1,2,0],[0,3,2,3,1]]
	
	def _determine(self,candle_stream_index,candle_stream):
		shape_points = self.find_shape_points(candle_stream,candle_stream_index)
		
		
		
	def draw_snapshot(self,candle_stream,snapshot_index):
		base_view = super().draw_snapshot(candle_stream,snapshot_index) #gets the support/resistance lines - do we really want these though? 
		
		coords = self.find_shape_points(candle_stream,snapshot_index)
		if coords:
			base_view.draw('patterns neutral points',[chv.Point(coord.index, coord.value) for coord in coords]) #mapping needed?
		
		return base_view

class HeadAndShoulders(ShapePattern):
	
	walk_shapes = [[0,2,0,3,0,1,0]]  #or [0 1,0,2,0,1,0]

class TeacupHandle(ShapePattern):
	pass


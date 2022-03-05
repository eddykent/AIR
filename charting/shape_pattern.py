

import numpy as np
import datetime

from enum import Enum
from collections import namedtuple

import charting.candle_stick_functions as csf
from charting.chart_pattern import *
import charting.chart_viewer as chv

#import charting.trend_line_functions as tlf
#from charting.trend_line_functions import TrendLine

#ShapePoint = namedtuple('ShapePoint','x y')


#use a least squares algorithm to find all extreme points 
class ChartPatternLeastSquares(ChartPattern):
	
	degree = 17 #the degree of function in which to use for the least squares curve fit
	memory_window = 120
	
	#override this in FFT version
	def _fit_function(self,values):
		xs = range(len(values))
		ys = values
		
		poly = Poly.fit(xs,ys,self.degree)
		curve = [poly(x) for x in xs] 
		return curve
	
	def _get_start_end_index(self,candles,candle_index):
		start_index = max(0,candle_index-self.memory_window)
		end_index = min(start_index+self.memory_window+1,len(candles))
		return start_index, end_index
	
	def _get_curve(self,candles,start_index,end_index):	
		#candle_mapper = lambda c: c[csf.low]
		#candle_mapper = lambda c: c[csf.high]
		#candle_mapper = csf.mean
		candle_mapper = csf.typical #maps the candle to a value
		candle_window = candles[start_index:end_index]
		values = list(reversed([candle_mapper(candle) for candle in candle_window]))  #start from the latest
		curve = list(reversed(self._fit_function(values)))   #reverse back result to put it into the correct order
		return curve
	
	#rename to get_extremes when ready? 
	def _get_stationary_points(self,curve,candles,start_index,end_index):  
		
		stationary_points = []
		indexs = range(start_index+1,end_index-1)   #clip ends off as we don't know if there is a local minimum at each end
		for index,p1,p2,p3 in zip(indexs,curve[:-2],curve[1:-1],curve[2:]):
			if self._fractal_down([p1,p2,p3],1):
				#found max
				local_max = candles[index][csf.high] #csf.highest(candles[index-1:index+2])
				stationary_points.append(Extremity(ExtremityType.MAXIMUM,local_max,index))
			if self._fractal_up([p1,p2,p3],1):
				#found min
				local_min = candles[index][csf.low] #csf.lowest(candles[index-1:index+2])
				stationary_points.append(Extremity(ExtremityType.MINIMUM,local_min,index))
		
		#current_point = Extremity(ExtremityType.VOID,csf.median(candles[candle_index]),candle_index)
		# +  [current_point]
		return stationary_points[:-1]
	
	def _find_shape_points(self,candles,candle_index):
		start_index, end_index = self._get_start_end_index(candles,candle_index)
		curve = self._get_curve(candles,start_index,end_index)
		return self._get_stationary_points(curve,candles,start_index,end_index)
		
	def draw_snapshot(self,candles,snapshot_index):
		base_view = super().draw_snapshot(candles,snapshot_index)
		
		start_index, end_index = self._get_start_end_index(candles,snapshot_index)
		curve = self._get_curve(candles,start_index,end_index)
		path = [] 
		for i,y in enumerate(curve):
			x = i + start_index
			path.append(chv.Point(x,y))
		
		base_view.draw('price_actions keyinfo paths',path)
		
		return base_view



class ShapePattern(ChartPatternLeastSquares):
	
	#bullish_walk_shapes= [[2,0,1,0,2]]#example
	
	def _determine(self,candle_stream_index,candle_stream):
		raise NotImplementedError('This method must be overridden')
	
	@staticmethod
	def _group_by_walk(walk,points):
				#there needs to be enough defined points 
		if len(points) >= len(walk):
			#check approximate structure of points by collecting the points into walk-levels 
			point_groups = [] #  [[]]*(max(walk)+1) #this repeats the same list in a reference!
			[point_groups.append([]) for i in range(max(walk)+1)]#need to do it this way to prevent reference copy
			
			for point, walk_level in zip(points[:len(walk)],walk):
				point_groups[walk_level].append(point)
			
			return point_groups
			
		return []
	
	@staticmethod
	def _check_walk_groups(walk_groups, gap):
		#now for each group, check if they are in the correct order from eachother
		if len(walk_groups) <= 1:
			return True #nothing to check - all in walk group fine! :) 
			
		for lpg,upg in zip(walk_groups[:-1],walk_groups[1:]):
			if any(lp.value > up.value - gap  for lp in lpg for up in upg):
				return False
		
		return True
	
	@staticmethod
	def _walk_inverse(walk_shape):
		m = max(walk_shape)
		return [m-s for s in walk_shape]
	

class DoubleTopAndBottom(ShapePattern):
	
	#BULLISH SHAPES ONLY! we can find the bearish shapes by _shape_inverse
	walk_shapes = [
		[2,0,1,0,1], 
		[1,0,1,0,1]
	] 
	
	def _determine(self,candle_stream_index,candle_stream):
		
		shape_points = self._find_shape_points(candle_stream,candle_stream_index)
		if not shape_points:
			return 0 
		
		gap = self._rolling_range_mean[candle_stream_index] / 4.0
		
		bullish_walk_shapes = [list(reversed(walk)) for walk in self.walk_shapes]   #we want to check the points from latest to earliest
		bearish_walk_shapes = [self._walk_inverse(walk) for walk in bullish_walk_shapes]
		shape_points = sorted(shape_points,key=lambda sp:sp.index,reverse=True) #we want to ensure the points are from latest to earliest
		
		for bull_walk in bullish_walk_shapes:
			walk_groups = self._group_by_walk(bull_walk,shape_points)
			is_match = self._check_walk_groups(walk_groups,gap)
			if is_match:
				return 1.0 * self.walk_fitness(walk_groups)
		
		for bear_walk in bearish_walk_shapes:
			walk_groups = self._group_by_walk(bear_walk,shape_points)
			is_match = self._check_walk_groups(walk_groups,gap)
			if is_match:
				return -1.0 * self.walk_fitness(walk_groups)
		
		return 0
	
	def walk_fitness(self,walk_groups,bullbear=0):
		return 1
	
	
	def draw_snapshot(self,candle_stream,snapshot_index):
		base_view = super().draw_snapshot(candle_stream,snapshot_index) #gets the support/resistance lines - do we really want these though? 
		
		coords = self._find_shape_points(candle_stream,snapshot_index)
		if coords:
			base_view.draw('patterns neutral points',[chv.Point(coord.index, coord.value) for coord in coords]) #mapping needed?
		
		return base_view

class TripleTopAndBottom(DoubleTopAndBottom):
	#BULLISH SHAPES ONLY! we can find the bearish shapes by _shape_inverse
	walk_shapes = [
		[2,0,1,0,1,0,1]
	] 

class HeadAndShoulders(DoubleTopAndBottom):
	
	walk_shapes = [
		[3,1,3,0,3,2,3]
	]  #or [0 1,0,2,0,1,0]

class TeacupHandle(DoubleTopAndBottom):
	pass


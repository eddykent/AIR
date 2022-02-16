

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








class ShapePattern(ChartPatternLeastSquares):
	
	#bullish_walk_shapes= [[2,0,1,0,2]]#example
	
	def _walk_match(self,walk,points):
		
		#there needs to be enough defined points 
		if len(points) >= len(walk):
			
			#check approximate structure of points by collecting the points into walk-levels 
			point_groups = [[]]*(max(walk)+1)
			for point, walk_level in zip(points,walk):
				point_groups[walk_level].append(point)
				
			#now for each group, check if they are in the correct order from eachother
			for lpg,upg in zip(point_groups[:-1],point_groups[1:]):
				if not all(lp.value < up.value for lp in lpg for up in upg):
					return False, [] 
			
			return True, point_groups #not sure if bullish or bearish?
			
		return False, []  # for no match, 1 for bullish 0 for bearish. Need fitness parameter too? 
	
	def _determine(self,candle_stream_index,candle_stream):
		raise NotImplementedError('This method must be overridden')
	
	@staticmethod
	def _walk_inverse(walk_shape):
		m = max(walk_shape)
		return [m-s for s in walk_shape]
	

class TopAndBottom(ShapePattern):
	
	#BULLISH SHAPES ONLY! we can find the bearish shapes by _shape_inverse
	walk_shapes = [
		[0,1,0,1]
	] 
	
	def _determine(self,candle_stream_index,candle_stream):
		
		shape_points = self._find_shape_points(candle_stream,candle_stream_index)
		if not shape_points:
			return 0 
		
		bullish_walk_shapes = [list(reversed(walk)) for walk in self.walk_shapes]   #we want to check the points from latest to earliest
		bearish_walk_shapes = [self._walk_inverse(walk) for walk in bullish_walk_shapes]
		shape_points = sorted(shape_points,key=lambda sp:sp.index,reverse=True) #we want to ensure the points are from latest to earliest
		
		for bull_walk in bullish_walk_shapes:
			is_match, point_groups = self._walk_match(bull_walk,shape_points)
			if is_match:
				return 1.0
		
		for bear_walk in bearish_walk_shapes:
			is_match, point_groups = self._walk_match(bear_walk,shape_points)
			if is_match:
				return -1.0
		
		return 0
		
	def draw_snapshot(self,candle_stream,snapshot_index):
		base_view = super().draw_snapshot(candle_stream,snapshot_index) #gets the support/resistance lines - do we really want these though? 
		
		coords = self._find_shape_points(candle_stream,snapshot_index)
		if coords:
			base_view.draw('patterns neutral points',[chv.Point(coord.index, coord.value) for coord in coords]) #mapping needed?
		
		return base_view


class HeadAndShoulders(ShapePattern):
	
	walk_shapes = [[0,2,0,3,0,1,0]]  #or [0 1,0,2,0,1,0]

class TeacupHandle(ShapePattern):
	pass




import numpy as np
import datetime

from enum import Enum
from collections import namedtuple

import charting.candle_stick_functions as csf
from charting.candle_stick_pattern import CandleStickPattern
from charting.chart_pattern import *

#import charting.trend_line_functions as tlf
#from charting.trend_line_functions import TrendLine

ShapePoint = namedtuple('ShapePoint','x y')

#not sure how to do this yet - thinking get the levels and then number them then see if the price action hits them in the correct order (or similar) 
class ShapePattern(SupportAndResistance):
	
	level_smudge = 5 #if points are within this distance then treat them as one
	level_gap_multiplier = 1.2 #push levels more apart 
	shape_point_gap_multiplier = 0.5
	
	#level_pattern  = [2,0,1,0,2]#example
	def fit_coords(self,candle_stream_index,candle_stream):
		#get some levels from the support and resistance pattern
		#trace back through each level and note down points that are very close to it 
		#group x values together that are consecutive and use the middle as the shape point 
		#return shape points for shape testing
		extreme_points  = list(reversed(self._get_extremes(candle_stream_index - self.pattern_start_index)))
		start_level = csf.median(candles[max(candle_stream_index-self.pattern_start_index,0)])
		
		max_gap = self._rolling_range_mean[candle_stream_index]
		level_gap = self.level_gap_multiplier * max_gap
		levels = self._generate_levels(extreme_points,start_level,level_gap)
		
		if not levels:
			return [], MAX_ERROR_VALUE
		
		shape_point_gap = self.shape_point_gap_multiplier * max_gap
		
		unclustered_shape_points = [] 
		for level in levels:
			close_points = _close_points_to_level(self,level,points,shape_point_gap)
			for close_point in close_points: #fix the level values 
				unclustered_shape_points.append(Extremity(close_point.type,level,close_point.index))
		
		return unclustered_shape_points
		
	
	def _determine(self,candle_stream_index,candle_stream):
		raise NotImplementedError('This method must be overridden')


class TopAndBottom(ShapePattern):
	
	def _determine(self,candle_stream_index,candle_stream):
		shape_points, error = self.fit_shape_points(self,candle_stream,candle_stream_index)
		
	
	def draw_snapshot(self,candle_stream,snapshot_index):
		base_view = super().draw_snapshot(candle_stream,snapshot_index) #gets the support/resistance lines - do we really want these though? 
		
		return base_view

class HeadAndShoulders(ShapePattern):
	pass

class TeacupHandle(ShapePattern):
	pass


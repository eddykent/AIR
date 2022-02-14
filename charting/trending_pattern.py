##more advanced patterns that use extreme points etc. Put into separate file because chart_patterns.py is a bit big 
##some patterns inherit from ChartPattern and others from SupportAndResistance, depending on if levels or trendlines are used

import numpy as np
import datetime

from enum import Enum
from collections import namedtuple

import charting.candle_stick_functions as csf
from charting.candle_stick_pattern import CandleStickPattern
from charting.chart_pattern import *
import charting.trend_line_functions as tlf
from charting.trend_line_functions import TrendLine


import pdb

#Extremity = namedtuple('Extremity','type value index') ##from ChartPattern

#this class isn't really meant to be used as a trading pattern - it just has some foundation functions 
#for the next set of chart patterns. 
#However, running this produces the best fit trendline that starts from (candle_stream_index - memory_window)
class TrendingPattern(ChartPattern):
	
	_ensure_trend_points = 2
	
	pattern_start_index = 4
	memory_window = 100
	buffer_gap = 0.25 #between (0,1) multply gap by this to get points close to the line 
	
	fitness_keys = ['length','breakout_size','hits','variance','gradient','convergence','x_iou']
	fitness_parameters = {'length':1.0, 'breakout_size':1.0, 'hits':1.0, 'variance':1.0, 'gradient':1.0, 'convergence':1.0, 'x_iou':1.0}
	
	line_error_keys = ['error_term','length','n_points']
	line_error_parameters = {'error_term':0.9,'length':1.0,'n_points':1.1}
	
	#from the start to the end point, get a fitness rating of how well a bunch of points touch this line. 
	#bear in mind this is NOT a correlation - it does not take into account points far away
	def _line_error(self,points,gap):	#OVERRIDE IF YOU WANT TO CHANGE IT 
		
		N = len(points)
		if N <= 2:
			return MAX_ERROR_VALUE #big error for not enough points 		
		
		sp = points[0]
		ep = points[-1]
		
		perfect_line = TrendLine(sp.index, sp.value, ep.index, ep.value, 0)
		parametric_values = tlf.parametric(perfect_line)	
		
		total_error = 0
		n = 0
				
		for p in points:
			error_value = abs(p.value - parametric_values[p.index])
			if error_value < gap * self.buffer_gap:
				total_error += (error_value * error_value)
				n += 1
				
		if n < self._ensure_trend_points:
			return MAX_ERROR_VALUE #big error for lack of points that lie on this line!
		
		if n == 0:
			return MAX_ERROR_VALUE #for the 0 case
		
		the_error = (total_error / n)
		return the_error
	
	def _n_close_points(self,points,gap):
		N = len(points)
		if N < 2:
			return 1
		
		sp = points[0]
		ep = points[-1]
		
		perfect_line = TrendLine(sp.index, sp.value, ep.index, ep.value, 0)
		parametric_values = tlf.parametric(perfect_line)	
		
		n = 0
				
		for p in points:
			error_value = abs(p.value - parametric_values[p.index])
			if error_value < (gap * self.buffer_gap):
				n += 1
		return n
	
	def _get_best_end_point(self,points,gap):
		
		N = len(points) 
		if N < 2:
			return 0,MAX_ERROR_VALUE
		
		line_lengths = [tlf.length(TrendLine(points[0].index,points[0].value,points[i].index,points[i].value,0)) for i in range(N)]
		close_points = [self._n_close_points(points[0:i+1],gap) for i in range(N)]
		
		max_line_length = max(line_lengths)
		line_length_terms = [1.0 - (ll/max_line_length) for ll in line_lengths]   #longer => better . Since we are minimising then use 1.0 - length ratio to get highest length
		max_close_points = max(close_points)
		close_point_terms = [1.0 - (cps/max_close_points) for cps in close_points]
		
		#n_point_terms = [1.0 - (i/N) for i in range(N)]    #more points => better  NUMBER OF CLOSE POINTS NOT ALL POINTS! 
		error_values = [self._line_error(points[0:i+1],gap) for i in range(0,N)] #i+1 since slice highs are exclusive
		error_values_without_wrongs = [ev if ev != MAX_ERROR_VALUE else -MAX_ERROR_VALUE for ev in error_values] #turn MAX_ERROR_VALUE into -1s so call to max() works
		
		max_error = max(error_values_without_wrongs)
		if max_error == -MAX_ERROR_VALUE: #all values didnt work 
			return 0, MAX_ERROR_VALUE # we have not got any error terms! So this line couldn't draw
		
		error_terms = [(e/max_error) if max_error > 0 else 0 for e in error_values_without_wrongs]
		
		choice_calculation = []
		ratios = {k:0 for k in self.line_error_keys}
		
		for (ll,nt,et) in zip(line_length_terms,close_point_terms,error_terms):
			ratios['length'] = ll 
			ratios['n_points'] = nt
			ratios['error_term'] = et
			
			assert ll <= 1.0 , 'line length term is larger than 1'
			assert et <= 1.0 , 'error term is larger than 1' #
			assert nt <= 1.0 , 'n pointsterm is larger than 1'
			
			choice_value = MAX_ERROR_VALUE
			if et >= 0: #when the error term is negative then something went wrong when attempting to find the line!
				choice_value = sum([ratios.get(k,1.0)*self.line_error_parameters.get(k,1.0) for k in self.line_error_keys])
						
			choice_calculation.append(choice_value)
		
		assert len(choice_calculation) == N, 'choice calculation array length has changed'
		
		line_end_at = np.argmin(choice_calculation)
		
		#line_end_at = np.argmin(error_values)
		error = choice_calculation[line_end_at]
	
		return line_end_at, error
	
	
	def _fit_minimum_trend_line(self,points,max_gap):
		end_point,error = self._get_best_end_point(points,max_gap)
		the_line = None
		if error != MAX_ERROR_VALUE:
			line_start = points[0]
			line_end = points[end_point]
			the_line = TrendLine(line_start.index, line_start.value, line_end.index,line_end.value,error)	
		return the_line #, error
	
	def __get_closing_points(self,candle_stream_index,candle_stream):
		indexs = range(max(0,candle_stream_index -self.memory_window),candle_stream_index)
		close_price_points = [c[csf.close] for c in candle_stream[max(0,candle_stream_index -self.memory_window):candle_stream_index]]
		closing_points = [Extremity(ExtremityType.VOID,cp,ind) for (cp,ind) in zip(close_price_points,indexs)]
		return closing_points
	
	def _determine(self,candle_stream_index,candle_stream):
		max_gap = self._rolling_range_mean[candle_stream_index] * 10
		
		closing_points = self.__get_closing_points(candle_stream_index,candle_stream)
		
		line = self._fit_minimum_trend_line(closing_points,max_gap)
		return line.error if line else MAX_ERROR_VALUE
		
	def draw_snapshot(self,snapshot_index,candles):
		base_view = super(self.__class__,self).draw_snapshot(snapshot_index,candles)
		
		closing_points = self.__get_closing_points(snapshot_index,candles)
		max_gap = self._rolling_range_mean[snapshot_index]
		line, error = self._fit_minimum_trend_line(closing_points,max_gap)
		if error >= MAX_ERROR_VALUE:
			return [None,None],[None,None]
		return [line.x1,line.x2],[line.y1,line.y2] 
	


#relaxed triangle breakout - the highs and lows are all included, not forced to use higher highs and lower lows
class TriangularBasedPattern(TrendingPattern):
	
	#override TriangleBreakout._highers_lowers
	def _highers_lowers(self,candle_stream_index):
		extremes  = list(reversed(self._get_extremes(candle_stream_index - self.pattern_start_index))) #working backwards from current index 
		lows = [ep for ep in extremes if ep.type == ExtremityType.MINIMUM]
		highs  = [ep for ep in extremes if ep.type == ExtremityType.MAXIMUM]
		return highs,lows 
	
	def _approx_hits(self,trendline,candles,gap):
		para = tlf.parametric(trendline)
		time_range = tlf.get_x_range(trendline)
		return [i for i in time_range if csf.range_distance(candles[i],para[i]) < gap]

	
	def _generate_trendlines(self,highers,lowers,gap,index):	
		upper_line = self._fit_minimum_trend_line(highers,gap)
		lower_line = self._fit_minimum_trend_line(lowers,gap)
		return upper_line, lower_line
	
	
	def _convergent(self,upper_line,lower_line):
		return tlf.convergent(upper_line,lower_line) 
	
	
	#breakout calculations
	def _gradient_for_breakout(self,trend1,trend2):
		return 0 # 0 means it will always pass (not positive or negative)
	
	
	#use to determine if the breakout is moving enough - wedges might have a high gradient
	def _trend_bounds_for_breakout(self,candle):
		trend_low = MAX_ERROR_VALUE #csf.body_bottom(candle)
		trend_high = -1 #csf.body_top(candle)
		return trend_high, trend_low
	
	
	def _breakout_fitness_signed(self,trend1,trend2,candle_stream,candle_stream_index):
		
		#the trend candle is the one where the trends start at 
		trend_candle = candle_stream[min(0,candle_stream_index-self.pattern_start_index)]
		latest_candle = candle_stream[candle_stream_index]
		
		trend1_value = tlf.projection(trend1,candle_stream_index)
		trend2_value = tlf.projection(trend2,candle_stream_index)
		
		body_bottom = csf.body_bottom(latest_candle)
		body_top = csf.body_bottom(latest_candle)		
		
		grad = self._gradient_for_breakout(trend1,trend2)
		
		#use the trend candle to determine breakout size, not the trendlines
		trend_high, trend_low = self._trend_bounds_for_breakout(trend_candle)
		
		if body_top < min(trend1_value,trend2_value) and body_top < trend_low and grad >= 0: #wedge is upward
			return body_top - min(trend1_value,trend2_value) #return negative - this is bearish
		elif body_bottom > max(trend1_value,trend2_value) and body_bottom > trend_high and grad <= 0:#wedge is downward
			return body_bottom - max(trend1_value,trend2_value) #return positive - this is bullish
		return 0
	
	
	#fitness calculations
	def _gradient_fitness(self,trend1,trend2):
		#return 1.0
		#return 1.0 - abs(tlf.combined_gradient(trend1,trend2)) #more level the better?
		return tlf.combined_gradient(trend1,trend2)
	
	
	def _convergence_fitness(self,trend1,trend2,candle_stream_index):
		return tlf.convergence_speed(trend1,trend2)
		
	
	#higher the fitness the better! 
	def _pattern_fitness(self,trend1,trend2,candle_stream_index,candle_stream,gap,parameter_settings={}):
		
		## speed of convergence? 
		## gradient (wedge only!) 
		## variance (normalise?) (div by mem window?)
		## trendline length 
		default = 0
		
		candles = candle_stream[max(0,candle_stream_index-self.memory_window):candle_stream_index]
		longest_line_length = tlf.length(TrendLine(0,csf.median(candles[0]),len(candles)-1,csf.median(candles[-1]),0))
		length = min(tlf.length(trend1),tlf.length(trend2))
		hits1 = self._approx_hits(trend1,candle_stream,gap)
		hits2 = self._approx_hits(trend2,candle_stream,gap)
		variance = np.var(hits1) + np.var(hits2)
		breakout = self._breakout_fitness_signed(trend1,trend2,candle_stream,candle_stream_index)
		
		#basic bounds checks? eg breakout abs is 0?
		if abs(breakout) == 0:
			return default
		
		if len(hits1) < self._ensure_trend_points:
			return default
		
		if len(hits2) < self._ensure_trend_points:
			return default
		
		ratios = {}
		
		ratios['length'] = length / longest_line_length
		ratios['breakout_size'] = abs(breakout)
		ratios['hits'] = (len(hits1) + len(hits2)) / self.memory_window
		ratios['variance'] = variance / self.memory_window
		ratios['gradient'] = self._gradient_fitness(trend1,trend2)
		ratios['convergence'] = self._convergence_fitness(trend1,trend2,candle_stream_index)
		ratios['x_iou'] = tlf.x_iou(trend1,trend2)
		#for ratio in ratios:
		#	assert type(ratios[ratio]) in [float,int,numpy.float64], f'the ratio {ratio} is {type(ratios[ratio])}'
		
		#calc fitness with simply a linear combination of the ratios with tuned parameter settings 
		fitness_score = sum([ratios.get(k,0)*parameter_settings.get(k, self.fitness_parameters.get(k,0)) for k in self.fitness_keys])
		
		#normalise the fitness between 0 and 1 so it can be compared to other chart patterns 
		denom = sum([parameter_settings.get(k, self.fitness_parameters.get(k,0)) for k in self.fitness_keys])
		
		assert denom > 0 , 'fitness parameter settings are wrong. they need to all be positive with at least one value'
		
		
		
		fitness = fitness_score / denom 
		
		if np.isnan(fitness):
			print('pattern fitness is NaN')
			pdb.set_trace()
		
		return fitness
		
	
	def _determine(self,candle_stream_index,candle_stream):
		
		highers, lowers = self._highers_lowers(candle_stream_index)
		max_gap = self._rolling_range_mean[candle_stream_index] 
		
		#if candle_stream_index == ???
		#	pdb.set_trace()
		upper_line, lower_line = self._generate_trendlines(highers,lowers,max_gap,candle_stream_index)
		
		default = 0 #MAX_ERROR_VALUE
		
		
		if not upper_line:
			return default
			
		if not lower_line: 
			return default

		if max(upper_line.error,lower_line.error) >= MAX_ERROR_VALUE:
			return default
		
		if not tlf.overlap_x(upper_line,lower_line):
			return default
			
		if not self._convergent(upper_line,lower_line):
			return default
		
		
		breakout = self._breakout_fitness_signed(upper_line,lower_line,candle_stream,candle_stream_index)
		sign = breakout / abs(breakout) if breakout != 0 else 0
		pattern_fitness = sign*self._pattern_fitness(upper_line,lower_line,candle_stream_index,candle_stream,max_gap)
		
		return pattern_fitness
		
	
	def draw_snapshot(self,candle_stream_index,candles):
		#pdb.set_trace()
		highers, lowers = self._highers_lowers(candle_stream_index)
		max_gap = self._rolling_range_mean[candle_stream_index]
		extreme_points = self._get_extremes(candle_stream_index - self.pattern_start_index)
		upper_line, lower_line = self._generate_trendlines(highers,lowers,max_gap,candle_stream_index)
		
		xs = []
		ys = []
		
		if lower_line and lower_line.error != MAX_ERROR_VALUE:
			xs += [lower_line.x1,lower_line.x2]
			ys += [lower_line.y1,lower_line.y2]
			
		xs += [None]
		ys += [None]
		
		if upper_line and upper_line.error != MAX_ERROR_VALUE:
			xs += [upper_line.x1,upper_line.x2]
			ys += [upper_line.y1,upper_line.y2]
		
		return xs,ys



##get higher highs and lower lows from non-grouped levels from a previous chart window. test for correlation. then test for breakouts 
##this is SYMETRIC only 
class TriangleBreakout(TriangularBasedPattern): #this is close to working! 	

	#overides ShapeBasedPattern - get higher highs and lower lows
	def _highers_lowers(self,candle_stream_index):
		extremes  = list(reversed(self._get_extremes(candle_stream_index - self.pattern_start_index)))  ##we want to work backwards from our snapshot location 
		lows = [ep for ep in extremes if ep.type == ExtremityType.MINIMUM]
		highs  = [ep for ep in extremes if ep.type == ExtremityType.MAXIMUM]
		lower_lows = []
		higher_highs = []
		lowest_low = MAX_ERROR_VALUE
		highest_high = -1
		for lp in lows:
			if lp.value < lowest_low:
				lowest_low = lp.value
				lower_lows.append(lp)
		for hp in highs:
			if hp.value > highest_high:
				highest_high = hp.value
				higher_highs.append(hp)	
				
		return higher_highs,lower_lows
	

class FallingTriangleBreakout(TriangularBasedPattern,SupportAndResistance):
	
	#overides ShapeBasedPattern - get highs and lower lows
	def _highers_lowers(self,candle_stream_index):
		extremes  = list(reversed(self._get_extremes(candle_stream_index - self.pattern_start_index)))  ##we want to work backwards from our snapshot location 
		highs  = [ep for ep in extremes if ep.type == ExtremityType.MAXIMUM]
		
		higher_highs = []
		highest_high = -1
		
		for hp in highs:
			if hp.value > highest_high:
				highest_high = hp.value
				higher_highs.append(hp)	
				
		return higher_highs,extremes
	
	def _generate_trendlines(self,highers,lowers,gap,index):	
		upper_line = self._fit_minimum_trend_line(highers,gap)
		lower_line = None
		extremes = lowers
		
		if extremes:
			start_level = extremes[0].value
			below_points = [p for p in extremes if p.value < start_level + gap]
			levels = self._generate_levels(below_points,start_level,gap)
			level_errors = sorted(self._level_errors(levels,below_points,gap),key=lambda l:l[1])
			if level_errors:
				level, error = level_errors[0]
				hits = self._close_points_to_level(level,below_points,gap) #consider using all extremes? 
				if len(hits) > 1:
					minx = min(p.index for p in hits)
					maxx = max(p.index for p in hits)
					lower_line = TrendLine(maxx,level,minx,level,error)
				
		return upper_line, lower_line
	
	def _gradient_for_breakout(self,trend1,trend2):
		return 1  #we only want to try and find bearish moves. We search for bearish when the trend is increasing in a wedge, so lets pretend it is 
	
	


class RisingTriangleBreakout(TriangularBasedPattern,SupportAndResistance):
	
	#overides ShapeBasedPattern - get higher highs and lower lows
	def _highers_lowers(self,candle_stream_index):
		extremes  = list(reversed(self._get_extremes(candle_stream_index - self.pattern_start_index)))  ##we want to work backwards from our snapshot location 
		lows = [ep for ep in extremes if ep.type == ExtremityType.MINIMUM]
		
		lower_lows = []
		lowest_low = MAX_ERROR_VALUE
		
		for lp in lows:
			if lp.value < lowest_low:
				lowest_low = lp.value
				lower_lows.append(lp)
				
		return extremes,lower_lows
	
	def _generate_trendlines(self,highers,lowers,gap,index):	
		upper_line = None
		extremes = highers
		
		if extremes:
			start_level = extremes[0].value
			above_points = [p for p in extremes if p.value > start_level + gap]
			levels = self._generate_levels(above_points,start_level,gap)
			level_errors = sorted(self._level_errors(levels,above_points,gap),key=lambda l:l[1])
			if level_errors:
				level, error = level_errors[0]
				hits = self._close_points_to_level(level,above_points,gap) #consider using all extremes? 
				if len(hits) > 1:
					minx = min(p.index for p in hits)
					maxx = max(p.index for p in hits)
					upper_line = TrendLine(maxx,level,minx,level,error)
	
		lower_line = self._fit_minimum_trend_line(lowers,gap)
		
		return upper_line, lower_line
		
		
	def _gradient_for_breakout(self,trend1,trend2):
		return -1  #we only want to try and find bullish moves. We search for bullish when the trend is decreasing so lets pretend it is 
	

#Supported lines are ones that must have all their points on one side of them (within an error boundary) 
#Supported lines are better suited for some patterns like wedges. 
#This base class might be able to be purged since we always want supported lines and thus the implementation should be further up 
#add buffer value for the points above and below the line
class SupportedLinePattern(TriangularBasedPattern):
	
	
	##needs its own error functions to prevent points being on the wrong side of trendlines 
	#from the start to the end point, get a fitness rating of how well a bunch of points touch this line. 
	#bear in mind this is NOT a correlation - it does not take into account points far away
	def _line_error(self,points,gap,extreme_type):	#OVERRIDE IF YOU WANT TO CHANGE IT 
		
		N = len(points)
		if N <= 2:
			return MAX_ERROR_VALUE #big error for not enough points 		
		
		sp = points[0]
		ep = points[-1]
		
		perfect_line = TrendLine(sp.index, sp.value, ep.index, ep.value, 0)
		parametric_values = tlf.parametric(perfect_line)	
		
		
		total_error = 0
		n = 0
		
		buffer_gap = gap * self.buffer_gap

		if extreme_type == ExtremityType.MAXIMUM:
			if any([p.value - buffer_gap > parametric_values[p.index] for p in points]):
				return MAX_ERROR_VALUE
		
		if extreme_type == ExtremityType.MINIMUM:
			if any([p.value  + buffer_gap < parametric_values[p.index] for p in points]):
				return MAX_ERROR_VALUE
				
		for p in points:
			error_value = abs(p.value - parametric_values[p.index])
			if error_value < (gap * self.buffer_gap):
				total_error += error_value**2
				n += 1
		
		if n == 0:
			return MAX_ERROR_VALUE #for the 0 case
		
		the_error = (total_error / n)
		return the_error
	

	def _get_best_end_point(self,points,gap,extreme_type):
		
		N = len(points) 
		if N < 2:
			return 0,MAX_ERROR_VALUE
		
		line_lengths = [tlf.length(TrendLine(points[0].index,points[0].value,points[i].index,points[i].value,0)) for i in range(N)]
		close_points = [self._n_close_points(points[0:i+1],gap) for i in range(N)]
		
		max_line_length = max(line_lengths)
		line_length_terms = [1.0 - (ll/max_line_length) for ll in line_lengths]   #longer => better . Since we are minimising then use 1.0 - length ratio to get highest length
		max_close_points = max(close_points)
		close_point_terms = [1.0 - (cps/max_close_points) for cps in close_points]
		
		#n_point_terms = [1.0 - (i/N) for i in range(N)]    #more points => better  NUMBER OF CLOSE POINTS NOT ALL POINTS! 
		error_values = [self._line_error(points[0:i+1],gap,extreme_type) for i in range(0,N)] 
		error_values_without_wrongs = [ev if ev != MAX_ERROR_VALUE else -MAX_ERROR_VALUE for ev in error_values] #turn MAX_ERROR_VALUE into -1s so call to max() works
		
		max_error = max(error_values_without_wrongs)
		if max_error == -MAX_ERROR_VALUE: #all values didnt work 
			return 0, MAX_ERROR_VALUE # we have not got any error terms! So this line couldn't draw
		
		error_terms = [(e/max_error) if max_error > 0 else 0 for e in error_values_without_wrongs]
		
		choice_calculation = []
		ratios = {k:0 for k in self.line_error_keys}
		
		for (ll,nt,et) in zip(line_length_terms,close_point_terms,error_terms):
			ratios['length'] = ll 
			ratios['n_points'] = nt
			ratios['error_term'] = et
			
			assert ll <= 1.0 , 'line length term is larger than 1'
			assert et <= 1.0 , 'error term is larger than 1' 
			assert nt <= 1.0 , 'n pointsterm is larger than 1'
			
			choice_value = MAX_ERROR_VALUE
			if et >= 0: #when the error term is negative then something went wrong when attempting to find the line!
				choice_value = sum([ratios.get(k,1.0)*self.line_error_parameters.get(k,1.0) for k in self.line_error_keys])
						
			choice_calculation.append(choice_value)
		
		assert len(choice_calculation) == N, 'choice calculation array length has changed'
		
		line_end_at = np.argmin(choice_calculation)
		error = choice_calculation[line_end_at]
	
		return line_end_at, error	
	

	def _fit_minimum_trend_line(self,points,max_gap,extreme_type):
		
		end_point, error = self._get_best_end_point(points,max_gap,extreme_type)
		the_line = None
		if error != MAX_ERROR_VALUE:
			line_start = points[0]
			line_end = points[end_point]
			the_line = TrendLine(line_start.index, line_start.value, line_end.index,line_end.value,error)
		
		return the_line #, error
	
	#this was the main function that needed to be overridden
	def _generate_trendlines(self,highers,lowers,gap,index):	
		upper_line = self._fit_minimum_trend_line(highers,gap,ExtremityType.MAXIMUM)
		lower_line = self._fit_minimum_trend_line(lowers,gap,ExtremityType.MINIMUM)
		return upper_line, lower_line

	
class WedgeBreakout(SupportedLinePattern): ##run more and find bugs 
		
	
	#override
	def _gradient_fitness(self,trend1,trend2): #maximise steepness?
		return abs(tlf.combined_gradient(trend1,trend2)) 
	
	#override
	def _convergence_fitness(self,trend1,trend2,candle_stream_index):
		return tlf.convergence_speed(trend1,trend2) 
	
	def _trend_bounds_for_breakout(self,candle):
		trendlow = csf.body_bottom(candle)
		trendhigh = csf.body_top(candle)
		return trendhigh, trendlow
	
	#override
	def _gradient_for_breakout(self,trend1,trend2):
		return tlf.combined_gradient(trend1,trend2) #we care about gradient in wedges 
	
	def _convergent(self,trend1,trend2):
		return tlf.convergent(trend1,trend2)

	def draw_snapshot(self,candle_stream_index,candles):
		#pdb.set_trace()
		highers, lowers = self._highers_lowers(candle_stream_index)
		max_gap = self._rolling_range_mean[candle_stream_index]
		extreme_points = self._get_extremes(candle_stream_index - self.pattern_start_index)
		upper_line, lower_line = self._generate_trendlines(highers,lowers,max_gap,candle_stream_index)
		
		xs = []
		ys = []
		
		if lower_line and lower_line.error != MAX_ERROR_VALUE:
			xs += [lower_line.x1,lower_line.x2]
			ys += [lower_line.y1,lower_line.y2]
			
		xs += [None]
		ys += [None]
		
		if upper_line and upper_line.error != MAX_ERROR_VALUE:
			xs += [upper_line.x1,upper_line.x2]
			ys += [upper_line.y1,upper_line.y2]
		
		return xs,ys


#a channel is optimised differently - it uses lines which are approximately paralell to eachother. 
class ApproximateChannelBreakout(SupportedLinePattern): 
	
	def _gradient_fitness(self,trend1,trend2): #minimise steepness?
		return 1.0 - abs(tlf.combined_gradient(trend1,trend2)) 
	
	#their gradient needs to be almost the same
	def _convergence_fitness(self,trend1,trend2,candle_stream_index):
		return 1.0 - tlf.convergence_speed(trend1,trend2) # we want the gradients to be level with eachother as much as possible to define a channel
	
	#they don't need to converge
	def _convergent(self,trend1,trend2):
		m1 = tlf.gradient(trend1)
		m2 = tlf.gradient(trend2) 
		return abs(m1 - m2) < 0.00001
	

#a parallel channel is actually forced to be parallel and to be at the same x1 x2 - perhaps we can remove the same x1 x2 constraint?
class ParallelChannelBreakout(SupportedLinePattern): 
 	
	#memory_window = 100
	
	#get trendlines, then get trendline (lower/upper) with least error. 
	#take the parametric of the smallest error. take off from the other (upper/lower) values to make flat
	#determine height and use to get parallel trendline above/below. Calc the error 
	
	#override
	def _gradient_for_breakout(self,trend1,trend2):
		gradient = tlf.gradient(trend1) if trend1.error < trend2.error else tlf.gradient(trend2)
		sign = gradient / abs(gradient) if gradient != 0 else 0
		return 0#sign * -1 #look for opposite direction trend 


		
	#they don't need to converge
	def _convergent(self,trend1,trend2):
		return True
	
	#their gradient needs to be almost the same
	def _convergence_fitness(self,trend1,trend2,candle_stream_index):
		return 0 #don't take any notice of convergence
	
	def _generate_trendlines(self,highers,lowers,gap,index):
	
		#if index == 863:
		#	pdb.set_trace()
		upper_line = self._fit_minimum_trend_line(highers,gap,ExtremityType.MAXIMUM)
		lower_line = self._fit_minimum_trend_line(lowers,gap,ExtremityType.MINIMUM)
		
		#delete the worse line
		if lower_line:
			if not upper_line or upper_line.error > lower_line.error:
				upper_line = None
		
		if upper_line:
			if not lower_line or lower_line.error > upper_line.error:
				lower_line = None
		
		#use the line to create the other line
		if upper_line:
			para = tlf.parametric(upper_line)
			matching_lower_points = [p for p in lowers if p.index >= tlf.lower_x(upper_line) and p.index <= tlf.higher_x(upper_line)]
			if matching_lower_points:
				line_dist = max(abs(para[p.index] - p.value) for p in matching_lower_points)# - (self.buffer_gap * gap)
				
				new_points = [Extremity(ExtremityType.MINIMUM,upper_line.y1-line_dist,upper_line.x1)] + \
					matching_lower_points + \
					[Extremity(ExtremityType.MINIMUM,upper_line.y2-line_dist,upper_line.x2)]
					
				error = self._line_error(new_points,gap,ExtremityType.MINIMUM)
				lower_line = TrendLine(new_points[0].index,new_points[0].value,new_points[-1].index,new_points[-1].value,error)
			
		elif lower_line:
			para = tlf.parametric(lower_line)
			matching_upper_points = [p for p in highers if p.index >= tlf.lower_x(lower_line) and p.index <= tlf.higher_x(lower_line)]
			if matching_upper_points: 
				line_dist = max(abs(para[p.index] - p.value) for p in matching_upper_points)# - (self.buffer_gap * gap)
				
				new_points = [Extremity(ExtremityType.MAXIMUM,lower_line.y1+line_dist,lower_line.x1)] + \
					matching_upper_points + \
					[Extremity(ExtremityType.MAXIMUM,lower_line.y2+line_dist,lower_line.x2)]
					
				error = self._line_error(new_points,gap,ExtremityType.MAXIMUM)
				upper_line = TrendLine(new_points[0].index,new_points[0].value,new_points[-1].index,new_points[-1].value,error)
		
		return upper_line, lower_line





















import numpy as np
import namedtuple

import pdb

import charting.candle_stick_functions as csf
from charting.chart_pattern import *
import charting.chart_viewer as chv


Matching = namedtuple('Matching','haystack_index candle_index error_value')
###CHANGE TO USE NUMPY FOR SPEED! 
##make a needle (use the current memory window and the close price)
##make a haystack (use all the chart candles close prices) 
##make a distance function (L2 norm/mse should be fine) 
##get all error values (sliding windows  - think of optimisations)
##select lowest error value windows from haystack 
##use lowest error windows to get price action (close prices, highest highs, lowest lows)
##draw nice funnels on a chart to display the results 
class MatchPattern(ChartPattern):
	
	memory_window = 20 #standard from ChartPattern
	haystack = [] #list of other candle streams (including this one) 
	#can be handled from the test/point of usage
	projection_length = 6 #number of candles after the haystack index to use as guide for the trad
	n_projections = 10 #select top 10 best candles from the haystack for use in projecting price
		
	def __init __(self):
		pass
	
	#from outside this class, pass all the other charts to this for searching 
	def set_haystack(self,candle_haystack):
		self.haystack = candle_haystack
	
	def create_needle(self,candles):
		closes = [candle[csf.close] for candle in candles]
		highest = max(closes)
		lowest = min(closes)
		return [(c - lowest) / (highest - lowest) for c in closes]
		
	def calc_errors(self,needle1,needle2):
		return sum((n1 - n2)*(n1 - n2) for (n1,n2) in zip(needle1,needle2)) / len(needle1) 
	
	def haystack_matching_errors(self,needle):
		error_values = []
		for haystack_index,candle_stream in enumerate(self.haystack):
			for candle_index in range(len(candle_stream) - self.memory_window - self.projection_length):
				candles = candle_stream[candle_index:candle_index+self.memory_window]
				other_needle = self.create_needle(candles)	
				the_error = self.calc_errors(needle,other_needle)
				error_values.append(Matching(haystack_index,candle_index,the_error))
		return error_values 
		
	#@override 
	def _determine(self,candle_stream,candle_stream_index):
		candles = candle_stream[candle_stream_index-self.memory_window:candle_stream_index]
		needle = self.create_needle(candles)
		haystack_errors = self.haystack_matching_errors(needle)
		haystack_errors = sorted(haystack_errors,key=lambda m:m.error_value)
		continuation_candles = [haystack[m.haystack_index][m.candle_index:m.candle_index+self.memory_window+self.projection_length] for m in haystack_errors[:self.n_projections]]
		#top_paths = []
		#mean path
		#highest/lowest values 
		#plot!
		
	












































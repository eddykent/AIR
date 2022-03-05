import numpy as np
from collections import namedtuple

import pdb

import charting.candle_stick_functions as csf
from charting.chart_pattern import *
import charting.chart_viewer as chv


#Matching = namedtuple('Matching','haystack_index candle_index error_value')
###CHANGE TO USE NUMPY FOR SPEED! 
##make a needle (use the current memory window and the close price)
##make a haystack (use all the chart candles close prices) 
##make a distance function (L2 norm/mse should be fine) 
##get all error values (sliding windows  - think of optimisations)
##select lowest error value windows from haystack 
##use lowest error windows to get price action (close prices, highest highs, lowest lows)
##draw nice funnels on a chart to display the results 
class MatchPattern(ChartPattern):
	
	memory_window = 20 #standard from ChartPattern - used fof needle size & comparing in haystack
	haystack_window = 400 #length back to look in haystack
	haystack = np.array([]) #list of other candle streams (including this one) 
	#can be handled from the test/point of usage
	projection_length = 8 #number of candles after the haystack index to use as guide for the trad
	n_projections = 20 #select top x best candles from the haystack for use in projecting price
	
	endings_to_check = 5
	
	line_channel = csf.close #csf.open? 
	
	best_std_multiplier = 2.1
	other_std_multiplier = 0.5
	
	def __init__(self):
		pass
	
	#from outside this class, pass all the other charts to this for searching 
	def set_haystack(self,candle_haystack):
		haystack = np.array(candle_haystack)[:,:,:4]#get all candles but chop all datetime off 
		self.haystack = np.float64(haystack)
	
	def normalise(self,hay):
		mins = np.expand_dims(np.min(hay[:,:self.memory_window],axis=1),axis=1) #NOTE - hay  > window size since it has projection 
		maxs = np.expand_dims(np.max(hay[:,:self.memory_window],axis=1),axis=1)
		return (hay - mins) / (maxs - mins) , mins, maxs
	
	def rescale(self,normed_shapes,new_min,new_max):
		new_shapes = (normed_shapes * (new_max - new_min)) + new_min
		return new_shapes
		
	def calc_distance(self,needle,hay):
		return (np.square(needle - hay[:,:self.memory_window])).mean(axis=1)
	
	def haystack_matchings(self,normed_needle,candle_stream_index):
		#error_values = []
		#for haystack_index,candle_stream in enumerate(self.haystack):
		#	for candle_index in range(len(candle_stream) - self.memory_window - self.projection_length):
		#		candles = candle_stream[candle_index:candle_index+self.memory_window]
		#		other_needle = self.create_needle(candles)	
		#		the_error = self.calc_errors(needle,other_needle)
		#		error_values.append(Matching(haystack_index,candle_index,the_error))
		#return error_values 
		
		nhays = self.haystack.shape[0]
		hay_end = candle_stream_index - self.memory_window - self.projection_length
		hay_start = max(hay_end - self.haystack_window,0)
		
		slideable_hay = self.haystack[:,hay_start:hay_end,self.line_channel]
		windowed_hay = np.lib.stride_tricks.sliding_window_view(slideable_hay,(nhays,self.memory_window+self.projection_length))
		
		y_dim = windowed_hay.shape[1] * windowed_hay.shape[2]
		x_dim = windowed_hay.shape[3]
		windowed_hay = windowed_hay.reshape((y_dim,x_dim))
		
		#this will also have some of its values at the end non-normed since they will be used later for fitness & drawing
		normed_hay,_,_ = self.normalise(windowed_hay)
		distances = self.calc_distance(normed_needle,normed_hay)
		
		return normed_hay,distances 
		
	
	def _get_closest_paths(self,candle_stream,candle_stream_index):
		
		candles = candle_stream[max(candle_stream_index-self.memory_window,0):candle_stream_index]
		
		needle = np.float64(np.array(candles)[:,self.line_channel])
		needle = np.expand_dims(needle,axis=0) #so we can apply it to some hay
		normed_needle, this_min, this_max = self.normalise(needle)
		
		normed_hay, distances = self.haystack_matchings(normed_needle,candle_stream_index)
		sorted_hay = sorted(zip(normed_hay,distances),key=lambda m:m[1])
		
		top_hay = sorted_hay[:self.n_projections]
		shapes = list(zip(*top_hay))[0]

		new_shapes = self.rescale(np.stack(shapes,axis=0),this_min,this_max)
		return new_shapes
	
	#@override
	def _determine(self,candle_stream_index,candle_stream):
		
		if candle_stream_index < self.haystack_window: #don't bother with detections smaller than the window of the haystack
			return 0
		
		new_shapes = self._get_closest_paths(candle_stream,candle_stream_index)
		
		#pdb.set_trace()
		standard_dev = np.std(new_shapes[-1,:])
		
		candles = candle_stream[max(candle_stream_index-self.memory_window,0):candle_stream_index]
		needle = np.float64(np.array(candles)[:,self.line_channel])
		needle = np.expand_dims(needle,axis=0) #so we can apply it to some hay
		_, _, this_max = self.normalise(needle)
		
		fitness = this_max / standard_dev #normalise std but do a 1 over score so bigger -> better!  
		
		#best path check
		endings = new_shapes[-1,:]
		
		mean_end = np.mean(endings) 
		last_close = candle_stream[candle_stream_index][self.line_channel]
		movement = standard_dev * self.best_std_multiplier #make highly significant for normal dist 
		
		#if we moved more than the sd then consider it a good choice
		direction = 1 if mean_end > last_close + movement else -1 if mean_end < last_close - movement else 0
		
		other_movement = standard_dev * self.other_std_multiplier
		
		best_ending_directions = [1 if some_end > last_close + other_movement else -1 if some_end < last_close - other_movement else 0 for some_end in endings[:self.endings_to_check]]
		best_ending_directions.append(direction)
		
		agreement = all(ed == 1 for ed in best_ending_directions) or all(ed == -1 for ed in best_ending_directions)
		
		return (fitness * direction).reshape((1))[0] if agreement else 0
		#top_paths = []
		#mean path
		#highest/lowest values 
		#plot!
		
	def draw_snapshot(self,candle_stream,snapshot_index):
		
		paths = self._get_closest_paths(candle_stream,snapshot_index)
		x_start = snapshot_index - self.memory_window
		x_axis = list(range(x_start,x_start+self.memory_window+self.projection_length)) #note - goes off the end of the plot (intentionally!)
		
		base_view = super().draw_snapshot(candle_stream,snapshot_index)
		#build a view of this chart pattern
		this_view = chv.ChartView()
		
		best_path = []
		for (x,y) in zip(x_axis,paths[0]):
			best_path.append(chv.Point(x,y))
		
		all_path = [] 
		for path in paths: 
			for (x,y) in zip(x_axis,path):
				all_path.append(chv.Point(x,y)) #s deliberately missed off since we are working with a single path with None points
			all_path.append(chv.Point(None,None))
		
		confuse_path = []
		
		for (x,y) in zip(x_axis,np.min(paths,axis=0)):
			confuse_path.append(chv.Point(x,y))
		confuse_path.append(chv.Point(None,None))
		for (x,y) in zip(x_axis,np.max(paths,axis=0)):
			confuse_path.append(chv.Point(x,y))
		
		this_view.draw('faint_traces neutral paths',all_path)
		this_view.draw('price_actions bearish paths',confuse_path)		
		this_view.draw('price_actions keyinfo paths',best_path)
		
		
		
		this_view += base_view 
		
		return this_view 










































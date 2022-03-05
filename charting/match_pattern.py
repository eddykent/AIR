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
	
	memory_window = 15 #standard from ChartPattern
	haystack = np.array([]) #list of other candle streams (including this one) 
	#can be handled from the test/point of usage
	projection_length = 6 #number of candles after the haystack index to use as guide for the trad
	n_projections = 10 #select top 10 best candles from the haystack for use in projecting price
	
	line_channel = csf.close #csf.open? 
	step = 3 #same some computation by checking every other one 
	
	def __init__(self):
		pass
	
	#from outside this class, pass all the other charts to this for searching 
	def set_haystack(self,candle_haystack):
		haystack = np.array(candle_haystack)[:,:,:4]#get all candles but chop all datetime off 
		self.haystack = np.float64(haystack)
	
	def normalise(self,candles):
		mins = np.expand_dims(np.min(candles,axis=1),axis=1)
		maxs = np.expand_dims(np.max(candles,axis=1),axis=1)
		return (candles - mins) / (maxs - mins) , mins, maxs
	
	def rescale(self,shapes,new_min,new_max):
		mins = np.expand_dims(np.min(shapes[:,:self.memory_window],axis=1),axis=1) #only take the scale from the memory window so the 
		maxs = np.expand_dims(np.max(shapes[:,:self.memory_window],axis=1),axis=1) #projection is preserved
		normed_shapes = (shapes - mins) / (maxs - mins)
		new_shapes = (normed_shapes * (new_max - new_min)) + new_min
		return new_shapes
		
	def calc_errors(self,needle,hay):
		return (np.square(needle - hay)).mean(axis=1)
	
	def haystack_matching_errors(self,needle):
		#error_values = []
		#for haystack_index,candle_stream in enumerate(self.haystack):
		#	for candle_index in range(len(candle_stream) - self.memory_window - self.projection_length):
		#		candles = candle_stream[candle_index:candle_index+self.memory_window]
		#		other_needle = self.create_needle(candles)	
		#		the_error = self.calc_errors(needle,other_needle)
		#		error_values.append(Matching(haystack_index,candle_index,the_error))
		#return error_values 
		error_values = []
		nhays = self.haystack.shape[0]
		for ci in range(0,self.haystack.shape[1] - self.memory_window - self.projection_length, self.step):
			hay = self.haystack[:,ci:ci+self.memory_window:,self.line_channel]
			hay,_,_ = self.normalise(hay)
			errors = self.calc_errors(needle,hay)
			cis = np.full((nhays,),ci)
			his = np.arange(0,nhays)
			error_values.append(np.stack([his,cis,errors],axis=1))
		return np.concatenate(error_values)
		
	
	def _get_closest_paths(self,candle_stream,candle_stream_index):
		
		candles = candle_stream[max(candle_stream_index-self.memory_window,0):candle_stream_index]
		
		needle = np.float64(np.array(candles)[:,self.line_channel])
		needle = np.expand_dims(needle,axis=0) #so we can apply it to some hay
		normed_needle, this_min, this_max = self.normalise(needle)
		
		haystack_errors = self.haystack_matching_errors(normed_needle)
		haystack_errors = sorted(haystack_errors,key=lambda m:m[2])
		
		shapes = []
		for he in haystack_errors[1:self.n_projections+1]: #omit first result - this is probably the actual result itself!
			shape = self.haystack[int(he[0]),int(he[1]):int(he[1]+self.memory_window+self.projection_length),self.line_channel]
			shapes.append(shape)
		
		new_shapes = self.rescale(np.stack(shapes,axis=1),this_min,this_max)
		return new_shapes
	
	#@override
	def _determine(self,candle_stream_index,candle_stream):
		
		if candle_stream_index < self.memory_window: #don't bother with detections smaller than the window
			return 0
		
		new_shapes = self._get_closest_paths(candle_stream,candle_stream_index)
		
		#pdb.set_trace()
		standard_dev = np.std(new_shapes[-1,:])
		
		candles = candle_stream[max(candle_stream_index-self.memory_window,0):candle_stream_index]
		needle = np.float64(np.array(candles)[:,self.line_channel])
		needle = np.expand_dims(needle,axis=0) #so we can apply it to some hay
		_, _, this_max = self.normalise(needle)
		
		fitness = this_max / standard_dev #normalise std but do a 1 over score so bigger -> better!  
		
		mean_end = np.mean(new_shapes[-1,:]) 
		last_close = candle_stream[candle_stream_index][self.line_channel]
		#if we moved more than the sd then consider it a good choice
		direction = 1 if mean_end > last_close + standard_dev else -1 if mean_end < last_close - standard_dev else 0
		
		return (fitness * direction).reshape((1))[0]
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
		
		pdb.set_trace()
		
		best_path = []
		for (x,y) in zip(x_axis,paths[:,0]):
			best_path.append(chv.Point(x,y))
		
		all_path = [] 
		for path in paths: 
			for (x,y) in zip(x_axis,paths[0]):
				all_path.append(chv.Point(x,y)) #s deliberately missed off since we are working with a single path with None points
			all_path.append(chv.Point(None,None))
		
		confuse_path = []
		for (x,y) in zip(x_axis,np.min(paths,axis=1)):
			confuse_path.append(chv.Point(x,y))
		confuse_path.append(chv.Point(None,None))
		for (x,y) in zip(x_axis,np.max(paths,axis=1)):
			confuse_path.append(chv.Point(x,y))
		
		this_view.draw('price_actions keyinfo paths',all_path)
		this_view.draw('price_actions bearish paths',confuse_path)		
		this_view.draw('price_actions bullish paths',best_path)
		
		base_view += this_view
		
		return base_view 










































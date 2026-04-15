

import time
import numpy as np
import scipy.spatial 
from enum import Enum

import tqdm

from air.charting.candle_stick_pattern import * 
import air.charting.candle_stick_functions as csf
from air.indicators.indicator import Indicator
from air.charting.chart_pattern import ChartPattern 

from air.utils import overrides


import logging 
log = logging.getLogger(__name__)






# private helper functions
#getting movements from values
def _movement_geo(np_values):
	before_values = np_values[:,:-1]
	after_values = np_values[:,1:]
	multiply_moves = 1 + ((after_values - before_values) / before_values)
	pad = np.zeros((np_values.shape[0],1))
	return np.concatenate([pad,multiply_moves],axis=1)



#class MatchMode(Enum):
#	BACKTEST = 0
	


#
# a matching pattern is one that looks at the movement of everything in the market (given a "haystack") 
# and then finds the most common ones using a current instrument movement (a "needle"). 
#
# WARNING: this class implementation is not backtest safe! the haystack will contain future values. To do 
# backtesting with this class, either create a new one per instance in time or use a different class that 
# has been designed to be backtestable (MatchPatternBacktest)
class MatchPatternInstance(ChartPattern):
	
	
	channel_keys = {'BIAS':0,'BIAS_RATIO':1,'AVERAGE':2,'STD':3,'ERROR':4,'ERROR_STD':5} 
	#channel_styles = {'BIAS':'neutral','BIAS_RATIO':'neutral','AVERAGE':'neutral','STD':'neutral','ERROR':'neutral','ERROR_STD':'neutral'} 
	candle_sticks = True
	
	#_haystack_step = 100 #for every 100 candles, create a new haystack (downsampling)
	_haystack_window = 2000 #limit to this many candles ago for speed & integrity (very old stuff is not as useful) 
	_precandles = None # call this to get single values per candle first. If it is None then close is used. 
	
	_haystack_query = None #a scipy kdtree with m = self._need_length
	_haystack_paths = None
	_haystack_result = None #an example of what happened next with a similar pattern 
	#_haystack_needle_position_diff =  3# ?place where the needle is in relation to the haystack?
	
	_needle_length = 10 
	_prediction_length = 5
	_n_predictions = 20
	
	
	def explain(self):
		return """
		A match in the market is a historic movement that has happened similar to the one observed. We can use this to 
		attempt to predict the next movement, by collecting what happened next in the market. If this is done on a number
		of matches, a preciction can be built of what might happen next for our current observation. 
		
		Note: This indicator is highly experimental and shouldn't be used on its own. 
		WARNING: This class is not back testable (unless done one per test) 
		"""
	
	#ensure the haystack is always before np_candles to not get a biased result! 
	def set_haystack(self,haystack_npc):
		haystack_candles = haystack_npc #remember - construct builds the candle block.
		#consider allowing streams of different lengths so we can dump anything in  & use nans for padding 
		
		haystack_values = haystack_candles[:,:,csf.close]
		
		if self._precandles and callable(self._precandles._perform):
			haystack_values = self._precandles._perform(haystack_candles)[:,:,0]
		
		#only use the last _haystack_window values for speed purposes
		haystack_values = _movement_geo(haystack_values)
		haystack_values = haystack_values[:,-(self._haystack_window+self._prediction_length):] #chop start off since it is useless? 
		
		haystack_window_chunks = np.lib.stride_tricks.sliding_window_view(haystack_values,window_shape=(self._needle_length+self._prediction_length),axis=1)
		haystack_windows = np.concatenate(haystack_window_chunks,axis=0) #test shape  = (?,needle + prediction)
		
		haystack_lhs = haystack_windows[:,:self._needle_length]
		haystack_rhs = haystack_windows[:,self._needle_length:]
		
		self._haystack_paths = haystack_lhs
		self._haystack_query = scipy.spatial.kdtree.KDTree(haystack_lhs) #don't change haystack_lhs ever! 
		self._haystack_result = haystack_rhs
	
	
	@overrides(ChartPattern)
	def _perform(self,np_candles):
		
		assert self._haystack_query is not None, "You must first provide haystack data with set_haystack(...)"
		
		full_paths, distances = self._get_haystack_paths(np_candles)
		
		play_outs = np.cumprod(full_paths[:,self._needle_length:],axis=1)
		#stats we probably want to get from the paths
		end_moves = play_outs[:,:,-1] - 1 #turn it back to a difference (centered around 0)
		
		#bias = np.sum(end_moves,axis=1)
		udr = np.divide(np.sum(end_moves > 0,axis=1),np.sum(end_moves < 0,axis=1)) #np.divide to not report warning for inf
		average_end = np.mean(end_moves,axis=1)
		std = np.std(end_moves,axis=1)
		query_error = np.mean(distances,axis=1)
		query_std = np.std(distances,axis=1)
		
		bias_flag = np.zeros((std.shape[0],)) 
		
		#add some bias rules here to determine from the results above if the pattern is bullish or bearish
		bias_flag[average_end > 0.001] = 1 # larger than 0.1% move upwards
		bias_flag[average_end < -0.001] = -1 #larger than 0.1% move downwards 
		bias_flag[udr > 0.75] = 1 #over 75% of predictions landed upwards 
		bias_flag[udr < 0.25] = -1 #over 75% of predictions landed downwards 
		
		#now extra constraints to delete biases
		bias_flag[query_error > 0.005] = 0 # over half % query error is unacceptable apparently! 
		
		#pdb.set_trace()
		#print('check_paths') #TODO: this is incorrect?
		rr = np.stack([bias_flag,udr,average_end,std,query_error,query_std])
		result = np.reshape(np.transpose(rr),(rr.shape[1],1,rr.shape[0]))
		return  result# the result for each channel :D 
		
	#@overrides(Indicator)
	#def calculate_multiple(self,candle_streams,candle_stream_index):
	#	#this is  different to the standard then?
	#	pass 
	
	def _get_haystack_paths(self,np_candles):
		values = np_candles[:,:,csf.close]
		
		if self._precandles and callable(self._precandles._perform):
			values = self._precandles._perform(np_candles)[:,:,0]
		
		values = _movement_geo(values)
		
		#just get the end result instead! 
		values = values[:,-(self._needle_length):] # change this for the full backtest version
		
		
		distances, result_indexs = self._haystack_query.query(values,self._n_predictions)
		
		#n results by _n_predictions - make array of n by _n_predictions by _prediction_length
		predicted_paths = np.zeros((values.shape[0],self._n_predictions,self._prediction_length))
		haystack_paths = np.zeros((values.shape[0],self._n_predictions,self._needle_length))
		
		#need some way of vectorizing this bit for speed 
		#for c in range(0,values.shape[0]):
		predicted_paths[:,:,:] = self._haystack_result[result_indexs[:,:]]
		haystack_paths[:,:,:] = self._haystack_paths[result_indexs[:,:]] 
			
		#for drawing the paths on a chart
		full_paths = np.concatenate([haystack_paths,predicted_paths],axis=2)
		return full_paths, distances

	@overrides(ChartPattern)
	def draw_snapshot(self,np_candles,instrument_index,snapshot_index):
		#np_candles, _ = self._construct(np_candles)
		full_paths, distances = self._get_haystack_paths(np_candles)
		paths = full_paths[instrument_index]
		anchor = np_candles[instrument_index,-self._needle_length,csf.close] #close? or typical? :/ 
		#expand paths to be of similar value to the anchor		
		
		anchorn = np.stack([anchor]*paths.shape[0],axis=0)
		paths = np.concatenate([anchorn[:,np.newaxis],paths],axis=1) #add anchor price 
		paths = np.cumprod(paths,axis=1)[:,1:]
		
		x_start = np_candles.shape[1] - self._needle_length
		x_axis = range(x_start,x_start+self._needle_length+self._prediction_length)
		
		
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
		
		return this_view 

		
		
		
		

#an improved version of the match pattern class that is backtestable. This instance is very slow compared to 
#the MatchPatternInstance class so it should really only be used for backtesting purposes. In otherwords, 
#do not use this class when filtering/finding signals for right now. 
class MatchPattern(ChartPattern):
	channel_keys = {'BIAS':0,'BIAS_RATIO':1,'AVERAGE':2,'STD':3,'ERROR':4,'ERROR_STD':5} 
	#channel_styles = {'BIAS':'neutral','BIAS_RATIO':'neutral','AVERAGE':'neutral','STD':'neutral','ERROR':'neutral','ERROR_STD':'neutral'} 
	candle_sticks = True
	
	_haystack_step = 100 #for every n candles, create a new haystack (downsampling)
	_haystack_window = 1000 #limit to this many candles ago for speed & integrity (very old stuff is not as useful + need a full haystack before we can backtest)
	_precandles = None # call this to get single values per candle first. If it is None then close is used. 
	
	_haystack_query = None #a scipy kdtree with m = self._need_length
	_haystack_paths = None
	_haystack_result = None #an example of what happened next with a similar pattern 
	#_haystack_needle_position_diff =  3# ?place where the needle is in relation to the haystack?
	
	_needle_length = 10 
	_prediction_length = 5
	_n_predictions = 20
	
	_move_param = 0.001 #0.1%
	_ratio_param = 0.3 

	

	#from a bunch of data, create a load of haystacks of length _haystack_window
	def set_haystack(self,haystack_npc):
		haystack_candles = haystack_npc #remember - construct builds the candle block.
		#consider allowing streams of different lengths so we can dump anything in  & use nans for padding 
		
		haystack_values = haystack_candles[:,:,csf.close]
		
		if self._precandles and callable(self._precandles._perform):
			haystack_values = self._precandles._perform(haystack_candles)[:,:,0]
		
		#only use the last _haystack_window values for speed purposes
		haystack_values = _movement_geo(haystack_values)
		haystack_values = haystack_values[:,-(self._haystack_window+self._prediction_length):] #chop start off since it is useless? 
		
		haystack_window_chunks = np.lib.stride_tricks.sliding_window_view(haystack_values,window_shape=(self._needle_length+self._prediction_length),axis=1)
		haystack_windows = np.concatenate(haystack_window_chunks,axis=0) #test shape  = (?,needle + prediction)
		
		haystacks_through_time = []
		for x in range(0, haystack_windows.shape[0]-self._haystack_window, self._haystack_step):
			haystacks_through_time.append(haystack_windows[x:x+self._haystack_window])
		
		
		#set multiple kdtrees here
		forest = []
		paths = []
		rhs = []
		log.info('Setting up haystacks...')
		for haystack in tqdm.tqdm(haystacks_through_time): #create all the haystacks 
			haystack_lhs = haystack[:,:self._needle_length]
			haystack_rhs = haystack[:,self._needle_length:]
			forest.append(scipy.spatial.kdtree.KDTree(haystack_lhs))
			rhs.append(haystack_rhs)
			paths.append(haystack_lhs)
		
		self._haystack_paths = np.array(paths)
		self._haystack_query = np.array(forest) 
		self._haystack_result = np.array(rhs)


	@overrides(ChartPattern)
	def _perform(self,np_candles,mask=None,return_flat=False):
		
		#assert self._haystack_query is not None, "You must first provide haystack data with set_haystack(...)"
		needles, haystack_indexs = self._get_window_needles(np_candles,mask) 
		
		#BUG?=>
		#pdb.set_trace()
		#print('Test the sizes of stuff. Work out why we have a 0 distance')
		
		full_paths, distances = self._get_haystack_paths(needles, haystack_indexs)
		
		#get stats for each needle
		play_outs = np.cumprod(full_paths[:,:,self._needle_length:],axis=2)
		#stats we probably want to get from the paths
		end_moves = play_outs[:,:,-1] - 1 #turn it back to a difference (centered around 0)
		
		#sumbias = np.sum(end_moves,axis=1) #useless?
		udr = np.divide(np.sum(end_moves > 0,axis=1),end_moves.shape[1]) #np.divide to not report warning for inf
		average_end = np.mean(end_moves,axis=1)
		std = np.std(end_moves,axis=1)
		query_error = np.mean(distances,axis=1)
		query_std = np.std(distances,axis=1)
		bias_flag = np.zeros((std.shape[0],)) 
		
		#add some bias rules here to determine from the results above if the pattern is bullish or bearish
		bias_flag[average_end > self._move_param] = 1 # larger than 0.1% move upwards
		bias_flag[average_end < -self._move_param] = -1 #larger than 0.1% move downwards 
		bias_flag[udr > (1-self._ratio_param)] = 1 #over 75% of predictions landed upwards 
		bias_flag[udr < self._ratio_param] = -1 #over 75% of predictions landed downwards 
		
		#now extra constraints to delete biases
		bias_flag[query_error > 0.005] = 0 # over half % query error is unacceptable apparently! 
		
		
		#pdb.set_trace()
		#print('check_paths')
		#remember to paste back nans at the start for when there was no haystack available - use mask for this
		
		results = np.stack([bias_flag,udr,average_end,std,query_error,query_std],axis=1) # the result for each channel :D 
		n_results = 6
		
		instrument_indexs, time_indexs = np.where(np.ones((np_candles.shape[0],np_candles.shape[1] - self._haystack_window)))
		
		if mask is not None:
			this_mask = mask[:,-number_windows:] #1 mask per window - chop off useless first ones
			instrument_indexs, time_indexs = np.where(this_mask) 
		
		if return_flat:
			return np.concatenate([instrument_indexs[:,np.newaxis],time_indexs[:,np.newaxis],results],axis=1)
					
		result_block = np.full((np_candles.shape[0],np_candles.shape[1] - self._haystack_window,n_results),np.nan)
		result_block[instrument_indexs,time_indexs] = results
		
		lpad = np.full((np_candles.shape[0],self._haystack_window,n_results),np.nan)
		return np.concatenate([lpad,result_block],axis=1)

	
	def _get_window_needles(self,np_candles,mask): #also returns  the haystack that the needle can be queried against 
		
		values = np_candles[:,:,csf.close]
		
		if self._precandles and callable(self._precandles._perform):
			values = self._precandles._perform(np_candles)[:,:,0]
		values = _movement_geo(values)
		
		#take off the head values as they are not far along enough to get a haystack 
		values = values[:,self._haystack_window-self._needle_length+1:] 
		number_windows = values.shape[1]-self._needle_length+1
		tindexs = np.stack([np.arange(number_windows)]*values.shape[0],axis=0)
		
		#pdb.set_trace()
		needles_unwindowed = np.lib.stride_tricks.sliding_window_view(values,window_shape=self._needle_length,axis=1)
		needles_windowed = np.concatenate(needles_unwindowed,axis=0)
		
		haystack_indexs = np.concatenate(tindexs // self._haystack_step, axis=0)
	
		if mask is not None: 
			this_mask = mask[:,-number_windows:] #1 mask per window - chop off useless first ones
			instrument_indexs, window_indexs = np.where(this_mask) 
			select_indexs = (number_windows * instrument_indexs) + window_indexs
			
			haystack_indexs = haystack_indexs[select_indexs]
			needles_windowed = needles_windowed[select_indexs]
			
		return needles_windowed, haystack_indexs
	
	#pluralise to multiple haystacks somehow? 
	def _get_haystack_paths(self,needles,haystack_indexs):
		
		#result arrays 
		full_paths = np.full((needles.shape[0],self._n_predictions,self._needle_length + self._prediction_length),np.nan)
		distances = np.full((needles.shape[0],self._n_predictions),np.nan) #one distance per result! 
		
		vals,counts = np.unique(haystack_indexs,return_counts=True) #for each haystack index, lets get them all and then count how many needles we are looking at in each. 
		
		log.info('Performing haystack searches... ')
		for (vi,cs) in tqdm.tqdm(list(zip(vals,counts))):
			#pdb.set_trace()
			indexer = np.where(haystack_indexs == vi)
			these_dists, result_indexs = self._haystack_query[vi].query(needles[indexer],self._n_predictions)
			distances[indexer] = these_dists
			
			lhs = self._haystack_paths[vi][result_indexs]
			rhs = self._haystack_result[vi][result_indexs]
			these_paths = np.concatenate([lhs,rhs],axis=2)
			full_paths[indexer] = these_paths
			#print('check')
			
		#pdb.set_trace()
		return full_paths, distances
	
	
	@overrides(ChartPattern)
	def draw_snapshot(self,np_candles,instrument_index,snapshot_index):
		mask = self._create_mask(np_candles,instrument_index,snapshot_index)
		
		needles, haystack_indexs = self._get_window_needles(np_candles,mask) 
		
		#BUG?=>
		#pdb.set_trace()
		#print('Test the sizes of stuff. Work out why we have a 0 distance')
		
		full_paths, distances = self._get_haystack_paths(needles, haystack_indexs)
		
		instrument_index, t_index = np.where(mask)
		x_start = t_index - self._needle_length
		anchors = np_candles[instrument_index,x_start-1,csf.close] #anchor => one before where the needle starts 
		
		this_view = chv.ChartView()
		for (xs, a, paths) in zip(x_start, anchors, full_paths):
			x_axis = range(xs,xs+self._needle_length+self._prediction_length)
	
			#expand paths to be of similar value to the anchor		
			
			anchorn = np.stack([a]*paths.shape[0],axis=0)
			paths = np.concatenate([anchorn[:,np.newaxis],paths],axis=1) #add anchor price 
			paths = np.cumprod(paths,axis=1)[:,1:]
						
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
		
		return this_view 

		
		





















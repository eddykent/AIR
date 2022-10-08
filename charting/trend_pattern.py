
import numpy as np 
#import scipy


import pdb

#from indicators.indicators import Indicator
import charting.chart_viewer as chv 
import charting.candle_stick_functions as csf
import charting.trend_line_functions as tlf 
from setups.trade_setup import TradeSignal, TradeDirection, SetupCriteria
from utils import overrides 

from charting.chart_pattern import ChartPattern

#detection: breakouts (when going over a trendline) and retests (when going near a trendline). 
#breakouts may need confirmation
#retests should be on trendlines that are far apart and not sloped too much in same direction (eg sell on downward wedge..) 

#pluralise over many trend patterns? or use cache?
class TrendPattern(ChartPattern):
	#put any global stuff in here to do with the trending stuff 
	
	#the top and bottom points 
	def tops_bottoms(self,xtreme_windows):	
		maximum_mask = xtreme_windows[:,:,2] == 1
		minimum_mask = xtreme_windows[:,:,2] == 0
		
		maximums = self._mask_to_flatlist(xtreme_windows,maximum_mask,just_right=True)
		minimums = self._mask_to_flatlist(xtreme_windows,minimum_mask,just_right=True)
		
		return maximums,minimums
		
	#for every entry, for the set of points, find the best fit line that is a sloped support/resistance of the points
	#starts from the last point 
	def _find_boundary_trends(self,points,top=False):
		parametrics = tlf.make_parametric(points)
		Xs = points[:,:,0]
		Ys = points[:,:,1]
		
		levels = Ys - parametrics
		end_indexs = np.nanargmax(levels,axis=1) if top else np.nanargmin(levels,axis=1)
		end_indexs = end_indexs.astype(np.int)
		
		x1s = Xs[:,0]
		y1s = Ys[:,0]
		x2s = Xs[np.arange(points.shape[0]),end_indexs]
		y2s = Ys[np.arange(points.shape[0]),end_indexs]
		
		trendlines = np.stack([x1s,y1s,x2s,y2s],axis=1)
		
		#need to work out what the error is for measureing later. project then negate the points, then squaresum 
		steps = (y2s - y1s) / end_indexs
		indexs = np.arange(points.shape[1])
		perfect_points_diff = np.outer(steps,indexs[np.newaxis,:])
		perfect_points = np.stack([y1s]*points.shape[1],axis=1) + perfect_points_diff
		
		trenderrors = np.nansum(np.power(perfect_points - Ys,2),axis=1) / y1s
		return np.concatenate([trendlines,trenderrors[:,np.newaxis]],axis=1)
		
	#draws the standard trendlines found from the functions above - might suffice for all patterns? 
	@overrides(ChartPattern)
	def draw_snapshot(self,np_candles,snapshot_index,instrument_index):
		mask = self._create_mask(np_candles,instrument_index,snapshot_index)
		xtreme_windows, _ = self._generate_xtreme_windows(np_candles,mask)
		
		maxs, mins = self.tops_bottoms(xtreme_windows)
		maxlines = self._find_boundary_trends(maxs[:,::-1,:],True)
		minlines = self._find_boundary_trends(mins[:,::-1,:],False)
		
		lines = np.stack([maxlines,minlines],axis=1) #zip together 
		
		this_view = chv.ChartView()
		for [maxline, minline] in lines: 
			x1,y1,x2,y2,_ = maxline
			chv_maxline = chv.Line(x1,y1,x2,y2)
			
			x1,y1,x2,y2,_ = minline
			chv_minline = chv.Line(x1,y1,x2,y2)
			
			this_view.draw('trends bullish lines',chv_maxline)
			this_view.draw('trends bearish lines',chv_minline)
		
		return this_view
	
	@overrides(ChartPattern)
	def _chart_perform(self,xtreme_bundle):
		xtreme_windows = xtreme_bundle.xtreme_windows
		breakout_windows = xtreme_bundle.breakout_windows
		x_start_pos = xtreme_bundle.x_start_positions
		
		maxs, mins = self.tops_bottoms(xtreme_windows)
		maxlines = self._find_boundary_trends(maxs[:,::-1,:],True)
		minlines = self._find_boundary_trends(mins[:,::-1,:],False)
		
		#check last breakout candle if it is above/below the trendlines 
		#pdb.set_trace()
		after_max_lines = tlf.projection(maxlines,x_start_pos + self._breakout_candles -1)
		after_min_lines = tlf.projection(minlines,x_start_pos + self._breakout_candles -1)
		
		
		after_maxs = np.maximum(after_max_lines,after_min_lines)
		after_mins = np.minimum(after_max_lines,after_min_lines)
		
		#simple for now, more later 
		last_close = breakout_windows[:,-1,csf.close]
		
		result = np.zeros((xtreme_windows.shape[0], 5))
		
		result[last_close > after_maxs,1] = (last_close - after_maxs)[last_close > after_maxs]
		result[last_close < after_mins,2] = (after_mins - last_close)[last_close < after_mins]
		result[:,2] = maxlines[:,3]
		result[:,3] = minlines[:,4]
		#print('got trendlines?')
		
		return self._constraints(result)
	
	#function for telling if this is a correct pattern or not. 
	def _constraints(self,np_results):
		return np_results	#return everything as there is no constraints on the generic pattern 
	
	#def bottom_line(self,maxlines,minlines,)?

#wedges too? 
class SymmetricTriangle(TrendPattern): #is this ONLY symmetricals? use as base for triangulars?
	
	_required_candles = 100
	
	
class RisingWedge(TrendPattern):
	pass
	
class FallingWedge(TrendPattern):
	pass

#rising/falling triangles?

class ApproximateChannel(TrendPattern):
	pass
	
class ParalellChannel(TrendPattern):
	pass
	

#class SymmetricTriangle, Wedge, etc 











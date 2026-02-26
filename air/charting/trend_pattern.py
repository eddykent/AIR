
import numpy as np 
#import scipy


import pdb

#from indicators.indicators import Indicator
import air.charting.chart_viewer as chv 
import air.charting.candle_stick_functions as csf
import air.charting.trend_line_functions as tlf 
from air.setups.trade_setup import TradeSignal, TradeDirection, SetupCriteria
from air.utils import overrides 

from air.charting.chart_pattern import ChartPattern

#detection: breakouts (when going over a trendline) and retests (when going near a trendline). 
#breakouts may need confirmation
#retests should be on trendlines that are far apart and not sloped too much in same direction (eg sell on downward wedge..) 

#pluralise over many trend patterns? or use cache?
class TrendPattern(ChartPattern):
	
	#put any global stuff in here to do with the trending stuff 
	_trend_end_gap = 1
	
	
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
		end_indexs = end_indexs.astype(int)
		
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
		
		trenderrors = np.nansum(np.power(perfect_points - Ys,2),axis=1) / y1s  #consider using objective function or something?
		return np.concatenate([trendlines,trenderrors[:,np.newaxis]],axis=1)
		
	#draws the standard trendlines found from the functions above - might suffice for all patterns? 
	@overrides(ChartPattern)
	def draw_snapshot(self,np_candles,instrument_index,snapshot_index):
		line_buffer = 5 #how much to hang trendlines over the edge
		
		mask = self._create_mask(np_candles,instrument_index,snapshot_index)
		xtreme_windows, _ = self._generate_xtreme_windows(np_candles,mask)
		x_pos = self._get_x_positions(np_candles,mask)  + self._breakout_candles + line_buffer
		
		maxs, mins = self.tops_bottoms(xtreme_windows)
		maxlines = self._find_boundary_trends(maxs[:,::-1,:],True) # => x1 > x2 always
		minlines = self._find_boundary_trends(mins[:,::-1,:],False)
		
		maxlines = tlf.stretch_move(maxlines,maxlines[:,tlf.x2]-line_buffer,x_pos)
		minlines = tlf.stretch_move(minlines,minlines[:,tlf.x2]-line_buffer,x_pos)
				
		#maxlines = tlf.stretch_move(maxlines,np.minimum(maxlines[:,tlf.x1],maxlines[:,tlf.x2])-line_buffer,x_pos)
		#minlines = tlf.stretch_move(minlines,np.minimum(minlines[:,tlf.x1],minlines[:,tlf.x2])-line_buffer,x_pos)
		
		lines = np.stack([maxlines,minlines],axis=1) #zip together
		 
		
		this_view = chv.ChartView()
		for [maxline, minline] in lines: 
			x1,y1,x2,y2,_ = maxline
			chv_maxline = chv.Line(x1,y1,x2,y2)
			
			x1,y1,x2,y2,_ = minline
			chv_minline = chv.Line(x1,y1,x2,y2)
			
			this_view.draw('trends bearish lines',chv_maxline)
			this_view.draw('trends bullish lines',chv_minline)
		
		return this_view
	
	@overrides(ChartPattern)
	def _chart_perform(self,xtreme_bundle):
		xtreme_windows = xtreme_bundle.xtreme_windows
		
		breakout_windows = xtreme_bundle.breakout_windows
		x_start_pos = xtreme_bundle.x_start_positions
		average_true_ranges = xtreme_bundle.average_true_ranges
		
		maxs, mins = self.tops_bottoms(xtreme_windows)
		
		maxlines = self._find_boundary_trends(maxs[:,::-1,:],True)  # => x1 > x2 always
		minlines = self._find_boundary_trends(mins[:,::-1,:],False)
		
		#TODO: number of touches?
		lines = np.stack([minlines,maxlines])
		
		result = self._trend_perform(lines,breakout_windows,x_start_pos,average_true_ranges)
		
		return result
		
	#override this on the last pattern when we are determining what the shape is for a generic pattern 
	def _trend_perform(self,lines,breakout_windows,x_start_pos,average_true_ranges): #must return -1,0,1
		
		correct_trends = self._check_trendlines(lines,x_start_pos,average_true_ranges) #can be used later to determine the trend instead? 
		
		#assume the pattern either breaks out or reflects off one of the lines 
		#if it does neither, or both but differing directions, bias = 0 
		breakout_direction = self._get_breakouts(lines,breakout_windows,x_start_pos,average_true_ranges)
		reflect_direction = self._get_reflects(lines,breakout_windows,x_start_pos,average_true_ranges)		
		
		result =  np.zeros((x_start_pos.shape[0],1)) 
		
		bullish = (breakout_direction + reflect_direction) > 0
		bearish = (breakout_direction + reflect_direction) < 0
		
		result[correct_trends & bullish,0] = 1
		result[correct_trends & bearish,0] = -1
		
		return result 
		
	
	#functions to override - for telling if this is a correct pattern or not & direction bias
	def _check_trendlines(self,lines,x_start_pos,avearage_true_ranges): # checks the pattern shape
		#note: candles should NOT be passsed in here as we are just inspecting the lines 
		return np.full(x_start_pos.shape,True)	#return true as there is no constraints on the generic pattern 
	
	#a pattern breaks out if the price closes on the the other side of the trend, and is bullish/bearish 
	def _get_breakouts(self,lines,breakout_windows,x_start_pos,average_true_ranges):  #  determines if the pattern is bullish/bearish
		return np.zeros(x_start_pos.shape)  #no breakout detection for blank pattern
			
	#a pattern reflects if the price touches (open/close still in the pattern) the trend and then moves in opposite direction
	def _get_reflects(self,lines,breakout_windows,x_start_pos,average_true_ranges):
		return np.zeros(x_start_pos.shape)  #no reflect detection for blank pattern



#wedges too? #falling & rising?
class Triangle(TrendPattern): #is this ONLY symmetricals? use as base for triangulars?
	
	_required_candles = 100
	
	@overrides(TrendPattern)
	def _check_trendlines(self,lines,x_start_pos,average_true_ranges):
		minlines,maxlines = lines 
		
		#check slopes 
		rising_mins = tlf.gradient(minlines) > 0 
		falling_maxs = tlf.gradient(maxlines) < 0
		
		#check apex forward enough (after x_start_pos + breakout_candles )
		ymin = tlf.projection(minlines,x_start_pos+self._breakout_candles)
		ymax = tlf.projection(maxlines,x_start_pos+self._breakout_candles)

		suitable_apex = ymax >= ymin + (self._trend_end_gap*average_true_ranges)
		
		return rising_mins & falling_maxs & suitable_apex
		
	@overrides(TrendPattern)
	def _get_breakouts(self,lines,breakout_windows,x_start_pos,average_true_ranges):
		
		minline, maxline = lines
		#get last candle in breakout window
		last_candle = breakout_windows[:,-1,:]
		#bullish = candle opens above maxline and closed bullish 
		bullish = (last_candle[:,csf.open] > tlf.projection(maxline,x_start_pos)) & csf.bullish(last_candle) # x_start_pos + self._breakout_candles? 
		#bearish = candle opens below min line and closed bearish 
		bearish = (last_candle[:,csf.open] < tlf.projection(minline,x_start_pos)) & csf.bearish(last_candle)
		
		result = np.zeros(x_start_pos.shape)
		result[bullish] = 1
		result[bearish] = -1
		
		return result
	
	def _get_reflects(self,lines,breakout_windows,x_start_pos,average_true_ranges):
		minline, maxline = lines
		
		last_candle = breakout_windows[:,-1,:]
		
		ymin = tlf.projection(minline,x_start_pos+self._breakout_candles)
		ymax = tlf.projection(maxline,x_start_pos+self._breakout_candles)
		
		#bearish = one or more high goes over top line, but last candle body is below line and bearish 
		bullish = (csf.lowest(breakout_windows) < ymin) & (last_candle[:,csf.open] > ymin) & csf.bullish(last_candle)
		bearish = (csf.highest(breakout_windows) > ymax) & (last_candle[:,csf.open] < ymax) & csf.bearish(last_candle)
		
		#ensure there's enough channel to move in
		large_enough = (ymax - ymin)   > (4 * average_true_ranges)
		
		result = np.zeros(x_start_pos.shape)  
		result[bullish & large_enough] = 1
		result[bearish & large_enough] = -1
		
		return result
		
	
	
class SymmetricalTriangle(Triangle):
	
	@overrides(Triangle)
	def _check_trendlines(self,lines,x_start_pos,average_true_ranges):
		
		is_triangle = super()._check_trendlines(lines,x_start_pos,average_true_ranges)
		
		minlines,maxlines = lines
		level_grad = np.abs(tlf.gradient(minlines) + tlf.gradient(maxlines)) / 2.0
		
		is_level = (level_grad * self._required_candles) < average_true_ranges   ##= True if the middle gradient differs by at most 2 range? 

		return is_triangle & is_level
		
	

#falling/rising triangle? unsure how to determine... 
class RisingTriangle(Triangle):
	
	@overrides(TrendPattern)
	def _check_trendlines(self,lines,x_start_pos,average_true_ranges):
		minlines,maxlines = lines 
		
		#check slopes 
		rising_mins = tlf.gradient(minlines) > 0 
		level_maxs = np.abs(tlf.gradient(maxlines) * self._required_candles) < average_true_ranges
		
		#check apex forward enough (after x_start_pos + breakout_candles )
		ymin = tlf.projection(minlines,x_start_pos+self._breakout_candles)
		ymax = tlf.projection(maxlines,x_start_pos+self._breakout_candles)

		suitable_apex = ymax >= ymin + (self._trend_end_gap*average_true_ranges)
		
		return rising_mins & level_maxs & suitable_apex

#falling/rising triangle? unsure how to determine... 
class FallingTriangle(Triangle):
	
	@overrides(TrendPattern)
	def _check_trendlines(self,lines,x_start_pos,average_true_ranges):
		minlines,maxlines = lines 
		
		#check slopes 
		level_mins = np.abs(tlf.gradient(minlines) * self._required_candles) < average_true_ranges 
		falling_maxs = tlf.gradient(maxlines) <  0 
		
		#check apex forward enough (after x_start_pos + breakout_candles )
		ymin = tlf.projection(minlines,x_start_pos+self._breakout_candles)
		ymax = tlf.projection(maxlines,x_start_pos+self._breakout_candles)

		suitable_apex = ymax >= ymin + (self._trend_end_gap*average_true_ranges)
		
		return level_mins & falling_maxs & suitable_apex


#only look for buys?
class RisingWedge(Triangle):
	
	@overrides(Triangle)
	def _check_trendlines(self,lines,x_start_pos,average_true_ranges):
		minlines,maxlines = lines 
		
		#check slopes 
		rising_mins = tlf.gradient(minlines) > 0 
		rising_maxs = tlf.gradient(maxlines) > 0
		
		#check apex forward enough (after x_start_pos + breakout_candles )
		ymin = tlf.projection(minlines,x_start_pos+self._breakout_candles)
		ymax = tlf.projection(maxlines,x_start_pos+self._breakout_candles)

		suitable_apex = ymax >= ymin + (self._trend_end_gap*average_true_ranges)
		
		return rising_mins & rising_maxs & suitable_apex
	
#only look for sells?
class FallingWedge(Triangle):
	
	@overrides(Triangle)
	def _check_trendlines(self,lines,x_start_pos,average_true_ranges):
		minlines,maxlines = lines 
		
		#check slopes 
		falling_mins = tlf.gradient(minlines) < 0 
		falling_maxs = tlf.gradient(maxlines) < 0
		
		#check apex forward enough (after x_start_pos + breakout_candles )
		ymin = tlf.projection(minlines,x_start_pos+self._breakout_candles)
		ymax = tlf.projection(maxlines,x_start_pos+self._breakout_candles)

		suitable_apex = ymax >= ymin + (self._trend_end_gap*average_true_ranges)
		
		return falling_mins & falling_maxs & suitable_apex



#channels 
class ApproximateChannel(TrendPattern):
	
	@overrides(TrendPattern)
	def _check_trendlines(self,lines,x_start_pos,average_true_ranges):
		minlines,maxlines = lines 
		return np.abs((tlf.gradient(minlines)-tlf.gradient(maxlines)) * self._required_candles) < average_true_ranges
	
	@overrides(TrendPattern)
	def _get_breakouts(self,lines,breakout_windows,x_start_pos,average_true_ranges):
		#same as triangle anyway but we dont want to call this a triangle (DRY)
		return Triangle._get_breakouts(self,lines,breakout_windows,x_start_pos,average_true_ranges) 
	
	@overrides(TrendPattern)
	def _get_reflects(self,lines,breakout_windows,x_start_pos,average_true_ranges):
		#same as triangle anyway but we dont want to call this a triangle (DRY)
		return Triangle._get_reflects(self,lines,breakout_windows,x_start_pos,average_true_ranges) 
		
		
	
#force upper or lower line to be same grad as the other and then 
class ParalellChannel(TrendPattern):
	pass


class Rectangle(ApproximateChannel):
	
	@overrides(ApproximateChannel)
	def _check_trendlines(self,lines,x_start_pos,average_true_ranges):
		minlines,maxlines = lines 
		is_channel = super()._check_trendlines(lines,x_start_pos,average_true_ranges)
		is_min_level = (tlf.gradient(minlines) * self._required_candles) < average_true_ranges
		is_max_level = (tlf.gradient(maxlines) * self._required_candles) < average_true_ranges
		return is_channel & is_min_level & is_max_level
	
#divergent patterns?











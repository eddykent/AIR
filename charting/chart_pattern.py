
#larger chart patterns - Support/Resistance Bounce, HeadShoulders, RisingFlags, rising/falling channel

#chart patterns are not of any fixed size, but they make use of support and resistance areas and of extreme points! 
import numpy as np
import datetime

from enum import Enum
from collections import namedtuple
import json

Extremity = namedtuple('Extremity','type value index')

import charting.candle_stick_functions as csf
from charting.candle_stick_pattern import CandleStickPattern
import charting.chart_viewer as chv
from utils import ListFileReader

import pdb

#used for initialising lows and for reporting non-fitting things (eg no trendline was able to be fit)
MAX_ERROR_VALUE = 999999999  #define?

class Level(Enum):
	VOID = 0
	SUPPORT = 1
	RESISTANCE = 2
	RETEST = 3
	BREAKOUT = 4
	BEARISH = 5
	BULLISH = 6

class ExtremityType(Enum):
	MAXIMUM = -1 #max => going down afterwards ;) 
	VOID = 0
	MINIMUM = 1 #min => going up afterwards ;) 

class KeyLevel:
	value = 0
	hits = []
	error = MAX_ERROR_VALUE
	
	def __init__(self,value,hits):
		assert type(hits) == list, "hits must be a list"
		self.value = value
		self.hits = hits 
	
	def __repr__(self):
		return f"KeyLevel(value={self.value},hits={len(self.hits)})"
	
	def draw(self):
		x0 = min(self.hits)-1
		x1 = max(self.hits)+1
		y0 = self.value
		y1 = self.value
		return [x0,x1], [y0,y1]

class LevelActivity: 
	
	key_level = 0 
	candle_location_index = -1
	measurement_candle = None #IMPORTANT! only used for measuring fitness! 
	activity_type = Level.VOID
	level_type = Level.VOID
	
	def __init__(self,activity_type,level_type,key_level,index,candle):
		
		self.candle_location_index = index
		self.measurement_candle = candle
		self.key_level = key_level
		self.activity_type = activity_type
		self.level_type = level_type
	
	def __repr__(self):
		drr = self.direction()
		direction_str = 'Bullish' if drr == Level.BULLISH else 'Bearish' if drr == Level.BEARISH else '?'
		sr_str = 'support' if self.level_type == Level.SUPPORT else 'resistance' if self.level_type == Level.RESISTANCE else '?'
		br_str = 'breakout' if self.activity_type == Level.BREAKOUT else 're-test' if self.activity_type == Level.RETEST else '?'
		return f"{direction_str} {sr_str} {br_str} at value = {self.key_level.value:.4f}, candle {self.candle_location_index} with {len(self.key_level.hits)} hits {self.distance():.4f} distance"
		
	
	def distance(self):
		if self.direction() == Level.BEARISH:
			return self.key_level.value  - self.measurement_candle[csf.high] 
		if self.direction() == Level.BULLISH:
			return self.measurement_candle[csf.low] - self.key_level.value 
		return 0 #not sure what to do here... 
	
	def direction(self):
		if self.level_type == Level.SUPPORT:
			if self.activity_type == Level.BREAKOUT: 
				return Level.BEARISH
			if self.activity_type == Level.RETEST:
				return Level.BULLISH
		if self.level_type == Level.RESISTANCE:
			if self.activity_type == Level.BREAKOUT: 
				return Level.BULLISH
			if self.activity_type == Level.RETEST:
				return Level.BEARISH
		return Level.VOID
	
	#def draw(self) -> ChartView:
	def draw(self): #need to enforce the type somehow
		direct = 1 if self.direction() == Level.BULLISH else -1 if self.direction() == Level.BEARISH else 0
		x,y,xh,yh = self.key_level.draw()
		return x,y,xh,yh,direct
		
	

class ChartPattern(CandleStickPattern): #a chart pattern is a very long candlestick pattern. It uses extreme points.
	#Extreme points are calculated for subclasses - so they can be used for determining where a pattern is. It is up
	#to the subclass for then doing its own analysis for levels/trendlines etc. But extreme points are common so they 
	#are calculated here.
	
	_fractal_size = 2 #size of fractal that has to happen to identify an extreme point
	_local_extreme_window_size = 20#size of window to use when finding extreme points
	
	#set from outside
	memory_window = 100 # duration of candles to look back on for chart analysis
	
	#start the pattern match at candle_stream_index - _pattern_start_index 
	#the rest of the candles are for confirmation 
	pattern_start_index = 4

	
	#precalc in this base class
	_extreme_points = []
	_rolling_range_mean = [] 
	_high_points = []
	_low_points = []
	
	fitness_parameters = {}
	
	def __init__(self,fractal_size=2,extremity_window=20):
		super(ChartPattern,self).__init__()
		self._fractal_size = fractal_size
		self._local_extreme_window_size = extremity_window
		self._load_fitness_parameters()
		
	
	def _load_fitness_parameters(self,filename="charting/tuner/pattern_parameters.json"):
		params = {} #attempt to read param settings from file if there are any
		lfr = ListFileReader()
		json_text = lfr.read_full_text(filename)
		params = json.loads(json_text)
		self.fitness_parameters = params.get(self.__class__.__name__,self.fitness_parameters)
	
	
	#override this function 
	def _determine(self,candle_index,candle_stream): 
		raise NotImplementedError('This method must be overridden')
		#return 0 
	
	def _get_extremes(self,candle_index):
		#return [ep for ep in self._extreme_points if _ep.index < candle_index and _ep.index >= candle_index - self.memory_window]
		end_index = candle_index
		start_index = max(candle_index  - self.memory_window,0)
		extremes = [] 
		for ex in self._extreme_points:
			if ex.index < start_index:
				continue
			elif ex.index > end_index:
				break
			else:
				extremes.append(ex)
		return extremes
	
	def _get_range_points(self,candle_index):
		highs = self._high_points[candle_index -self.memory_window:candle_index+1]
		lows = self._low_points[candle_index -self.memory_window:candle_index+1]
		return highs, lows

	#private functions 
	def __calculate_rolling_mean_range(self,candle_stream):
		ranges = [candle[csf.high] - candle[csf.low] for candle in candle_stream]
		self._rolling_range_mean = self._window_function(np.mean,ranges,self.memory_window)
	
	def __calculate_local_extremes(self,candle_stream):	#local in the sense of a local minimum/maximum not the memory window 
		#find extreme points using the fractal approach
		_extreme_points = []
		for index in range(self._fractal_size,len(candle_stream)-self._fractal_size):
			candle_block = candle_stream[index-self._fractal_size:index+self._fractal_size+1]
			
			if self.__fractal_up(candle_block,self._fractal_size):
				_extreme_points.append(Extremity(ExtremityType.MINIMUM,csf.lowest(candle_block),index)) #index is at the middle of the fractal?
				
			if self.__fractal_down(candle_block,self._fractal_size):
				_extreme_points.append(Extremity(ExtremityType.MAXIMUM,csf.highest(candle_block),index))
				
		#then using a sliding window approach 
		current_min = MAX_ERROR_VALUE
		current_max = -1
		for index in range(len(candle_stream)):#- self._local_extreme_window_size):
			candles = candle_stream[index:index+self._local_extreme_window_size]
			#use a fractal to get rid of annoying sliding window errors 
			fractal = candle_stream[max(0,index-1):min(index+2,len(candle_stream))]  
			
			_high = csf.highest(candles)
			_low = csf.lowest(candles)
			if _high > current_max:
				current_max = _high
			if _low < current_min:
				current_min = _low
			
			candle = candle_stream[index]
			if candle[csf.high] == current_max:# and self.__fractal_down(fractal,1):
				_extreme_points.append(Extremity(ExtremityType.MAXIMUM,current_max,index))
				current_max = -1
			if candle[csf.low] == current_min:# and self.__fractal_up(fractal,1): 
				_extreme_points.append(Extremity(ExtremityType.MINIMUM,current_min,index))
				current_min = MAX_ERROR_VALUE
		
		
		#sort them in their index order so they are easy to iterate through
		self._extreme_points = sorted(set(_extreme_points),key=lambda p: p.index)
	
	def __calculate_all_range_points(self,candle_stream):
		self._high_points = [Extremity(ExtremityType.MAXIMUM,candle_stream[i][csf.high],i) for i in range(len(candle_stream))]
		self._low_points = [Extremity(ExtremityType.MINIMUM,candle_stream[i][csf.low],i) for i in range(len(candle_stream))]
		
	
	#for this candle stream, return a same sized list of locations of bearish and bullish patterns 
	def detect(self,candle_stream):
		self.__calculate_local_extremes(candle_stream)
		self.__calculate_rolling_mean_range(candle_stream)
		self.__calculate_all_range_points(candle_stream)
		
		results = []
		for candle_stream_index in range(len(candle_stream)):
			results.append(self._determine(candle_stream_index,candle_stream))
		
		return results
	
	#override for chart patterns 
	def draw_snapshot(self,candle_stream,candle_stream_index):
		
		base_view = super().draw_snapshot(candle_stream,candle_stream_index)
		
		#build a view of this chart pattern
		this_view = chv.ChartView()
		#this_view.set_candles(candle_stream) #already done in base
		
		extreme_points = self._get_extremes(candle_stream_index)
		xmins = [ep.index for ep in extreme_points if ep.type == ExtremityType.MINIMUM]
		ymins = [ep.value for ep in extreme_points if ep.type == ExtremityType.MINIMUM]
		xmaxs = [ep.index for ep in extreme_points if ep.type == ExtremityType.MAXIMUM]
		ymaxs = [ep.value for ep in extreme_points if ep.type == ExtremityType.MAXIMUM]
		min_points = [chv.Point(x,y) for (x,y) in zip(xmins,ymins)]
		max_points = [chv.Point(x,y) for (x,y) in zip(xmaxs,ymaxs)]
		
		this_view.draw('carets keyinfo lines', chv.Line(candle_stream_index,min(ymins),candle_stream_index,max(ymaxs)) )
		this_view.draw('debug bullish points',min_points)
		this_view.draw('debug bearish points',max_points)
		
		base_view += this_view
		
		return base_view
	
	#could override but would be messy!
	#def draw(self):
	#	xmins = [ep.index for ep in self._extreme_points if ep.type == ExtremityType.MINIMUM]
	#	ymins = [ep.value for ep in self._extreme_points if ep.type == ExtremityType.MINIMUM]
	#	
	#	xmaxs = [ep.index for ep in self._extreme_points if ep.type == ExtremityType.MAXIMUM]
	#	ymaxs = [ep.value for ep in self._extreme_points if ep.type == ExtremityType.MAXIMUM]
	#	
	#	return xmins, ymins, xmaxs, ymaxs
	
	
	@staticmethod
	def __fractal_up(candles,fractal_size=2):
		fractal_length = 2*fractal_size + 1
		if len(candles) >= fractal_length:
			lows = [candle[csf.low] for candle in candles[-fractal_length:]]
			if all(lows[i-1] > lows[i] for i in range(1,fractal_size+1)) and \
				all(lows[i] < lows[i+1] for i in range(fractal_size,2*fractal_size)):
				return True
		return False
		
	@staticmethod
	def __fractal_down(candles,fractal_size=2):
		fractal_length = 2*fractal_size + 1
		if len(candles) >= fractal_length:
			highs = [candle[csf.high] for candle in candles[-fractal_length:]]
			if all(highs[i-1] < highs[i] for i in range(1,fractal_size+1)) and \
				all(highs[i] > highs[i+1] for i in range(fractal_size,2*fractal_size)):
				return True
		return False


#uses a method that uses error values from most recent extreme points instead of clusters. Less effective but faster
#also levels are fixed length away from the current candle
#also gives some key functions for later chart patterns like TriangleBreakout etc 
class SupportAndResistance(ChartPattern):
	
	top_levels = 5# number of support/resistance levels to identify
	
	_memory_window = 100
	
	pattern_start_index = 1
	buffer_gap = 0.5
	
	fitness_keys = ['length','breakout_size','hits','variance','level_error']
	fitness_parameters = {'length':1.0, 'breakout_size':1.0, 'hits':1.0, 'variance':1.0, 'level_error':1.0}
	
	def __init__(self):
		super(SupportAndResistance,self).__init__()
	
	def _closest_level_to_candle(self,levels,candle):
		distances = [csf.body_distance(candle,level) for level in levels]
		return levels[np.argmin(distances)]
	
	def _level_errors(self,levels,points,gap):
		return [(level, self._level_error(level,points,gap)) for level in levels]
		
	
	def _close_points_to_level(self,level,points,gap):
		return [p for p in points if abs(p.value - level) < gap]
	
	#calculate the mean squared error for a list of points and a given level for all points close to the level
	def _level_error(self,level,points,gap):
		close_points = self._close_points_to_level(level,points,gap)
		if not close_points:
			return MAX_ERROR_VALUE
		total = sum((p.value - level)*(p.value - level) for p in close_points)
		return total / len(close_points)
	
	
	def _generate_levels(self,extreme_points,start_level,gap):
		max_distance = 0
		support_points = []
		n_support = 0
		
		buffer = self.buffer_gap * gap
		
		for i,ep in enumerate(extreme_points):
			this_distance =  abs(ep.value - start_level)
			if this_distance > max_distance + buffer: #esure that the next level is actually far away enough - might need to make gap larger
				#if  #check this level is not max error
				if self._level_error(ep.value, extreme_points[i:],gap) < MAX_ERROR_VALUE: #profile this step - might be causing headaches! could be better done in _pattern_fitness
					max_distance = this_distance
					support_points.append(ep)
					n_support += 1 
					if n_support >= self.top_levels:
						break
					
		return [ep.value for ep in support_points]
	
	#def _fit_minimum_level_line(self,points,max_gap):?
	
	def _breakout_fitness_signed(self,level,this_candle):
		
		distance = csf.body_distance(this_candle,level)
		if csf.body_bottom(this_candle) > level:
			#above level - so bullish
			return distance
		if csf.body_top(this_candle) < level:
			#below level - so bearish
			return -distance 
		return 0 #breakout hasn't happened yet 
	
	#higher the fitness the better! 
	def _pattern_fitness(self,levels,this_candle,points,gap,parameter_settings={}):
		
		## variance (normalise?) (div by mem window?)
		## level length 
		## n hits on level
		## breakout distance
		default = 0
		
		#bounds checks 
		if not levels: 
			return default
		
		level = self._closest_level_to_candle(levels,this_candle)
		#level_errors = sorted(self._level_errors(levels,points,gap),key=lambda le:le[1])
		#level = level_errors[0][0]
		breakout = abs(self._breakout_fitness_signed(level,this_candle))
		hits = self._close_points_to_level(level,points,gap)
		level_error = self._level_error(level,points,gap)
		level_length = abs(hits[0].index - hits[-1].index) #might be able to just do hits[0] and hits[-1]
		variance = np.var([ep.index for ep in hits])
		
		#bounds checks 
		if not hits: 
			return default
		
		if level_length == 0:
			return default
		
		if breakout == 0:
			return default
			
		#ratios
		#fitness_keys = ['length','breakout_size','hits','variance','level_error']
		ratios = {}
		ratios['length'] = level_length / self.memory_window
		ratios['breakout_size'] = abs(breakout)
		ratios['hits'] = len(hits) / self.memory_window
		ratios['variance'] = variance / self.memory_window
		ratios['level_error'] = level_error / gap #? 
		
		#final linear combination
		fitness_score = sum([ratios.get(k,0)*parameter_settings.get(k, self.fitness_parameters.get(k,0)) for k in self.fitness_keys])
		
		#normalise the fitness between 0 and 1 so it can be compared to other chart patterns 
		denom = sum([parameter_settings.get(k, self.fitness_parameters.get(k,0)) for k in self.fitness_keys])
		
		assert denom > 0 , 'fitness parameter settings are wrong. they need to all be positive with at least one value'
		
		fitness = fitness_score / denom 
		return fitness
	
	
	#def get_levels(self,candle_stream_index,candle_stream):
	#	extreme_points  = list(reversed(self._get_extremes(candle_stream_index - self.pattern_start_index)))
	#	start_level = csf.median(candle_stream[max(candle_stream_index-self.pattern_start_index,0)])
	#	
	#	max_gap = self._rolling_range_mean[candle_stream_index]
	#	levels = self._generate_levels(extreme_points,start_level,max_gap)
	#	return levels 
	
	def _determine(self,candle_stream_index,candle_stream):
		
		extreme_points  = list(reversed(self._get_extremes(candle_stream_index - self.pattern_start_index)))
		start_level = csf.median(candle_stream[max(candle_stream_index-self.pattern_start_index,0)])
		
		max_gap = self._rolling_range_mean[candle_stream_index]
		levels = self._generate_levels(extreme_points,start_level,max_gap)
		
		this_candle = candle_stream[candle_stream_index]
		
		default = 0 #MAX_ERROR_VALUE
		
		if not levels:
			return default
		
		level = self._closest_level_to_candle(levels,this_candle)
		
		breakout = self._breakout_fitness_signed(level,this_candle)
		sign = breakout / abs(breakout) if breakout != 0 else 0
		
		pattern_fitness = sign*self._pattern_fitness(levels,this_candle,extreme_points,max_gap)
		
		if np.isnan(pattern_fitness): #assert instead?
			pattern_fitness = 0
			
		return pattern_fitness
		
	
	def draw_snapshot(self,candles,candle_stream_index):
		
		#base_instance = ChartPattern() ##horrible! must clean this as it doesn't work as it should
		base_view = super().draw_snapshot(candles,candle_stream_index)
		
		#base_view = base_instance.draw_snapshot(candle_stream_index,candles)
		this_view = chv.ChartView()
				
		extreme_points  = list(reversed(self._get_extremes(candle_stream_index - self.pattern_start_index)))
		start_level = csf.median(candles[max(candle_stream_index-self.pattern_start_index,0)])
		
		max_gap = self._rolling_range_mean[candle_stream_index]
		levels = self._generate_levels(extreme_points,start_level,max_gap)
		
		lines = []
		for level in levels:
			lines.append(chv.Line(candle_stream_index-self.memory_window,level,candle_stream_index,level))
		
		this_view.draw('boundaries neutral lines',lines)
		base_view += this_view
		
		return base_view
	
	





#this class detects if a breakout or a retest has happened at a support/resistance level 
#the support and resistance is calculated from memory window and from extreme points. The activity is then inspected and resulting breakouts/retests are reported
#note: this pattern should only be used as a confirmation as it takes a while to run, but it is powerful!
class SupportAndResistanceAction(ChartPattern):
	
	#perhaps use EMA and then use local minima/maxima from that to find support/resistance?
	
	_confirmation = 2#number of confirming candles after the bounce/intersect
	_closest_actions = 3#number of activities to user per level to measure its fitness 
	_range_mean_divide = 2#used when grouping levels together to get an average group level width
	
	_positions_ago = 50 #only care about stuff that is recent - if a levels most recent activity is further away than this then remove it 
	_determine_distance = 10 #only report -1 or 1 in _determine if the latest activity was within the last _determine_distance steps
	
	#export to base class?
	fitness_keys = ['activity_distance','level_distance','hits','position']
	fitness_parameters = {'level_distance':1.0, 'activity_distance':0.2, 'hits':0.5, 'position':5.0} #we need actions that are recent so we use position:5 to ensure this
	
	top_levels = 3

	def __init__(self,confirmation=2):
		#self._previous_range = previous_range
		self._confirmation = confirmation
		#self.memory_window = self.memory_window + previous_range
	
	#get an approximate range of levels from the extremes for support and resistance 
	def _find_levels(self,extreme_points,candle_stream_index):
		gap = self._rolling_range_mean[candle_stream_index] / self._range_mean_divide
		if not extreme_points:
			return [], 0
		
		if len(extreme_points) < 2:
			return [], 0
		
		extreme_by_values = sorted(extreme_points,key=lambda ep:ep.value)
		
		#keep min and max. pass through grouping levels that are close together - use mean range for that 
		key_level_groups = []
		key_level_groups.append(extreme_by_values[0:1])
		partition_group = [] 
		partition_level = extreme_by_values[1].value
		for level in extreme_by_values[1:-1]: 
			if level.value < partition_level + gap:
				partition_group.append(level)
			else:
				key_level_groups.append(partition_group)
				partition_group = [level]
				partition_level = level.value
		key_level_groups.append(partition_group)
		key_level_groups.append(extreme_by_values[-1:])
		
		key_levels = []
		max_hits = 0
		for group in key_level_groups:
			n = 0
			x = 0
			indexs = []
			multiplier = 0
			for ep in group:
				multiplier = ep.index - candle_stream_index + self.memory_window #the closer to candle_stream_index, the more significant 
				assert multiplier >= 0,"multiplier has became negative somehow?"
				accumulate = ep.value * multiplier 
				indexs.append(ep.index)
			if multiplier:
				new_value = accumulate / multiplier
				key_levels.append(KeyLevel(new_value,indexs))
				n_hits = len(indexs)
				if n_hits > max_hits:
					max_hits = n_hits
		return key_levels, max_hits 
		
	
	def _action_per_level(self,candle_stream,candle_stream_index,level):
		
		gap = self._rolling_range_mean[candle_stream_index] / self._range_mean_divide
		these_indexs = range(max(candle_stream_index - self.memory_window,0),candle_stream_index+1) 
		
		activities = []
		
		for this_index in these_indexs:
			
			this_candle = candle_stream[this_index]
			prev_candle = candle_stream[this_index-1] if this_index > 0 else None
			
			activity_type = Level.BREAKOUT #checking for breakouts 
			level_type = Level.VOID
			if csf.body_bottom(this_candle) < level.value and level.value < csf.body_top(this_candle):
				confirmation_candles = candle_stream[this_index+1:min(candle_stream_index,this_index+self._confirmation+1)]
				
				level_type = Level.RESISTANCE if csf.bullish(this_candle) else Level.SUPPORT if csf.bearish(this_candle) else Level.VOID
				if self._confirm(confirmation_candles,level.value,level_type,activity_type):
					activities.append(LevelActivity(activity_type,level_type,level,this_index,confirmation_candles[-1]))  #activity_type,level_type,key_level,index,candle
					continue
					
			elif prev_candle:
				#but remove the previous activity retest if there is one?
				confirmation_candles = candle_stream[this_index:min(candle_stream_index,this_index+self._confirmation)]
				if csf.body_top(prev_candle) < level.value and level.value < csf.body_bottom(this_candle):
					level_type = Level.RESISTANCE
				if csf.body_bottom(prev_candle) > level.value and level.value > csf.body_top(this_candle):
					level_type = Level.SUPPORT
				if self._confirm(confirmation_candles,level.value,level_type,activity_type):
					activities.append(LevelActivity(activity_type,level_type,level,this_index,confirmation_candles[-1]))
					continue
			
			activity_type = Level.RETEST #now check for retests			
			#test for closeness then to report possible retests - get start and end and report min body distance as the retest candle
			if this_index < self._confirmation+1 or this_index + self._confirmation > candle_stream_index:
				continue #dont bother adding retests if there is no suitable confirmation candles 
				
			confirmation_candles = candle_stream[this_index-self._confirmation:this_index+self._confirmation+1] #get these for testing for fractal with bodys
			resting = any(csf.resting_above(candle,level.value,gap) for candle in confirmation_candles)
			hanging = any(csf.hanging_below(candle,level.value,gap) for candle in confirmation_candles)
			if hanging and not resting:
				level_type = Level.RESISTANCE #this candle may be testing resistance
			if resting and not hanging:
				level_type = Level.SUPPORT #testing support 
			if self._confirm(confirmation_candles,level.value,level_type, activity_type):
				activities.append(LevelActivity(activity_type,level_type,level,this_index,confirmation_candles[-1]))
			
		return activities
	
	def _confirm(self,confirm_candles,level_value,level_type,activity_type):
		
		if not confirm_candles or len(confirm_candles) < 2:
			return False
			
		if activity_type == Level.BREAKOUT:
			if level_type == Level.RESISTANCE: #checking for higher highs and lower lows was not very useful :( 
			#	return csf.higher_lows(confirm_candles[1:]) and csf.lowest_body(confirm_candles) > level_value
				return csf.lowest_body(confirm_candles) > level_value
			if level_type == Level.SUPPORT:
			#	return csf.lower_highs(confirm_candles[1:]) and csf.highest_body(confirm_candles) < level_value
				return csf.highest_body(confirm_candles) < level_value
		
		if activity_type == Level.RETEST:
			#check the middle candle is the most significant? other checks might be useful/needed
			this_candle = confirm_candles[self._confirmation]
			if level_type == Level.RESISTANCE:
				return csf.lowest_body(confirm_candles) == csf.body_bottom(this_candle)
			if level_type == Level.SUPPORT:
				return csf.highest_body(confirm_candles) == csf.body_top(this_candle)
		
		return False
	
	#multi objective function for each level. Use some params for determining if we care about closeness or about hits most etc
	def _level_fitness(self,key_level,actions,candle_stream_index,max_hits,parameter_settings={}):
		if not actions:
			return key_level, [], 0
		
		#first get stuff we will test for
		gap = self._rolling_range_mean[candle_stream_index]
		n_hits = len(key_level.hits) 
		action_timeline = sorted(actions, key=lambda act:act.candle_location_index)
		most_recent_actions = action_timeline[-self._closest_actions:] #as param? 
		level_distance = action_timeline[-1].distance()
		latest_index = most_recent_actions[-1].candle_location_index
		activity_distance = latest_index - most_recent_actions[0].candle_location_index 
		
		#then add boundaries
		#not enough hits 
		if n_hits < 2:
			return key_level, most_recent_actions, 0 
		
		#last activity was too far away 
		if candle_stream_index - latest_index > self._positions_ago:
			return key_level, most_recent_actions, 0 
		
		#not enough actions to determine the level fitness
		if len(most_recent_actions) < self._closest_actions:
			return key_level, most_recent_actions, 0 #we dont have enough activity on this level to determine a good setup
		
		
		
		#then calculate subject to parameter settings 
		#calc ratios for everything we want to include in the fitness score 
		ratios = {}
		ratios['activity_distance'] = activity_distance / self.memory_window 
		ratios['level_distance'] = level_distance / (gap * self._fractal_size) # the _fractal_size was what we used to determine where a local optimum was so it is useful here
		ratios['hits'] = n_hits / max_hits
		ratios['position'] = latest_index / candle_stream_index
		
		fitness_score = sum([ratios.get(k,0)*parameter_settings.get(k, self.fitness_parameters.get(k,0)) for k in self.fitness_keys])
		denom = sum([parameter_settings.get(k, self.fitness_parameters.get(k,0)) for k in self.fitness_keys])
		
		
		return key_level,most_recent_actions,fitness_score/denom
	
	#override - return 1 for buy, -1 for sell and 0 for neutral? perhaps more info should be returned to be collected later
	def _determine(self,candle_stream_index,candle_stream):		
	
		extreme_points = self._get_extremes(candle_stream_index)
		
		key_levels, level_fitness_tab = self._get_key_level_information(candle_stream_index,candle_stream,extreme_points)
		
		if len(level_fitness_tab) < self.top_levels:
			return 0 
		
		for lft_row in level_fitness_tab[:self.top_levels]:
			key_level,actions,fitness = lft_row

			if fitness == 0:
				break  #we have evaluated all levels 
			if candle_stream_index - max(key_level.hits) > self._determine_distance:
				continue
	
			direction = actions[-1].direction()
			return 1 if direction == Level.BULLISH else -1 if direction == Level.BEARISH else 0
		return 0
		#return key_levels, level_fitness_tab
	
	def _get_key_level_information(self,candle_stream_index,candle_stream,extreme_points):
		
		action_levels = {}
		
		key_levels, max_hits = self._find_levels(extreme_points,candle_stream_index)
		for key_level in key_levels:
			action_levels[key_level] = self._action_per_level(candle_stream,candle_stream_index,key_level)
			
		#measure fitness of activities/levels and get top 3?
		
		level_fitness_tab = [self._level_fitness(key_level,action_levels[key_level],candle_stream_index,max_hits) for key_level in action_levels]
		level_fitness_tab = sorted(level_fitness_tab,key=lambda lft: lft[2],reverse=True)[:self.top_levels] #highest first
		
		return key_levels, level_fitness_tab
		
	
	#def draw(self):
	#	pass
	#
	#def draw_snapshot(self):
	#	pass







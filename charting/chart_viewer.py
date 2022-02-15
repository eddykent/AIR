###chart viewer - for displaying nice charts! 
## the idea here is we don't need to depend on plotly - we can just use a plotly interface! :) 
## that way, if we needed to switch to matplotlib we can by just defining a new class here 
from enum import Enum
from collections import namedtuple

from plotly import graph_objects as chart
import json

import re

import pdb


from utils import ListFileReader, DictUpdater, TypeSafe, TypedList
type_safe = TypeSafe()#to turn off, TypeSafe(False)


Point = namedtuple('Point','x y')
Line = namedtuple('Line','x1 y1 x2 y2')
Box = namedtuple('Box','x1 y1 x2 y2')
Circle = namedtuple('Circle','x y r')
Triangle = namedtuple('Triangle','x1 y1 x2 y2 x3 y3')
Quadrilateral = namedtuple('Triangle','x1 y1 x2 y2 x3 y3')
Text = namedtuple('Text','x y string')
Candle = namedtuple('Candle','open high low close datetime')

#
#class DrawingPoint(Point):
#	x = 0
#	y = 0
#	
#	def __init__(self,x,y):
#		self.x = x 
#		self.y = y
#	
#	
#class DrawingLine(Line):
#	
#	x1 = 0
#	y1 = 0
#	x2 = 0
#	y2 = 0
#	
#	def __init__(self,x1,y1,x2,y2):
#		self.x1 = x1
#		self.y1 = y1
#		self.x2 = x2
#		self.y2 = y2
#		
#	@classmethod
#	def from_points(cls,p1,p2):
#		return cls(p1.x,p1.y,p2.x,p2.y)
#		
#	@classmethod
#	def from_trendline(self,trendline):
#		return cls(trendline.x1,trendline.y1,trendline.x2,trendline.y2)
#		
#	@classmethod
#	def from_coords(self,x1,y1,x2,y2):
#		return cls(x1,y1,x2,y2)
#
#class DrawingBox(Box):
#	
#	x1 = 0
#	y1 = 0
#	x2 = 0
#	y2 = 0
#	
#	def __init__(self,x1,y1,x2,y2):
#		self.x1 = x1
#		self.y1 = y1
#		self.x2 = x2
#		self.y2 = y2
#		
#	@classmethod
#	def from_points(cls,p1,p2):
#		return cls(p1.x,p1.y,p2.x,p2.y)
#	
#	@classmethod
#	def from_trendline(cls,trendline):
#		return cls(trendline.x1,trendline.y1,trendline.x2,trendline.y2)
#	
#	@classmethod	
#	def from_coords(cls,x1,y1,x2,y2):
#		return cls(x1,y1,x2,y2)
#	
#	@classmethod
#	def from_center_width_height(cls,x,y,w,h):
#		return cls(x-(0.5*w),y-(0.5*h),x+(0.5*w),y+(0.5*h))
#	
#
#
#class DrawingShape:
#	points = []
#	
#	def __init__(self,points):
#		[type_safe(p,Point) for p in points]
#		self.points = points
#

#a chart pattern view contains all of the information needed to sketch a chart with all the stuff on it. 
#They should be able to be added together for combined views! :) 
class DrawingMode(Enum):
	POINTS = 0
	LINES = 1
	BOXES = 2
	CIRCLES = 3
	SHAPES = 4
	TEXT = 5
	CANDLES = 6
	ALL = 7


class DrawingData:
	
	points = TypedList(None)
	lines = TypedList(None)
	boxes = TypedList(None)
	candles = TypedList(None)
	triangles = TypedList(None)
	quadrilaterals = TypedList(None)
	texts = TypedList(None)
	circles = TypedList(None)
	
	def __init__(self,modes=[DrawingMode.ALL]):
		for mode in modes:
			if mode == DrawingMode.POINTS or mode == DrawingMode.ALL:
				self.points = TypedList(Point)
			if mode == DrawingMode.LINES or mode == DrawingMode.ALL:
				self.lines = TypedList(Line) 
			if mode == DrawingMode.TEXT or mode == DrawingMode.ALL:
				self.texts = TypedList(Text)
			if mode == DrawingMode.BOXES or mode == DrawingMode.ALL:	
				self.boxes = TypedList(Box)
			if mode == DrawingMode.CIRCLES or mode == DrawingMode.ALL:	
				self.boxes = TypedList(Box)
			if mode == DrawingMode.CANDLES or mode == DrawingMode.ALL:
				self.candles = TypedList(Candle)
			if mode == DrawingMode.SHAPES or mode == DrawingMode.ALL:
				self.triangles = TypedList(Triangle)
				self.quadrilaterals = TypedList(Quadrilateral)
	
	def __add__(self,drawing_data):
		self.extend(drawing_data)
		return self
		
	def draw(self,location,value):
		if not location.endswith('s'):
			location = location + 's'
		if type(value) in (list,set): #any other iterator types we might use
			self.__getattribute__(location).extend(value)	
		else:
			self.__getattribute__(location).append(value)
	
	def extend(self,drawing_data):
		type_safe.has_type(drawing_data,DrawingData)
		properties = [property for property in dir(self) if not property.startswith('__') and not callable(property)]
		for prop in properties:
			if not callable(self.__getattribute__(prop)):
				self.__getattribute__(prop).extend(drawing_data.__getattribute__(prop))
	
	def clear(self):
		properties = [property for property in dir(self) if not property.startswith('__') and not callable(property)]
		for prop in properties:
			if not callable(self.__getattribute__(prop)):
				self.__getattribute__(prop).clear()
		
class ChartPatternViewElement:

	#everything in here is a LineDotArea??
	bullish = None 
	bearish = None
	neutral = None
	keyinfo = None
	
	def __init__(self,_modes):
		modes = _modes
		if type(modes) != list:
			modes = [modes]
		self.bullish = DrawingData(modes)
		self.bearish = DrawingData(modes)
		self.neutral = DrawingData(modes)
		self.keyinfo = DrawingData(modes)
		
	def __add__(self,chart_view_pattern_element):
		self.extend(chart_view_pattern_element)
		return self
	
	def draw(self,location,value):
		keys = [ts for ts in location.split(' ') if ts]
		property = keys[0]
		sublocation = ' '.join(keys[1:])
		self.__getattribute__(property).draw(sublocation,value)
	
	def extend(self,chart_view_pattern_element):
		type_safe.has_type(chart_view_pattern_element,ChartPatternViewElement)
		properties = [property for property in dir(self) if not property.startswith('_')]
		for prop in properties:
			if not callable(self.__getattribute__(prop)):
				self.__getattribute__(prop).extend(chart_view_pattern_element.__getattribute__(prop))
		
	def clear(self):
		self.bullish.clear()
		self.bearish.clear()
		self.neutral.clear()
		self.keyinfo.clear()

class ChartPatternView:
	
	def __init__(self):	
		self.candle_sticks = ChartPatternViewElement(DrawingMode.CANDLES)
		self._instrument_name = ''
		
		###public members
		#every list is a ChartPatternViewElement
		#lines to show on the top of the candles - indicating where the price is moving
		#example is trading212 close price 
		self.action_lines = ChartPatternViewElement(DrawingMode.LINES)# route that the price action takes
		
		#background regions that we might want to draw - eg if it is a bullish or bearish region
		self.backgrounds = ChartPatternViewElement(DrawingMode.BOXES)
		
		#shapes we might want to draw that covers the candles showing a chart pattern or a candle stick highlight box?
		self.patterns = ChartPatternViewElement(DrawingMode.ALL)
		
		#support lines and resistance lines - eg at top of a chart pattern or below price action etc 
		self.boundary_lines = ChartPatternViewElement(DrawingMode.LINES) #support,resistance, 
		
		#any lines that we want to use to show that a trend is happening
		self.trend_lines = ChartPatternViewElement(DrawingMode.LINES)
		
		#red and green points or just any points that we might want to add? 
		self.boundary_points = ChartPatternViewElement(DrawingMode.POINTS)
		
		#any trades that were taken on the candlestick data - use to draw the stop loss and take profit regions and POSSIBLY use the data to draw if it is a winning/losing trade?
		self.trade_boxes = ChartPatternViewElement(DrawingMode.BOXES) #unbounded means draw a whole region upwards/downwards! 
		self.bounded_trade_boxes = ChartPatternViewElement(DrawingMode.ALL) #bounded means we got an actual region to draw for these
		self.trade_points = ChartPatternViewElement(DrawingMode.POINTS)#points in which entry and TP or SL were hit 
		
		#a line that shows where we are in a point in time - might be useful for showing previous chart setups (eg if we want to check if a chart pattern happened in the last x candles)
		#can also be used for fundamental bullish/bearish 
		self.caret_lines = ChartPatternViewElement(DrawingMode.LINES)
		self.arrows = ChartPatternViewElement(DrawingMode.LINES)
		
		self.circle_highlights = ChartPatternViewElement(DrawingMode.CIRCLES)
		
		##use for debugging purposes to ensure that the calculation is running smoothly 
		self.debugs = ChartPatternViewElement(DrawingMode.ALL)
	
	
	def __add__(self,_chart_pattern_view):
		self.extend(_chart_pattern_view)
		return self
	
	def extend(self,_chart_pattern_view):
		type_safe.has_type(_chart_pattern_view,ChartPatternView)
		properties = [property for property in dir(self) if not property.startswith('_')]
		
		for prop in properties:
			if not callable(self.__getattribute__(prop)):
				self.__getattribute__(prop).extend(_chart_pattern_view.__getattribute__(prop))
		
		if self._instrument_name is None:
			self._instrument_name = chart_pattern_view._instrument_name
	
	
	#a generic method for drawing any elements into the fields above 
	def draw(self,_location,_value): #this.add('boundary_point bullish point',(1,6))
		location = re.sub('-|>|<|\.',' ',_location)
		location = location.strip()
		keys = [ts for ts in location.split(' ') if ts]
		if not keys:
			raise ValueError('locator needs to be of the form "property style object"')
		property = keys[0]
		sublocation = ' '.join(keys[1:])
		if not property.endswith('s'):
			property = property + 's'
		self.__getattribute__(property).draw(sublocation,_value)
		
	#drtawing specific stuff for ease of use (eg, candles will always be drawn the same - as will results for backgrounds etc) 
	#basically if we can derive the style from the method name we can put it here. (upward trends are bullish, down are bearish etc)
	def draw_candles(self,_candle_stick_data):
		#self.candle_sticks.clear()
		for untyped_candle in _candle_stick_data:
			candle = Candle._make(untyped_candle[:5]) #don't get anything other than the first 5 values
			self.draw('candle_sticks keyinfo candles',candle)
			if candle.open > candle.close:#
				self.draw('candle_sticks bearish candles',candle)
			elif candle.open < candle.close:
				self.draw('candle_sticks bullish candles',candle)
			else:
				self.draw('candle_sticks neutral candles',candle)
		
	def draw_instrument_name(self,_name):
		self._instrument_name = _name
	
	def draw_background_result(self,_results):
		pass
		
	def draw_trendlines(self,_trendlines):
		pass
	
	def get_bounds(self):	
		W = 0
		H = 0
		return W, H #size of the figure	
	
#ChartCanvas - able to hold multiple chart pattern views and controls where they go (eg price action and RSI indicator)	
	








#easy wrapper for all our chart viewing needs! 
class ChartPainter:
	
	fig = None
	
	colour_pallet = {
		#for shapes, we might want to fill them with a nice colour!
		'background':{
			'default':'rgba(200,200,200,0.1)',
			'bullish':'rgba(0,255,0,0.1)',
			'bearish':'rgba(255,0,0,0.2)',
			'keyinfo':'rgba(0,255,255,0.3)'
		},
		'shape':{
			'neutral':{'stroke':'rgba(200,200,200,0.5)','fill':'rgba(0,0,200,0.2)'},
			'bullish':{'stroke':'rgba(0,255,0,0.5)','fill':'rgba(0,255,0,0.2)'},
			'bearish':{'stroke':'rgba(255,0,0,0.5)','fill':'rgba(255,0,0,0.2)'},
			'keyinfo':{'stroke':'rgba(255,255,0,0.1)','fill':'rgba(255,255,0,0.1)'}
		},
		#'caret_line': #for current position of interest (like a y axis)
		#'trend_line': 'down -> bearish and up -> bullish? or stick to support resistance colors?
		#'candle_stick' #obv
		#'level': #support and resistance lines
		#'level_hit_point' #breakouts at support/resistance and also touch points on trend lines 
		#'follow_line' #eg to draw a line over the candles to show the price action for a rising triangle
		#'arrow':? #not sure yet but might be useful for pointing at someting :) 
		'ranks': {
			'rank':['red','blue','yellow','green']
		},
		'debug_point':{'*':'rgba(0,100,255,1)'},
		'debug_line':{'*':'rgba(0,100,255,1)'},
		'debug_area':{'*':'rgba(0,100,255,0.2)'}
		#'sketch': #for anything not defined yet 
	}
	
	def __init__(self): #override?
		pass
	
	def load_colours(self,file_name="default.json"):
		lfr = ListFileReader()
		json_str = lfr.read_full_text(file_name)
		new_colours = json.loads(json_str) #for 
		DictUpdater.update(self.colour_pallet,new_colours)
	
	def paint(self,chart_pattern_view):
		type_safe.has_type(chart_pattern_view, ChartPatternView)
		self._draw_candles(chart_pattern_view.candle_sticks)

		
		
		
		self._draw_caret_lines(chart_pattern_view.caret_lines)
	
	#all methods that paint uses that must be overridden
	def _paint_candles(self, chart_pattern_view):
		raise NotImplementedError('This method must be overridden')
	
	def _paint_caret_lines(self, chart_pattern_view):
		raise NotImplementedError('This method must be overridden')
	
	def _paint_boundary_lines(self, chart_pattern_view):
		raise NotImplementedError('This method must be overridden')
	
	def _paint_trend_lines(self, chart_pattern_view):
		raise NotImplementedError('This method must be overridden')
	
	def show(self):
		raise NotImplementedError('This method must be overridden')
		

class PlotlyChartPainter(ChartPainter):
	
	fig = None
	
	def __init__(self):
		super(ChartPainter,self).__init__()
		self.fig = chart.Figure(data=[])
	
	def _paint_candles(self,candle_sticks):
		all_candles = candle_sticks.keyinfo.candles #plotly nicely takes care of the bullish bearish style for us so give it all the candles 

		candlestick_chart_data = chart.Candlestick(
			#x=x,
			open=[candle.open for candle in all_candles],
			high=[candle.high for candle in all_candles],
			low=[candle.low for candle in all_candles],
			close=[candle.close for candle in all_candles],
			#name= instrument_name if instrument_name else ''
		)
		self.fig.add_trace(candlestick_chart_data)
	
	def _paint_caret_lines(self, chart_pattern_view):
		raise NotImplementedError('This method must be overridden')
	
	def _paint_boundary_lines(self, chart_pattern_view):
		raise NotImplementedError('This method must be overridden')
	
	def _paint_trend_lines(self, chart_pattern_view):
		raise NotImplementedError('This method must be overridden')
	
	
	#override
	def show(self):
		self.fig.show()
	
	
	
	
	
	
	
	
	
	
	
	
	
	
	
	
	
	
	
	
	
	
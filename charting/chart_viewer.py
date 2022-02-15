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
	ALL = 6


class DrawingData:
	
	points = TypedList(None)
	lines = TypedList(None)
	boxes = TypedList(None)
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
			if mode == DrawingMode.SHAPES or mode == DrawingMode.ALL:
				self.triangles = TypedList(Triangle)
				self.quadrilaterals = TypedList(Quadrilateral)
	
	def draw(self,location,value):
		if not location.endswith('s'):
			location = location + 's'
		self.__getattribute__(location).append(value)
	
	def extend(self,drawing_data):
		type_safe.has_type(drawing_data,DrawingData)
		properties = [property for property in dir(self) if not property.startswith('__') and not callable(property)]
		for prop in properties:
			if not callable(self.__getattribute__(prop)):
				self.__getattribute__(prop).extend(drawing_data.__getattribute__(prop))
	
	def __iadd__(self,drawing_data):
		self.extend(drawing_data)
		return self
		
	def __add__(self,drawing_data):
		self.extend(drawing_data)
		return self
		
		
class ChartPatternViewElement:

	#everything in here is a LineDotArea??
	bullish = None 
	bearish = None
	neutral = None
	keyinfo = None
	
	def __init__(self,modes):
		if type(modes) != list:
			modes = [modes]
		self.bullish = DrawingData(modes)
		self.bearish = DrawingData(modes)
		self.neutral = DrawingData(modes)
		self.keyinfo = DrawingData(modes)
		
	
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
	
	def __iadd__(self,chart_view_pattern_element):
		self.extend(chart_view_pattern_element)
		return self
	
	def __add__(self,chart_view_pattern_element):
		self.extend(chart_view_pattern_element)
		return self
		

class ChartPatternView:
	
	
	###private members 
	_candle_stick_data = None
	_instrument_name = ''
	
	
	###public members
	#every list is a ChartPatternViewElement
	#lines to show on the top of the candles - indicating where the price is moving
	#example is trading212 close price 
	action_lines = TypedList(ChartPatternViewElement(DrawingMode.LINES))# route that the price action takes
	
	#background regions that we might want to draw - eg if it is a bullish or bearish region
	backgrounds = ChartPatternViewElement(DrawingMode.BOXES)
	
	#shapes we might want to draw that covers the candles showing a chart pattern or a candle stick highlight box?
	patterns = ChartPatternViewElement(DrawingMode.ALL)
	
	#support lines and resistance lines - eg at top of a chart pattern or below price action etc 
	boundary_lines = ChartPatternViewElement(DrawingMode.LINES) #support,resistance, 
	
	#red and green points or just any points that we might want to add? 
	boundary_points = ChartPatternViewElement(DrawingMode.POINTS)
	
	#any trades that were taken on the candlestick data - use to draw the stop loss and take profit regions and POSSIBLY use the data to draw if it is a winning/losing trade?
	trades = ChartPatternViewElement(DrawingMode.ALL) #unbounded means draw a whole region upwards/downwards! 
	bounded_trades = ChartPatternViewElement(DrawingMode.ALL) #bounded means we got an actual region to draw for these
	
	
	#the actual candles themselves!
	#candle_sticks = ChartPatternViewElement([DrawingMode.LINES,DrawingMode.BOXES])#plotly has this inbuilt but we MIGHT want to display it ourself?
	
	#a line that shows where we are in a point in time - might be useful for showing previous chart setups (eg if we want to check if a chart pattern happened in the last x candles)
	#can also be used for fundamental bullish/bearish 
	caret_lines = ChartPatternViewElement(DrawingMode.LINES)
	
	
	#circle_highlights = ChartPatternViewElement(DrawingMode.CIRCLES)
	
	
	##use for debugging purposes to ensure that the calculation is running smoothly 
	debug = ChartPatternViewElement(DrawingMode.ALL)
	
	
	def __init__(self):
		pass
	
	def _set_candles(self,_candle_stick_data):
		self._candle_stick_data = _candle_stick_data
		##todo: populate candle_sticks  --- if needed?
		
	def _set_instrument_name(self,name):
		self._instrument_name = name
	
	def draw(self,location,value): #this.add('boundary_point bullish point',(1,6))
		location = re.sub('-|>|<',' ',location)
		location = location.strip()
		keys = [ts for ts in location.split(' ') if ts]
		if not keys:
			raise ValueError('locator needs to be of the form "property style object"')
		property = keys[0]
		sublocation = ' '.join(keys[1:])
		if not property.endswith('s'):
			property = property + 's'
		self.__getattribute__(property).draw(sublocation,value)
		
	
	def extend(self,chart_pattern_view):
		type_safe.has_type(chart_pattern_view,ChartPatternView)
		properties = [property for property in dir(self) if not property.startswith('_')]
		
		for prop in properties:
			if not callable(self.__getattribute__(prop)):
				self.__getattribute__(prop).extend(chart_pattern_view.__getattribute__(prop))
	
	def __iadd__(self,chart_pattern_view):
		self.extend(chart_pattern_view)
		return self
			
	def __add__(self,chart_pattern_view):
		self.extend(chart_pattern_view)
		return self
		
	def get_bounds(self):	
		W = 0
		H = 0
		return W, H #size of the figure
	
	
	

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
		self.draw_candles(chart_pattern_view._candle_stick_data)
	
	#helpers
	def draw_candles(self):
		raise NotImplementedError('This method must be overridden')
		
	def show(self):
		fig.show()
		

class PlotlyChartPainter(ChartPainter):
	
	fig = None
	
	def __init__(self):
		super(ChartPainter,self).__init__()
		self.fig = chart.Figure(data=[])
	
	def draw_candles(self,candles):
		candlestick_chart_data = chart.Candlestick(
			#x=x,
			open=[candle[csf.open] for candle in candles],
			high=[candle[csf.high] for candle in candles],
			low=[candle[csf.low] for candle in candles],
			close=[candle[csf.close] for candle in candles],
			name=pair
		)
		fig.add_trace(candlestick_chart_data)
	
	#override
	def show(self):
		fig.show()
	
	
	
	
	
	
	
	
	
	
	
	
	
	
	
	
	
	
	
	
	
	
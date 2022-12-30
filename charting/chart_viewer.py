###chart viewer - for displaying nice charts! 
## the idea here is we don't need to depend on plotly - we can just use a plotly interface! :) 
## that way, if we needed to switch to matplotlib we can by just defining a new class here 
## Also all styling etc is done here so we can just dump lines/points etc into a view object 
## and everything will be painted from a painting tool in this file 
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
Quadrilateral = namedtuple('Quadrilateral','x1 y1 x2 y2 x3 y3 x4 y4') #everything can be built from triangles but quadrilaterals allow for trapeziums in curves for convenience 
Text = namedtuple('Text','x y string')
Candle = namedtuple('Candle','open high low close datetime')

 
class DrawingMode(Enum):
	POINTS = 0
	LINES = 1
	BOXES = 2
	CIRCLES = 3
	SHAPES = 4
	TEXT = 5
	CANDLES = 6
	PATHS = 7
	ALL = 8


class DrawingData:
	
	points = TypedList(None)
	lines = TypedList(None)
	boxes = TypedList(None)
	candles = TypedList(None)
	triangles = TypedList(None)
	quadrilaterals = TypedList(None)
	texts = TypedList(None)
	circles = TypedList(None)
	paths = TypedList(None)
	
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
			if mode == DrawingMode.PATHS or mode == DrawingMode.ALL:
				self.paths = TypedList(Point)
			if mode == DrawingMode.SHAPES or mode == DrawingMode.ALL:
				self.triangles = TypedList(Triangle)
				self.quadrilaterals = TypedList(Quadrilateral)
	
	def __add__(self,drawing_data):
		self.extend(drawing_data)
		return self
	
	def __bool__(self):
		drawing_object_types = self.get_drawing_object_types()
		return any([getattr(self,drawing_object_type) for drawing_object_type in drawing_object_types])
		
	def draw(self,location,value): #add reflexive mappings here? 
		if not location.endswith('s'):
			location = location + 's'
		if type(value) in (list,set): #any other iterator types we might use
			getattr(self,location).extend(value)	
		else:
			getattr(self,location).append(value)
	
	def get_drawing_object_types(self):
		drawing_object_types = [drawing_object_type for drawing_object_type in dir(self) if not drawing_object_type.startswith('__')]
		return [drawing_object_type for drawing_object_type in drawing_object_types if not callable(self.__getattribute__(drawing_object_type))]


	def extend(self,drawing_data):
		type_safe.has_type(drawing_data,DrawingData)
		drawing_object_types = self.get_drawing_object_types()
		for drawing_object_type in drawing_object_types:
			getattr(self,drawing_object_type).extend(getattr(drawing_data,drawing_object_type))
				
	def clear(self):
		drawing_object_types = self.get_drawing_object_types()
		for drawing_object_type in drawing_object_types:
			getattr(self,drawing_object_type).clear()
	
	def get_drawing_objects(self,drawing_object_type):
		return getattr(self,drawing_object_type)
	
	
class ChartLayer:

	#styles that are drawn on this layer
	neutral = None
	bullish = None 
	bearish = None
	keyinfo = None
	
	def __init__(self,_modes):
		modes = _modes
		if type(modes) != list:
			modes = [modes]
			
		self.neutral = DrawingData(modes)
		self.bullish = DrawingData(modes)
		self.bearish = DrawingData(modes)
		self.keyinfo = DrawingData(modes)
		
	def __add__(self,chart_layer):
		self.extend(chart_layer)
		return self
	
	def __bool__(self):
		styles = self.get_styles()
		return any(getattr(self,style) for style in styles)
	
	def draw(self,location,value):
		keys = [ts for ts in location.split(' ') if ts]
		property = keys[0]
		sublocation = ' '.join(keys[1:])
		getattr(self,property).draw(sublocation,value)
	
	def extend(self,chart_layer):
		type_safe.has_type(chart_layer,ChartLayer)
		styles = self.get_styles()
		for style in styles:
			getattr(self,style).extend(getattr(chart_layer,style))
		
	def clear(self):
		self.bullish.clear()
		self.bearish.clear()
		self.neutral.clear()
		self.keyinfo.clear()
	
	def get_styles(self):
		styles = [style for style in vars(self) if not style.startswith('_')]
		return [style for style in styles if not callable(self.__getattribute__(style))]
	
	def get_drawing_data(self,style):
		styles = self.get_styles()
		if style not in styles:
			raise NameError(f"The style of {style} was not found on this layer.")
		return getattr(self,style)

class ChartView:
	
	_title = ''
	
	#everything that is put onto this object is a layer unless it starts with _
	#the layers will draw in the order in which they are found in here
	def __init__(self,title=''):	
		self._title = title
		self.define_layers()
	
	def __add__(self,_chart_view):
		self.extend(_chart_view)
		return self
	
	def extend(self,_chart_view):
		type_safe.has_type(_chart_view,ChartView)
		
		for layer in self.get_layers():
			getattr(self,layer).extend(getattr(_chart_view,layer))
		
		if not self._title:
			self._title = _chart_view._title
	
	#override if different layers should be used
	def define_layers(self):
		#background regions that we might want to draw - eg if it is a bullish or bearish region - borderless
		self.backgrounds = ChartLayer(DrawingMode.BOXES)
		
		#support lines and resistance lines - eg at top of a chart pattern or below price action etc 
		self.boundaries = ChartLayer([DrawingMode.LINES,DrawingMode.POINTS]) #support,resistance, 
		
		#faint background lines 
		self.faint_traces = ChartLayer(DrawingMode.PATHS)
		
		#shapes we might want to draw that covers the candles showing a chart pattern eg a candle stick highlight box or a wedge
		self.candle_boxes = ChartLayer(DrawingMode.BOXES) #note: bordered 
		
		#wedge patterns etc 
		self.patterns = ChartLayer(DrawingMode.ALL)
		
		#any trades that were taken on the candlestick data - use to draw the stop loss and take profit regions and POSSIBLY use the data to draw if it is a winning/losing trade?
		self.trades = ChartLayer([DrawingMode.BOXES,DrawingMode.POINTS,DrawingMode.LINES]) 
		
		#the candle sticks themselves that we will draw
		self.candle_sticks = ChartLayer(DrawingMode.CANDLES)
		
		#lines to show on the top of the candles - indicating where the price is moving
		#example is trading212 close price 
		self.price_actions = ChartLayer(DrawingMode.PATHS)# route that the price action takes
		
		#circles or shapes that highlight a region for us 
		self.highlights = ChartLayer([DrawingMode.CIRCLES,DrawingMode.SHAPES,DrawingMode.BOXES])
		
		#any lines that we want to use to show that a trend is happening
		self.trends = ChartLayer(DrawingMode.LINES)
		
		#can also be used for fundamental bullish/bearish thin lines but should mainly be for "point in time" stuff
		self.carets = ChartLayer([DrawingMode.LINES,DrawingMode.PATHS])
				
		#anything that needs pointing to!
		self.arrows = ChartLayer(DrawingMode.LINES)
		
		#pieces of text that can go anywhere
		self.labels = ChartLayer(DrawingMode.TEXT)
		
		##use for debugging purposes to ensure that the calculation is running smoothly 
		self.debugs = ChartLayer(DrawingMode.ALL)
	
	def get_layers(self):
		layers = [layer for layer in vars(self) if not layer.startswith('_')]
		return [layer for layer in layers if not callable(self.__getattribute__(layer))]
				
				
	#a generic method for drawing any elements into the fields above 
	def draw(self,_location,_value): #this.add('boundary_point bullish point',(1,6))
		location = re.sub('-|>|<|\.',' ',_location)
		location = location.strip()
		keys = [ts for ts in location.split(' ') if ts]
		if not keys:
			raise ValueError('locator needs to be of the form "layer style object"')
		layer = keys[0]
		sublocator = ' '.join(keys[1:])
		if not layer.endswith('s'):
			layer = layer + 's'
		self.__getattribute__(layer).draw(sublocator,_value)
		
	#drawing specific stuff for ease of use (eg, candles will always be drawn the same - as will results for backgrounds etc) 
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
	
	#perhaps extend to shaded?
	def draw_background_results(self,_results): # should be list of numbers - might want to check?
		min_x, min_y, max_x, max_y = self.calculate_bounds()
		bearbox = []
		bullbox = []
		for i,r in enumerate(_results):
			if r < 0:
				bearbox.append(Box(i-1,min_y,i,max_y))
			if r > 0:
				bullbox.append(Box(i-1,min_y,i,max_y))
		self.draw('backgrounds bullish boxes',bullbox)
		self.draw('backgrounds bearish boxes',bearbox)
			
	def draw_fundamental_result(self,fundamentals):
		min_x, min_y, max_x, max_y = self.calculate_bounds()
		bearline = []
		bullline = []
		for i,r in enumerate(_results):
			if r < 0:
				bearbox.append(Line(i,min_y,i,max_y))
			if r > 0:
				bullbox.append(line(i,min_y,i,max_y))
		self.draw('carets bullish lines',bullline)
		self.draw('carets bearish lines',bearline)
		
	def draw_time_caret(self,snapshot_index):
		min_x, min_y, max_x, max_y = self.calculate_bounds()
		self.draw('carets neutral lines',Line(max_x,max_y,max_x,min_y))
		
	def draw_trendlines(self,_trendlines):
		#self.draw('trends keyinfo lines',[Line._make(line[:4]) for line in _trendlines])
		if type(_trendlines) in (list,set):
			increasing_lines = []
			decreasing_lines = []
			horizontal_lines = []
			for line in _trendlines:
				drawing_line = Line._make(line[:4])
				if line.x1 < line.x2:
					if line.y1 < line.y2:
						increasing_lines.append(drawing_line)
					elif line.y1 > line.y2:
						decreasing_lines.append(drawing_line)
					else:
						horizontal_lines.append(drawing_line)
				if line.x1 > line.x2:
					if line.y1 < line.y2:
						decreasing_lines.append(drawing_line)
					elif line.y1 > line.y2:
						increasing_lines.append(drawing_line)
					else:
						horizontal_lines.append(drawing_line)
				#don't add points or vertical lines (A trend can never be vertical)
						
			self.draw('trends bullish lines',increasing_lines)
			self.draw('trends bearish lines',decreasing_lines)
			self.draw('trends neutral lines',horizontal_lines)
	
	#def draw_candle_pattern(self,candle_stick_pattern,candles,index):
	#	pass #handle highlighting a candle stick pattern if it is bullish/bearish
	#
	#def draw_chart_pattern(self,chart_pattern,candles,index):  #use draw_snapshot methods
	#	pass #?? 
	
	#calculate the bounds from the candles. If they don't exist may have to calculate from elsewhere? 
	def calculate_bounds(self):	
		min_x = 0
		min_y = 0
		max_x = 0
		max_y = 0
		
		if self.candle_sticks.keyinfo.candles:
			min_x = 0 
			min_y = min([c.low for c in self.candle_sticks.keyinfo.candles])
			max_x = len(self.candle_sticks.keyinfo.candles)
			max_y = max([c.high for c in self.candle_sticks.keyinfo.candles])
		
		return min_x,min_y,max_x,max_y
	
#ChartCanvas - able to hold multiple chart pattern views and controls where they go (eg price action and RSI indicator)	
	




#easy wrapper for all our chart viewing needs! 
class ChartPainter:
	
	fig = None
	activated = {} #all layers are activated by default. If deactivate(layer) is called then this dict should have a False in it for that layer as the key
	config = {} #any configuration options stored in the class that are passed to fig
	
	colour_palette = {
		#for shapes, we might want to fill them with a nice colour!
		'backgrounds':{
			'neutral':{'fill':'rgba(200,200,200,0.1)'},
			'bullish':{'fill':'rgba(0,255,0,0.2)'},
			'bearish':{'fill':'rgba(255,0,0,0.2)'},
			'keyinfo':{'fill':'rgba(0,255,255,0.3)'}
		},
		'faint_traces':{
			'neutral':{'stroke':'rgba(200,200,200,1)'},
			'bullish':{'stroke':'rgba(0,255,0,1)'},
			'bearish':{'stroke':'rgba(255,0,0,1)'},
			'keyinfo':{'stroke':'rgba(0,255,255,1)'}
		},
		'boundaries':{
			'neutral':{'stroke':'rgba(200,200,200,1)'},
			'bullish':{'stroke':'rgba(0,255,0,1)'},
			'bearish':{'stroke':'rgba(255,0,0,1)'},
			'keyinfo':{'stroke':'rgba(0,255,255,1)'}
		},
		'candle_sticks':{
			'bullish':{'stroke':'rgba(20,150,255,0.9)'	,'fill':'rgba(0,100,255,0.9)'},
			'bearish':{'stroke':'rgba(255,20,50,0.9)'	,'fill':'rgba(255,70,70,0.9)'},
			'neutral':{'stroke':'rgba(0,100,255,1)'		,'fill':'rgba(0,100,255,0.3)'},
			'keyinfo':{'stroke':'rgba(255,255,0,1)'		,'fill':'rgba(255,255,0,0.3)'}
		},
		'candle_boxes':{
			'neutral':{'fill':'rgba(200,200,200,0.1)','stroke':'rgba(200,200,200,1)'},
			'bullish':{'fill':'rgba(0,255,0,0.2)','stroke':'rgba(0,255,0,1)'},
			'bearish':{'fill':'rgba(255,0,0,0.2)','stroke':'rgba(255,0,0,1)'},
			'keyinfo':{'fill':'rgba(0,255,255,0.3)','stroke':'rgba(0,255,255,1)'}
		},
		'trends':{
			'neutral':{'stroke':'rgb(200,200,200)'},
			'bullish':{'stroke':'rgb(0,255,0)'},
			'bearish':{'stroke':'rgb(255,0,0)'},
			'keyinfo':{'stroke':'rgb(0,255,255)'}
		},
		'patterns':{
			'neutral':{'stroke':'rgba(150,150,150,1.0)','fill':'rgba(0,0,200,0.2)'},
			'bullish':{'stroke':'rgba(0,255,0,0.9)','fill':'rgba(0,255,0,0.2)'},
			'bearish':{'stroke':'rgba(255,0,0,0.9)','fill':'rgba(255,0,0,0.2)'},
			'keyinfo':{'stroke':'rgba(255,255,0,0.5)','fill':'rgba(255,255,0,0.1)'}
		},
		'price_actions':{
			'neutral':{'stroke':'rgb(0,0,255)'},
			'bullish':{'stroke':'rgb(0,255,0)'},
			'bearish':{'stroke':'rgb(255,0,0)'},
			'keyinfo':{'stroke':'rgb(0,255,255)'}
		},
		'carets':{
			'neutral':{'stroke':'rgb(100,100,255)'},
			'bullish':{'stroke':'rgb(0,255,0)'},
			'bearish':{'stroke':'rgb(255,0,0)'},
			'keyinfo':{'stroke':'rgb(0,255,255)'}
		},
		'trades':{
			'neutral':{'stroke':'rgba(0,0,200,1.0)','fill':'rgba(0,0,200,0.2)'},
			'bullish':{'stroke':'rgba(0,255,0,0.9)','fill':'rgba(0,255,0,0.2)'},
			'bearish':{'stroke':'rgba(255,0,0,0.9)','fill':'rgba(255,0,0,0.2)'},
			'keyinfo':{'stroke':'rgba(0,100,255,0.5)','fill':'rgba(0,100,255,0.1)'}
		},
		#'level': #support and resistance lines
		#'level_hit_point' #breakouts at support/resistance and also touch points on trend lines 
		#'follow_line' #eg to draw a line over the candles to show the price action for a rising triangle
		#'arrow':? #not sure yet but might be useful for pointing at someting :) 
		
		'debugs':{
			'bullish':{'stroke':'rgba(0,255,255,1)','fill':'rgba(0,255,255,0.4)'},
			'bearish':{'stroke':'rgba(255,0,255,1)','fill':'rgba(255,0,255,0.4)'},
			'neutral':{'stroke':'rgba(0,0,255,1)','fill':'rgba(0,0,255,0.4)'},
			'keyinfo':{'stroke':'rgba(255,255,255,1)','fill':'rgba(255,255,255,0.4)'}
		}
		#'sketch': #for anything not defined yet 
	}
	
	def __init__(self): #override?
		self.fig = None
		self.activated = {}
		self.colour_palette = {} 
		self.load_colours()
		self.options = {}
	
	def load_colours(self,file_name="default"):
		if file_name == 'default':
			self.colour_palette = ChartPainter.colour_palette
		lfr = ListFileReader()
		json_str = lfr.read_full_text(file_name)
		new_colours = json.loads(json_str) #for 
		DictUpdater.update(self.colour_pallet,new_colours)
	
	def activate(layer_name,yn=True):
		self.activated[layer_name] = yn
	
	def paint(self,chart_view):
		type_safe.has_type(chart_view, ChartView)
		#ordering = z-index
		layers = chart_view.get_layers()
		
		for layer in layers:
			if not self.activated.get(layer,True):
				continue
			layer_content = chart_view.__getattribute__(layer)
			if not layer_content:
				continue
			layer_painter_name = '_paint_'+layer
			if hasattr(self,layer_painter_name):
				layer_painter = getattr(self,layer_painter_name)
				if not callable(layer_painter):
					raise TypeError(f'Method {layer_painter_name} in {self.__class__.__name__} is not callable')
				layer_painter(layer_content)
			else:
				pdb.set_trace()
				raise NotImplementedError(f'Method {layer_painter_name} must be defined in {self.__class__.__name__}')
	
	def get_colour(self,layer_name,style,default='#666666'):
		return self.colour_palette.get(layer_name,{}).get(style,{'stroke':default,'fill':default})
	
	def show(self):
		raise NotImplementedError('This method must be overridden')
		

class PlotlyChartPainter(ChartPainter):
	
	fig = None
	fig_data = [] 
	_drawing_object_mode = {
		'points':'markers',
		'lines':'lines',
		'boxes':'none'
	}
	
	def __init__(self):
		super(ChartPainter,self).__init__()
		self.fig_data = []
		self.fig = chart.Figure(data=self.fig_data)
	
	def __paint_plotly_points(self,chart_layer,layer_name,thickness=1):
		styles = chart_layer.get_styles()
		for style in styles:
			drawing_data = chart_layer.get_drawing_data(style)
			colour = self.get_colour(layer_name,style)
			if drawing_data.points:
				xs = []
				ys = []
				for point in drawing_data.points:
					xs += [point.x,None]
					ys += [point.y,None]
				points = chart.Scatter(
					x=xs,
					y=ys,
					mode='markers'
				)
				#colour = self.get_color(layer_name,style)
				points.marker.color = colour['stroke']
				points.marker.size = thickness
				self.fig.add_trace(points)
				
				self.fig_data.append(self.fig.data[-1]) #add last thing that has been figged to the fig data 
				
	def __paint_plotly_paths(self,chart_layer,layer_name,thickness=1):
		styles = chart_layer.get_styles()
		for style in styles:
			drawing_data = chart_layer.get_drawing_data(style)
			colour = self.get_colour(layer_name,style)
			if drawing_data.paths:
				xs = []
				ys = []
				for point in drawing_data.paths: 
					xs += [point.x]
					ys += [point.y]
				path = chart.Scatter(
					x=xs,
					y=ys,
					mode='lines'
				)
				#colour = self.get_color(layer_name,style)
				path.line.color = colour['stroke']
				path.line.width = thickness
				self.fig.add_trace(path)
				
				self.fig_data.append(self.fig.data[-1]) #add last thing that has been figged to the fig data 
	
	def __paint_plotly_lines(self,chart_layer,layer_name,thickness=1):
		styles = chart_layer.get_styles()
		for style in styles:
			drawing_data = chart_layer.get_drawing_data(style)
			colour = self.get_colour(layer_name,style)
			if drawing_data.lines:
				xs = []
				ys = []
				for line in drawing_data.lines:
					xs += [line.x1,line.x2,None]
					ys += [line.y1,line.y2,None]
				lines = chart.Scatter(
					x=xs,
					y=ys,
					mode='lines'
				)
				lines.line.color = colour['stroke']
				lines.line.width = thickness
				self.fig.add_trace(lines)
				
				self.fig_data.append(self.fig.data[-1]) #add last thing that has been figged to the fig data 
		
	def __paint_plotly_boxes(self,chart_layer,layer_name,border_width=0):
		styles = chart_layer.get_styles()
		
		for style in styles:
			drawing_data = chart_layer.get_drawing_data(style)
			
			colour = self.get_colour(layer_name,style) 
			if drawing_data.boxes:
				xs = []
				ys = []
				for box in drawing_data.boxes:
					xs += [box.x1,box.x2,box.x2,box.x1,box.x1,None]
					ys += [box.y1,box.y1,box.y2,box.y2,box.y1,None]
				boxes = chart.Scatter(
					x=xs,
					y=ys,
					fill='toself',
					mode='lines'
				)
				boxes.line.width = border_width
				if border_width: 
					boxes.line.color = colour['stroke']
				boxes.fillcolor = colour['fill']
				self.fig.add_trace(boxes)
				
				self.fig_data.append(self.fig.data[-1]) #add last thing that has been figged to the fig data 


	def _paint_candle_sticks(self,chart_layer):
		all_candles = chart_layer.keyinfo.candles #plotly nicely takes care of the bullish bearish style for us so give it all the candles 
		
		candlestick_chart_data = chart.Candlestick(
			#x=x,
			open=[candle.open for candle in all_candles],
			high=[candle.high for candle in all_candles],
			low=[candle.low for candle in all_candles],
			close=[candle.close for candle in all_candles],
			#name= instrument_name if instrument_name else ''
		)
		
		bearish_colour = self.get_colour('candle_sticks','bearish')
		bullish_colour = self.get_colour('candle_sticks','bullish')
		neutral_colour = self.get_colour('candle_sticks','neutral')
		#add colour scheme here
		candlestick_chart_data.increasing.fillcolor = bullish_colour['fill'] #'rgba(0,100,255,0.9)'
		candlestick_chart_data.increasing.line.color = bullish_colour['stroke'] #'rgba(20,150,255,0.9)'
		candlestick_chart_data.decreasing.fillcolor = bearish_colour['fill'] #'rgba(255,70,70,0.9)'
		candlestick_chart_data.decreasing.line.color = bearish_colour['stroke'] #'rgba(255,20,50,0.9)'
		
		self.fig.add_trace(candlestick_chart_data)
		self.fig_data.append(self.fig.data[-1]) #add last thing that has been figged to the fig data 
	
	def _paint_backgrounds(self,chart_layer):
		self.__paint_plotly_boxes(chart_layer,'backgrounds',0)
	
	def _paint_carets(self, chart_layer):
		self.__paint_plotly_lines(chart_layer,'carets',1) 
		#self.__paint_plotly_paths(chart_layer,'carets',1)
		
	def _paint_faint_traces(self, chart_layer):
		self.__paint_plotly_paths(chart_layer,'faint_traces',1)
			
	def _paint_boundaries(self, chart_layer):
		self.__paint_plotly_lines(chart_layer,'boundaries',3)
		self.__paint_plotly_points(chart_layer,'boundaries',3)
	
	def _paint_trends(self, chart_layer):
		self.__paint_plotly_lines(chart_layer,'trends',2)
	
	def _paint_trades(self, chart_layer):
		self.__paint_plotly_boxes(chart_layer,'trades',0) #no border
		self.__paint_plotly_lines(chart_layer,'trades',1)
		self.__paint_plotly_points(chart_layer,'trades',6)
		
	
	def _paint_debugs(self,chart_layer):
		self.__paint_plotly_lines(chart_layer,'debugs',3)
		self.__paint_plotly_boxes(chart_layer,'debugs',1)
		self.__paint_plotly_points(chart_layer,'debugs',7)
		
	def _paint_patterns(self,chart_layer):
		self.__paint_plotly_points(chart_layer,'patterns',15)
		self.__paint_plotly_paths(chart_layer,'patterns',4)
	
	def _paint_candle_boxes(self,chart_layer):
		self.__paint_plotly_boxes(chart_layer,'candle_boxes',2)
		
	def _paint_price_actions(self,chart_layer):
		self.__paint_plotly_paths(chart_layer,'price_actions',2)
	
	def __get_config(self):
		config = {}
		config.update({'scrollZoom': True}) #window zoom
		config.update(self.config) #all passed in config
		return config
		
	#override
	def show(self):
		self.fig.data = self.fig_data #force the data to be drawn in the right order - makes no difference... 
		self.fig.update_yaxes(fixedrange=False,autorange=True)
		self.fig.show(config=self.__get_config())
	
	
	
	
	
	
	
	
	
	
	
	
	
	
	
	
	
	
	
	
	
	
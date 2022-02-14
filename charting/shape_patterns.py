

import numpy as np
import datetime

from enum import Enum
from collections import namedtuple

import charting.candle_stick_functions as csf
from charting.candle_stick_pattern import CandleStickPattern
from charting.chart_pattern import *

#import charting.trend_line_functions as tlf
#from charting.trend_line_functions import TrendLine



#not sure how to do this yet - thinking get the levels and then number them then see if the price action hits them in the correct order (or similar) 
class ShapePattern(SupportAndResistance):
	
	level_pattern  = [2,0,1,0,2]#example
	
	
	pass



class TopAndBottom(ShapePattern):
	pass

class HeadAndShoulders(ShapePattern):
	pass

class TeacupHandle(ShapePattern):
	pass


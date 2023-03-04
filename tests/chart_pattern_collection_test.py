




import datetime 
import numpy as np


import pdb


from configuration import Configuration

from data.tools.cursor import Database, DataComposer
from data.base.candles import CandleDataTool


from utils import ListFileReader
from charting.chart_pattern import SupportAndResistance, PivotPoints, ChartPattern, XtremeWindowSettings
from charting.match_pattern import MatchPatternInstance, MatchPattern
from charting.trend_pattern import *
from charting.harmonic_pattern import *
from charting.shape_pattern import HeadAndShoulders, DoubleExtreme
import charting.chart_viewer as chv

from setups.collected_setups import *
from setups.setup_tools import PipStop

import debugging.functs as debug


lfr = ListFileReader()
currencies = lfr.read('fx_pairs/currencies.txt')
fx_pairs = lfr.read('fx_pairs/fx_mains.txt')

the_date = datetime.datetime(2022,5,20,12,0)

datatool = CandleDataTool() 
datatool.start_date = datetime.datetime(2022,5,4)
datatool.end_date = datetime.datetime(2022,9,4)
datatool.instruments = lfr.read('fx_pairs/fx_mains.txt')
datatool.volumes = True
debug.stopwatch('fetch candles')
datatool.read_data_from_currencies(currencies)
tsd = datatool.get_trade_signalling_data()
debug.stopwatch('fetch candles')

#chart_pattern = Butterfly()  #Gartley, Crab, DeepCrab, Bat, todo: Cypher
#chart_pattern = Bat()
cc = ChartCollection() 
cc = Harmony() 
#cc = Trends()
#cc = Shapes() 
#cc.chart_patterns = [Bat,Crab,Butterfly,Gartley,DeepCrab]
#cc.settings = []
#for o in [1,2,3,4,5,6,7,8]:
#	xws = XtremeWindowSettings() 
#	
#	xws.order = o 
#	xws.required_candles = 200
#	cc.settings.append(xws)

#result = cc.detect(tsd)
signals = cc.get_setups(tsd)
pdb.set_trace()




























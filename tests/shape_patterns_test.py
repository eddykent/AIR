

##this is a test file for chart patterns. In particular, this one was used to test the support and resistance pattern 
##This file also has plenty of material that can be used when creating a chart viewer 

import numpy 
import psycopg2
import datetime

from sklearn import manifold
from plotly import graph_objects as chart

import pdb
import time


assert __name__ != "__main__", "You must run tests through the run_test.py hoister"

from charting import candle_stick_functions as csf
from utils import Configuration, ListFileReader
from charting.chart_pattern import * #grab all patterns 
from charting.trending_pattern import * #grab all advanced patterns to
from charting.candle_stick_pattern import *
from charting.shape_pattern import *
from charting.chart_viewer import PlotlyChartPainter 


config = Configuration()
con = psycopg2.connect(config.database_connection_string())
cur = con.cursor()

lfr = ListFileReader()
currencies = lfr.read('fx_pairs/currencies.txt')
fx_pairs = lfr.read('fx_pairs/fx_mains.txt')
sorted(fx_pairs)

the_date = datetime.datetime(2022,2,23,10,0)

parameters = {
	'chart_resolution':60,
	'the_date':the_date,
	'hour':the_date.hour,
	'days_back':50,
	'currencies':currencies,
	'candle_offset':0
}

query = ''
with open('queries/candle_stick_selector.sql','r') as f:
	query = f.read()

cur.execute(query,parameters)
database_response = cur.fetchall()

#OurChartPattern = TrendingPattern
#OurChartPattern = TriangleBreakout
#OurChartPattern = FallingTriangleBreakout
#OurChartPattern = RisingTriangleBreakout
#OurChartPattern = WedgeBreakout  #2
#OurChartPattern = ApproximateChannelBreakout
#OurChartPattern = SupportAndResistanceAction
#OurChartPattern = SupportAndResistance
#OurChartPattern = ParallelChannelBreakout


#OurChartPattern = DoubleTopAndBottom
#OurChartPattern = TripleTopAndBottom
OurChartPattern = HeadAndShoulders



chart_pattern = OurChartPattern()

#chart_pattern = TriangleBreakout()

#chart_pattern.bounce_size = 2
#chart_pattern.memory_window = 250
pair = 'GBP/USD'
candle_stream = chart_pattern.to_candles(database_response,pair)


chart_pattern.setup(candle_stream)

t0 = time.time()
chart_result = chart_pattern.detect(candle_stream) 
t1 = time.time()

#OurCandlePattern = PinBar
#OurCandlePattern = Engulfing
#OurCandlePattern = SoldiersAndCrows
OurCandlePattern = MorningEveningStars
#OurCandlePattern = Harami
#OurCandlePattern = ThreeLineStrikes
print(f"Drawing time for {chart_pattern.__class__.__name__} was {t1-t0}")


candle_pattern = OurCandlePattern()

t0 = time.time()
candle_result = candle_pattern.detect(candle_stream)
t1 = time.time()

print(f"Drawing time for {candle_pattern.__class__.__name__} was {t1-t0}")

#fig = chart.Figure(data=[])



def draw(snapshot_index):
	
	chart_view = chart_pattern.draw_snapshot(candle_stream,snapshot_index)
	if chart_result and not any(r is None for r in chart_result):
		chart_view.draw_background_results(chart_result)


	#time this since it is very reflexive
	pcp = PlotlyChartPainter()
	pcp.paint(chart_view)
	pcp.show()


snapshot_index = len(chart_result) - 1
draw(snapshot_index)









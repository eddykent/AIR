import datetime

import numpy as np


from charting.match_pattern import MatchPattern
from charting.chart_viewer import PlotlyChartPainter 
from utils import ListFileReader, Database 


the_date = datetime.datetime(2022,3,2,15,15)

lfr = ListFileReader()
currencies = lfr.read('fx_pairs/currencies.txt')
fx_pairs = lfr.read('fx_pairs/fx_mains.txt')
sorted(fx_pairs)

cur = Database()

query = 'querys/candle_stick_selector.sql'
parameters = {
	'chart_resolution':60,
	'the_date':the_date,
	'hour':the_date.hour,
	'days_back':20,
	'candle_offset':0,
	'currencies':currencies	
}

query = ''
with open('queries/candle_stick_selector.sql','r') as f:
	query = f.read()

cur.execute(query,parameters)
database_response = cur.fetchall()

match_pattern = MatchPattern()

haystack = [match_pattern.to_candles(database_response,pair) for pair in fx_pairs]

match_pattern.set_haystack(haystack)

candle_stream = match_pattern.to_candles(database_response,'EUR/USD')

chart_result = match_pattern.detect(candle_stream)

def draw(snapshot_index):
	chart_view = match_pattern.draw_snapshot(candle_stream,snapshot_index)
	chart_view.draw_background_results(chart_result)

	#time this since it is very reflexive
	pcp = PlotlyChartPainter()
	pcp.paint(chart_view)
	pcp.show()

draw(len(chart_result) - match_pattern.projection_length)






















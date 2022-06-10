import datetime
import time

import numpy as np
import pdb


from charting.match_pattern import MatchPattern
from charting.chart_viewer import PlotlyChartPainter 
from utils import ListFileReader, Database 


the_date = datetime.datetime(2022,3,2,15,0)

lfr = ListFileReader()
currencies = lfr.read('fx_pairs/currencies.txt')
fx_pairs = lfr.read('fx_pairs/fx_mains.txt')
sorted(fx_pairs)

cur = Database()

query = 'querys/candle_stick_selector.sql'
parameters = {
	'chart_resolution':240,
	'the_date':the_date,
	'hour':the_date.hour,
	'days_back':400,
	'candle_offset':120,
	'currencies':currencies	
}

query = ''
with open('queries/candle_stick_selector.sql','r') as f:
	query = f.read()

cur.execute(query,parameters)
database_response = cur.fetchall()

match_pattern = MatchPattern()

all_candles = cur.fetchcandles(fx_pairs)

haystack = np.array([all_candles[pair] for pair in fx_pairs])[:,:,:4]
haystack = haystack.astype(np.float64)
pdb.set_trace()
match_pattern.set_haystack(haystack)
candle_stream = np.array(all_candles.get('EUR/USD'))[np.newaxis,:,:]


def draw(snapshot_index):
	chart_view = match_pattern.draw_snapshot(candle_stream,snapshot_index)
	chart_view.draw_background_results(chart_result)

	#time this since it is very reflexive
	pcp = PlotlyChartPainter()
	pcp.paint(chart_view)
	pcp.show()

draw(len(chart_result) - match_pattern.projection_length)






















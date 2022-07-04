




import datetime 

from utils import Database, DataComposer, Configuration, ListFileReader
from charting.chart_pattern import SupportAndResistance, PivotPoints, ChartPattern
from charting.match_pattern import MatchPatternInstance, MatchPattern
from charting.trend_pattern import SymmetricTriangle
from charting.harmonic_pattern import *
import charting.chart_viewer as chv

import numpy as np

lfr = ListFileReader()
currencies = lfr.read('fx_pairs/currencies.txt')
fx_pairs = lfr.read('fx_pairs/fx_mains.txt')

the_date = datetime.datetime(2022,5,20,12,0)

candles = []
with Database(commit=False, cache=False) as cursor: 
	composer = DataComposer(cursor) #.candles(params).call()...
	#composer.call('get_candles_volumes_from_currencies',{'currencies':currencies,'this_date':the_date,'days_back':100,'chart_resolution':15})
	composer.call('get_candles_from_currencies',{'currencies':currencies,'this_date':the_date,'days_back':50,'chart_resolution':15})

	candle_result = composer.result(as_json=True)
	candles = composer.as_candles(candle_result,fx_pairs)


#chart_pattern = Butterfly()  #Gartley, Crab, DeepCrab, Bat, todo: Cypher
chart_pattern = Bat()





#chart_pattern._xtreme_degree = 2
#chart_pattern._order = 1
#chart_pattern.required_candles = 200

#chart_pattern = SupportAndResistance()
#chart_pattern = PivotPoints()
#chart_pattern  = MatchPatternInstance()
#chart_pattern = SymmetricTriangle()
chart_pattern = MatchPattern()




candle_streams = [candles[fx] for fx in fx_pairs]
chart_pattern.set_haystack(candle_streams)

results = chart_pattern.calculate_multiple(candle_streams)

#print a nice summary
#pdb.set_trace()
print(np.stack([np.arange(results.shape[0]),np.sum(results[:,:,0]==1,axis=1),np.sum(results[:,:,0]==-1,axis=1)],axis=1))

def show_chart(instrument_index, snap_index=-1):
	this_view = chv.ChartView()
	this_view.draw_candles(candle_streams[instrument_index])
	np_candles, _ = chart_pattern._construct(candle_streams)

	chart_view = chart_pattern.draw_snapshot(np_candles,snapshot_index=[snap_index],instrument_index=instrument_index)
	this_view += chart_view

	dots = ChartPattern.draw_snapshot(chart_pattern,np_candles,snapshot_index=[snap_index],instrument_index=instrument_index)
	this_view += dots

	result_bias = results[instrument_index,:,0]
	this_view.draw_background_results(result_bias) #effect for showing a bullish/bearish pattern!

	pcp = chv.PlotlyChartPainter()
	#pcp.paint(indicator_view)
	pcp.paint(this_view)
	pcp.show()

show_chart(0)



















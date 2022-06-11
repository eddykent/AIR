


import datetime 

from utils import Database, DataComposer, Configuration, ListFileReader
from charting.match_pattern import MatchPatternInstance 
from charting.chart_viewer import PlotlyChartPainter

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


chart_pattern  = MatchPatternInstance()

candle_streams = [candles[fx] for fx in fx_pairs]

chart_pattern.set_haystack(candle_streams)

results = chart_pattern.calculate_multiple(candle_streams)
#pdb.set_trace()
#print('check results')
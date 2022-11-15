


import datetime 

from utils import Database, DataComposer, Configuration, ListFileReader
from indicators.mathematic import *
from indicators.volatility import ChoppinessIndex

import charting.chart_viewer as chv

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


OurIndicator = FourierGradient
#OurIndicator = ChoppinessIndex

indicator = OurIndicator()

candle_streams = [candles[fx] for fx in fx_pairs]
results = indicator.calculate_multiple(candle_streams)



indicator_view = indicator.draw_snapshot(candle_streams[0])

pcp = chv.PlotlyChartPainter()
if indicator.candle_sticks:
	indicator_view.draw_candles(candle_streams[0])
pcp.paint(indicator_view)
pcp.show()

#pcp = PlotlyChartPainter()

#pcp.show()











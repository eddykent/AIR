


import datetime 

from utils import Database, DataComposer, Configuration, ListFileReader
from indicators.mathematic import *
from indicators.volatility import ChoppinessIndex

import charting.chart_viewer as chv
from setups.setup_tools import CandleDataTool

import debugging.functs as debug

lfr = ListFileReader()
currencies = lfr.read('fx_pairs/currencies.txt')
fx_pairs = lfr.read('fx_pairs/fx_mains.txt')

the_date = datetime.datetime(2022,5,20,12,0)

#candles = []


#with Database(commit=False, cache=False) as cursor: 
#	composer = DataComposer(cursor) #.candles(params).call()...
#	#composer.call('get_candles_volumes_from_currencies',{'currencies':currencies,'this_date':the_date,'days_back':100,'chart_resolution':15})
#	composer.call('get_candles_from_currencies',{'currencies':currencies,'this_date':the_date,'days_back':50,'chart_resolution':15})
#
#	candle_result = composer.result(as_json=True)
#	candles = composer.as_candles(candle_result,fx_pairs)

datatool = CandleDataTool() 
datatool.start_date = datetime.datetime(2022,8,4)
datatool.end_date = datetime.datetime(2022,11,20,12,0)
datatool.instruments = lfr.read('fx_pairs/fx_mains.txt')
datatool.volumes = True
debug.stopwatch('fetch candles')
datatool.read_data_from_currencies(currencies)
tsd = datatool.get_trade_signalling_data()
debug.stopwatch('fetch candles')


OurIndicator = FourierGradient
#OurIndicator = ChoppinessIndex
#OurIndicator = CorrelationAnalysis

indicator = OurIndicator()

candle_streams = [candles[fx] for fx in fx_pairs]
results = indicator.calculate_multiple(candle_streams)



indicator_view = indicator.draw_snapshot(tsd.np_candles,0)

pcp = chv.PlotlyChartPainter()
if indicator.candle_sticks:
	indicator_view.draw_candles(tsd.np_candles[0])
pcp.paint(indicator_view)
pcp.show()

#pcp = PlotlyChartPainter()

#pcp.show()











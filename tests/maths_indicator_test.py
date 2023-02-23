


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

import pdb
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

results = indicator(tsd.np_candles)

result0 = results[:,:,0] < 0
result1 = results[:,:,1] < 0
result2 = results[:,:,0] > 0
result3 = results[:,:,1] > 0


bullish1, bearish1 = (result0 & result1), (result2 & result3)
bullish2, bearish2 = (result2 & result3), (result0 & result1)
bullish3, bearish3 = (result0 & result3), (result2 & result1)
bullish4, bearish4 = (result2 & result1), (result0 & result3)

bullish = np.stack([bullish1,bullish2,bullish3,bullish4])
bearish = np.stack([bearish1,bearish2,bearish3,bearish4])

trying = 0 

def draw_charts(ii):
	for i in range(4):
		#indicator_view = indicator.draw_snapshot(tsd.np_candles,0)
		indicator_view = chv.ChartView()
		pcp = chv.PlotlyChartPainter(title=f"Chart {i}")
		indicator_view.draw_candles(tsd.np_candles[ii])
		result_bias = bullish[i,ii].astype(np.int) - bearish[i,ii].astype(np.int)
		indicator_view.draw_background_results(result_bias)
		pcp.paint(indicator_view)
		pcp.show()

#pcp = PlotlyChartPainter()
#conv tsd to singalling data and get setup results on simple 30,20 stop 

#pcp.show()
draw_charts(0)











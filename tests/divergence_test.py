


import datetime 

from utils import Database, DataComposer, Configuration, ListFileReader
from indicators.reversal import RSI, Stochastic 
from indicators.indicator import Typical
import charting.chart_viewer as chv

from setups.trade_setup import MomentumDivergenceTool

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




candle_streams = [candles[fx] for fx in fx_pairs]
#chart_pattern.set_haystack(candle_streams)

operator = RSI()
price_action = Typical()


momentum_result = operator.calculate_multiple(candle_streams)
price_action_result = price_action.calculate_multiple(candle_streams)
np_candles, _ = operator._construct(candle_streams)


divergence = MomentumDivergenceTool()
divergence.set_signals(price_action_result[:,:,0],momentum_result[:,:,0])
divergence_results = divergence.detect()
np_candles, _ = operator._construct(candle_streams)

def show_chart(instrument_index, snap_index=-1):
	this_view = chv.ChartView()
	this_view.draw_candles(candle_streams[instrument_index])
	
	
	chart_view = price_action.draw_snapshot(np_candles,snapshot_index=[snap_index],instrument_index=instrument_index)
	this_view += chart_view   
	
	#chart_view = chart_pattern.draw_snapshot(np_candles,snapshot_index=[snap_index],instrument_index=instrument_index)
	#this_view += chart_view   
	#work out how to draw the operator below the candlesticks

	result_bias = divergence_results[instrument_index,:]
	this_view.draw_background_results(result_bias) #effect for showing a bullish/bearish pattern!

	pcp = chv.PlotlyChartPainter()
	#pcp.paint(indicator_view)
	pcp.paint(this_view)
	pcp.show()

show_chart(0)



















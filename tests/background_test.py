


import datetime 

from utils import Database, DataComposer, Configuration, ListFileReader
from indicators.reversal import RSI, Stochastic 
from indicators.indicator import Typical
from indicators.mathematic import FourierGradient
import charting.chart_viewer as chv

from setups.setup_tools import DivTool, CandleDataTool

import numpy as np
import pdb

lfr = ListFileReader()
currencies = lfr.read('fx_pairs/currencies.txt')
fx_pairs = lfr.read('fx_pairs/fx_mains.txt')

#the_date = datetime.datetime(2022,5,20,12,0)
#
#candles = []
#with Database(commit=False, cache=False) as cursor: #now handled with CandleDataTool! :) 
#	composer = DataComposer(cursor) #.candles(params).call()...
#	#composer.call('get_candles_volumes_from_currencies',{'currencies':currencies,'this_date':the_date,'days_back':100,'chart_resolution':15})
#	composer.call('get_candles_from_currencies',{'currencies':currencies,'this_date':the_date,'days_back':50,'chart_resolution':15})
#
#	candle_result = composer.result(as_json=True)
#	candles = composer.as_candles(candle_result,fx_pairs)


datatool = CandleDataTool() 
datatool.start_date = datetime.datetime(2022,3,4)
datatool.end_date = datetime.datetime(2022,5,20,12,0)
datatool.instruments = lfr.read('fx_pairs/fx_mains.txt')
datatool.volumes = True
#dbf.stopwatch('fetch candles')
datatool.read_data_from_currencies(currencies)
tsd = datatool.get_trade_signalling_data()
#dbf.stopwatch('fetch candles')



#candle_streams = [candles[fx] for fx in fx_pairs]
#chart_pattern.set_haystack(candle_streams)

np_candles = tsd.np_candles
#pdb.set_trace()
candle_streams = tsd.candlesticks

#operator = RSI()
#price_action = Typical()

#momentum_result = operator.calculate_multiple(candle_streams)
#price_action_result = price_action.calculate_multiple(candle_streams)
#np_candles, _ = operator._construct(candle_streams)
#momentum_result = operator._perform(np_candles)
#price_action_result = price_action._perform(np_candles)
#pdb.set_trace()
#momentum_result = operator(np_candles)
#price_action_result = price_action(np_candles)

#pdb.set_trace()

#divergence = MomentumDivergenceTool()
#divergence.set_signals(price_action_result[:,:,0],momentum_result[:,:,0])
#divergence_results = divergence.detect()


#div_tool = DivTool(momentum_result,price_action_result)

#bullish, bearish = div_tool.markup()
#bias = bullish.astype(np.int) - bearish.astype(np.int)

fg = FourierGradient()
fg_result = fg(np_candles)
neg_bias = (fg_result[:,:,0] > 0) & (fg_result[:,:,1] > 0)
pos_bias = (fg_result[:,:,0] < 0) & (fg_result[:,:,1] < 0)

bias = pos_bias.astype(np.int) - neg_bias.astype(np.int)


def show_chart(instrument_index, snap_index=-1):
	this_view = chv.ChartView()
	this_view.draw_candles(np_candles[instrument_index])
	
	
	#chart_view = price_action.draw_snapshot(candle_streams[instrument_index],snapshot_index=[snap_index],instrument_index=instrument_index)
	#this_view += chart_view   
	
	#chart_view = chart_pattern.draw_snapshot(np_candles,snapshot_index=[snap_index],instrument_index=instrument_index)
	#this_view += chart_view   
	#work out how to draw the operator below the candlesticks
	result_bias = bias[instrument_index]
	
	#pdb.set_trace()
	this_view.draw_background_results(result_bias) #effect for showing a bullish/bearish pattern!

	pcp = chv.PlotlyChartPainter()
	#pcp.paint(indicator_view)
	pcp.paint(this_view)
	pcp.show()

show_chart(0)



















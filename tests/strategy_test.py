

#test any strategy either tuning or running 

import numpy as np 
import pdb 
from datetime import datetime


from setups.setup_tools import CandleDataTool, PipStop, ATRStop
from utils import ListFileReader, Database

from indicators.reversal import RSI 
from indicators.moving_average import EMA
from indicators.currency import CurrencyWrapper

from strategies.iterative_search import IterativeSearch, LambdaContainer

from charting import candle_stick_functions as csf

from debugging import functs as dbf

lfr = ListFileReader()
currencies = lfr.read('fx_pairs/currencies.txt')
fx_pairs = lfr.read('fx_pairs/fx_mains.txt')


datatool = CandleDataTool() 
datatool.start_date = datetime(2022,9,5)
datatool.end_date = datetime(2022,11,16)
#datatool.start_date = datetime(2022,12,16)
#datatool.end_date = datetime(2022,12,23)
datatool.instruments = lfr.read('fx_pairs/fx_mains.txt')
datatool.volumes = True
#datatool.ask_candles = True
datatool.chart_resolution = 15
#datatool.candle_offset = 15
dbf.stopwatch('fetch candles')
datatool.read_data_from_currencies(currencies)
trade_signalling_data = datatool.get_trade_signalling_data()
dbf.stopwatch('fetch candles')

datatool.backtesting = True 
dbf.stopwatch('fetch candles')
datatool.read_data_from_currencies(currencies)
backtesting_data = datatool.get_trade_signalling_data()
dbf.stopwatch('fetch candles')


#a breif list of indicators we will use for this 

#ema_lamb_bull = lambda res, npc : npc[:,:,csf.low] > res[:,:,0]
#ema_lamb_bear = lambda res, npc : npc[:,:,csf.high] < res[:,:,0]

np_candles = trade_signalling_data.np_candles
#pdb.set_trace()
currency_thing = CurrencyWrapper(RSI(),fx_pairs,currencies)
currency_result = currency_thing(np_candles)

lambdas = [
	#emas
	LambdaContainer(EMA(200), lambda res, npc : npc[:,:,csf.low] > res[:,:,0], lambda res, npc : npc[:,:,csf.high] < res[:,:,0], 'full clearance'),
	LambdaContainer(EMA(100), lambda res, npc : npc[:,:,csf.close] > res[:,:,0], lambda res, npc : npc[:,:,csf.close] < res[:,:,0], 'clearence close only'),
	LambdaContainer(EMA(50), lambda res, npc : npc[:,:,csf.close] > res[:,:,0], lambda res, npc : npc[:,:,csf.close] < res[:,:,0], 'clearence close only'),
	LambdaContainer(EMA(15), lambda res, npc : npc[:,:,csf.close] > res[:,:,0], lambda res, npc : npc[:,:,csf.close] < res[:,:,0], 'clearence close only'),
	
	#rsis
	LambdaContainer(RSI(20), lambda res, npc : res[:,:,0] < 0.2, lambda res, npc : res[:,:,0] > 0.8, '0.2 and 0.8'),
	LambdaContainer(RSI(14), lambda res, npc : res[:,:,0] < 0.2, lambda res, npc : res[:,:,0] > 0.8, '0.2 and 0.8'),
	LambdaContainer(RSI(9), lambda res, npc : res[:,:,0] < 0.2, lambda res, npc : res[:,:,0] > 0.8, '0.2 and 0.8'),
	LambdaContainer(RSI(5), lambda res, npc : res[:,:,0] < 0.2, lambda res, npc : res[:,:,0] > 0.8, '0.2 and 0.8'),
	
	#currency strength metrics
	LambdaContainer(CurrencyWrapper(RSI(14),fx_pairs,currencies), lambda res, npc : (npc[:,:,0] > 0.65) & (npc[:,:,1] < 0.35), lambda res,npc : (npc[:,:,1] > 0.65) & (npc[:,:,0] < 0.35), '.35 .65 activation'),
	LambdaContainer(CurrencyWrapper(RSI(9),fx_pairs,currencies), lambda res, npc : (npc[:,:,0] > 0.65) & (npc[:,:,1] < 0.35), lambda res,npc : (npc[:,:,1] > 0.65) & (npc[:,:,0] < 0.35), '.35 .65 activation'),
	LambdaContainer(CurrencyWrapper(RSI(14),fx_pairs,currencies), lambda res, npc : (npc[:,:,0] > npc[:,:,1]), lambda res,npc : (npc[:,:,1] > npc[:,:,0]), 'x/y x>y activation'),
	LambdaContainer(CurrencyWrapper(RSI(9),fx_pairs,currencies), lambda res, npc : (npc[:,:,0] > npc[:,:,1]), lambda res,npc : (npc[:,:,1] > npc[:,:,0]), 'x/y x>y activation'),
 
	#LambdaContainer(MACD(), lambda res, npc : #unsure how this will work yet
 ]

stops = [
	PipStop(take_profit_pips=30,stop_loss_pips=20)
]

#pdb.set_trace()
its = IterativeSearch(2)#3

its.lambda_containers = lambdas 
its.stop_operators = stops 

its.pass_data(trade_signalling_data,backtesting_data)
its.main() 




















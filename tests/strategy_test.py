

#test any strategy either tuning or running 

import numpy as np 
import pdb 
from datetime import datetime

import pickle

from setups.setup_tools import CandleDataTool, PipStop, ATRStop, RollingExtremeStop
from utils import ListFileReader, Database

from indicators.reversal import RSI 
from indicators.moving_average import EMA
from indicators.currency import CurrencyWrapper

from strategies.setup_search import ExhaustiveSearch, TriggerBlock, SetupBlock, SetupSearch 
import strategies.trigger_block_lists as tbl
import strategies.setup_lists as sul 

from setups.collected_setups import Harmony

from charting import candle_stick_functions as csf

from backtest import BackTesterCandles, BackTestStatistics 

from debugging import functs as dbf

train_period_start = datetime(2022,6,6)
train_period_end = datetime(2022,11,18)

test_period_start = datetime(2022,11,21)
test_period_end = datetime(2022,11,25)

resolution = 15
combination = 3
grace_period = 50


lfr = ListFileReader()
currencies = lfr.read('fx_pairs/currencies.txt')
fx_pairs = lfr.read('fx_pairs/fx_mains.txt')


datatool = CandleDataTool() 
datatool.start_date = train_period_start
datatool.end_date = train_period_end
#datatool.start_date = datetime(2022,12,16)
#datatool.end_date = datetime(2022,12,23)
datatool.instruments = lfr.read('fx_pairs/fx_mains.txt')
datatool.volumes = True
datatool.grace_period = grace_period
#datatool.ask_candles = True
datatool.chart_resolution = resolution
#datatool.candle_offset = 15
dbf.stopwatch('fetch candles')
datatool.read_data_from_currencies(currencies)
trade_signalling_data = datatool.get_trade_signalling_data()

#with open('results/trade_signalling_data.pkl','wb') as f:
#	pickle.dump(trade_signalling_data,f)

#with open('results/trade_signalling_data.pkl','rb') as f:
#	trade_signalling_data = pickle.load(f)

dbf.stopwatch('fetch candles')


datatool.backtesting = True 
dbf.stopwatch('fetch bt candles')
datatool.read_data_from_currencies(currencies)
backtesting_data = datatool.get_trade_signalling_data()

#with open('results/backtesting_data.pkl','wb') as f:
#	pickle.dump(backtesting_data,f)

#with open('results/backtesting_data.pkl','rb') as f:
#	backtesting_data = pickle.load(f)
dbf.stopwatch('fetch bt candles')

sb = SetupBlock(Harmony(),trade_signalling_data) #, lambda res, npc : res[:,:,0] > 0, lambda res, npc : res[:,:,0] < 0)
#a breif list of indicators we will use for this 

#pdb.set_trace()

#ema_lamb_bull = lambda res, npc : npc[:,:,csf.low] > res[:,:,0]
#ema_lamb_bear = lambda res, npc : npc[:,:,csf.high] < res[:,:,0]

np_candles = trade_signalling_data.np_candles
#pdb.set_trace()
currency_thing = CurrencyWrapper(RSI(),fx_pairs,currencies)
currency_result = currency_thing(np_candles)

#triggers = tbl.good_set(trade_signalling_data)

stops = [
	PipStop(take_profit_pips=35,stop_loss_pips=25)
	#RollingExtremeStop()
]

trigger_block_func = tbl.good_set

#pdb.set_trace()
#if False:
its = ExhaustiveSearch(combination)# increase to 3 for longer (better?) runs
its.trigger_blocks = trigger_block_func(trade_signalling_data)
its.stop_operators = stops 
suggestion_result = its.train(trade_signalling_data,backtesting_data) 



datatool = CandleDataTool() 
datatool.start_date = test_period_start
datatool.end_date = test_period_end
#datatool.start_date = datetime(2022,12,16)
#datatool.end_date = datetime(2022,12,23)
datatool.instruments = lfr.read('fx_pairs/fx_mains.txt')
datatool.volumes = True
datatool.grace_period = grace_period
#datatool.ask_candles = True
datatool.chart_resolution = resolution
#datatool.candle_offset = 15
dbf.stopwatch('fetch test candles')
datatool.read_data_from_currencies(currencies)
later_trade_signalling_data = datatool.get_trade_signalling_data()

dbf.stopwatch('fetch test candles')


datatool.backtesting = True 
dbf.stopwatch('fetch bt test candles')
datatool.read_data_from_currencies(currencies)
later_backtesting_data = datatool.get_trade_signalling_data()

dbf.stopwatch('fetch bt test candles')


#a breif list of indicators we will use for this 

#ema_lamb_bull = lambda res, npc : npc[:,:,csf.low] > res[:,:,0]
#ema_lamb_bear = lambda res, npc : npc[:,:,csf.high] < res[:,:,0]

np_candles = trade_signalling_data.np_candles
#pdb.set_trace()
currency_thing = CurrencyWrapper(RSI(),fx_pairs,currencies)
currency_result = currency_thing(np_candles)


btc = BackTesterCandles(later_backtesting_data)

its2 = ExhaustiveSearch(combination)
its2.trigger_blocks = trigger_block_func(later_trade_signalling_data)
its2.stop_operators = stops
#pdb.set_trace()
these_signals = its2.infer(later_trade_signalling_data,suggestion_result)

these_results = btc.perform(these_signals) 
bts = BackTestStatistics(later_backtesting_data, these_signals, these_results)
results = bts.calculate()

if False: 
	ss1 = SetupSearch() 
	ss1.setup_list = sul.third_party_list 
	suggestion_result = ss1.train(trade_signalling_data,backtesting_data) 

	#pdb.set_trace() #check suggestion_result
	ss2 = SetupSearch() 
	ss2.setup_list = sul.third_party_list
	ss_signals = ss2.infer(later_trade_signalling_data,suggestion_result)
	ss_results = btc.perform(ss_signals) 


	bts2 = BackTestStatistics(later_backtesting_data, ss_signals, ss_results)
	ss_results = bts2.calculate()

#reload pickle from prev rrun for faster 
#full_results = [] 
#with open('results/full_results.pkl','rb') as f:
#	full_results = pickle.load(f)
#
#its.process_full_results(full_results) #test this fnc


#btc = BackTesterCandles(backtesting_data) 
#bad_sigs = []
#with open('results/badsignals.pkl','rb') as f:	
#	bad_sigs = pickle.load(f)
#bad_result = btc.perform(bad_sigs)
#bts = BackTestStatistics(backtesting_data, bad_sigs, bad_result)
#pdb.set_trace()
#some_result = bts.calculate()














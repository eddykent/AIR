

#test any strategy either tuning or running 

import numpy as np 
import pdb 
from datetime import datetime, timedelta

import pickle

from data.base.candles import CandleDataTool
from data.tools.cursor import Database

from setups.setup_tools import PipStop, ATRStop, RollingExtremeStop
from utils import ListFileReader

from indicators.reversal import RSI 
from indicators.moving_average import EMA
from indicators.currency import CurrencyWrapper

from strategy.setup_search import ExhaustiveSearch, TriggerBlock, SetupBlock, SetupSearch 
import strategy.trigger_block_lists as tbl
import strategy.setup_lists as sul 

from setups.collected_setups import Harmony, Triangles, Shapes

from charting import candle_stick_functions as csf

from backtest import BackTesterCandles, BackTestStatistics 


from filters.time_based import EconomicCalendarTool, EconomicCalendarFilter, PipSpreadFilter, TimeOfDayFilter


from debugging import functs as dbf

week = 7
week_offset = 1
test_date_offset = timedelta(days=week*week_offset)

#train_period_start = datetime(2022,10,6)#just care about if it runs for now for debugging
train_period_start = datetime(2022,10,17) + test_date_offset #actual serious test (too long?)  1months => 1 week 
train_period_end = datetime(2022,11,19) + test_date_offset

test_period_start = datetime(2022,11,21) + test_date_offset
test_period_end = datetime(2022,11,26) + test_date_offset

hole_end = datetime(2023,2,10)
hole_start = datetime(2022,1,1)

from data.tools.holefinder import HoleFinder

#hf = HoleFinder(hole_start,hole_end,['EUR/USD','USD/JPY'])
#holes = hf.find_holes()

#some_signals = []
#with open('data/pickles/trade_signals.pkl', 'rb') as fp:
#	some_signals =pickle.load(fp)
#

#some_signals = ecf.filter(some_signals)

resolution = 15 #required for BT, not for strategy
combination = 4  #3
grace_period = 50 #enough?

trigger_block_func = tbl.full_set
#pdb.set_trace()
#trigger_block_func = tbl.small_set

lfr = ListFileReader()
currencies = lfr.read('fx_pairs/currencies.txt')
fx_pairs = lfr.read('fx_pairs/fx_mains.txt')

stop_tool = PipStop(take_profit_pips=30,stop_loss_pips=20)



###LABELLING RESULT
tbfn = trigger_block_func.__name__
stopstr = '?' #break on purpose! We want to know what the stops were
if stop_tool.__class__.__name__ == 'PipStop':
	stopstr = f"{stop_tool.tpp}pip{stop_tool.slp}"
if stop_tool.__class__.__name__ == 'ATRStop':
	stopstr = f"a{stop_tool.atr.period}t{stop_tool.tpm}r{stop_tool.slm}"
if stop_tool.__class__.__name__ == 'RollingExtremeStop':
	stopstr = f"r{stop_tool.risk_reward_ratio}p{stop_tool.period}".replace('.','r')

trainstartstr = f"{train_period_start.year}{train_period_start.month}{train_period_start.day}"
trainendstr = f"{train_period_end.year}{train_period_end.month}{train_period_end.day}"
backtest_fn = f"backtest-{stopstr}-{tbfn}({combination})-{trainstartstr}-{trainendstr}.pkl" 


print(f"results will be saved in {backtest_fn}")

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


fstart_date = train_period_start # min(s.the_date for s in some_signals)
fend_date = train_period_end # max(s.the_date for s in some_signals)
ect = EconomicCalendarTool(fstart_date,fend_date)
ecf = EconomicCalendarFilter(ect.get_df())
fmask = ecf.extract_mask(trade_signalling_data.instruments,trade_signalling_data.timeline)
#pdb.set_trace()

datatool.backtesting = True 
dbf.stopwatch('fetch bt candles')
datatool.read_data_from_currencies(currencies)
backtesting_data = datatool.get_trade_signalling_data()

#with open('results/backtesting_data.pkl','wb') as f:
#	pickle.dump(backtesting_data,f)

#with open('results/backtesting_data.pkl','rb') as f:
#	backtesting_data = pickle.load(f)
dbf.stopwatch('fetch bt candles')

#pips=5, pip_handle=PipHandler()



#a breif list of indicators we will use for this 

#pdb.set_trace()

#ema_lamb_bull = lambda res, npc : npc[:,:,csf.low] > res[:,:,0]
#ema_lamb_bear = lambda res, npc : npc[:,:,csf.high] < res[:,:,0]

#np_candles = trade_signalling_data.np_candles
#pdb.set_trace()
#currency_thing = CurrencyWrapper(RSI(),fx_pairs,currencies)
#currency_result = currency_thing(np_candles)

#get these working! - yay 
#print('try triangles')
#sb1 = SetupBlock(Triangles(),trade_signalling_data) #, lambda res, npc : res[:,:,0] > 0, lambda res, npc : res[:,:,0] < 0)
#bullish, bearish = sb1(np_candles) 
#
#print('try shapes')
#sb2 = SetupBlock(Shapes(),trade_signalling_data)
#bullish, bearish = sb2(np_candles) 
#pdb.set_trace()



#triggers = tbl.good_set(trade_signalling_data)


ect1 = EconomicCalendarTool(train_period_start,train_period_end)

ecf1 = EconomicCalendarFilter(ect1.get_df())
psf1 = PipSpreadFilter(backtesting_data) 
tdf1 = TimeOfDayFilter()

training_filters = [ecf1, psf1, tdf1]



#pdb.set_trace()
#if False:
its = ExhaustiveSearch(combination)# increase to 3 for longer (better?) runs
its.trigger_blocks = trigger_block_func(trade_signalling_data)
its.stop_tool = stop_tool 
its.filters = training_filters
backtest_result = its.train(trade_signalling_data,backtesting_data) 

with open('results/pickles/'+backtest_fn,'wb') as btfn:
	pickle.dump(backtest_result,btfn)


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

#np_candles = trade_signalling_data.np_candles
#pdb.set_trace()
#currency_thing = CurrencyWrapper(RSI(),fx_pairs,currencies)
#currency_result = currency_thing(np_candles)


ect2 = EconomicCalendarTool(test_period_start,test_period_end)

ecf2 = EconomicCalendarFilter(ect2.get_df())
psf2 = PipSpreadFilter(later_backtesting_data) 
tdf2 = TimeOfDayFilter()

testing_filters = [ecf2, psf2, tdf2]

btc = BackTesterCandles(later_backtesting_data)

its2 = ExhaustiveSearch(combination)
its2.trigger_blocks = trigger_block_func(later_trade_signalling_data)
its2.stop_tool = stop_tool
its2.filters = testing_filters
#pdb.set_trace()
 #ug = suggestions[(suggestions['N'] > 25) & (suggestions['ratio'] > 0.55)]
def try_suggestion(suggestion):
	these_signals = its2.infer(later_trade_signalling_data,suggestion)

	these_results = btc.perform(these_signals) 
	bts = BackTestStatistics(later_backtesting_data, these_signals, these_results)
	results = bts.calculate()
	print(results)

#pdb.set_trace()
#with open('data/pickles/suggestions.pkl','rb') as fp:
#	backtest_result = pickle.load(fp)
	
suggestions = backtest_result[backtest_result['objective_value'] > 0]
suggestions.sort_values('objective_value',ascending=False)

try_suggestion(suggestions.head(250))

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














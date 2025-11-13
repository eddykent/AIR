
##test for getting best inference values 
import pickle
import datetime

from data.base.candles import CandleDataTool
from data.tools.cursor import Database

from setups.setup_tools import PipStop

from backtest import BackTesterCandles, BackTestStatistics 

from utils import ListFileReader

from strategy.setup_search import ExhaustiveSearch, TriggerBlock, SetupBlock, SetupSearch, CombinationChoice, SignalShield
import strategy.trigger_block_lists as tbl

from filters.time_based import EconomicCalendarTool, EconomicCalendarFilter, PipSpreadFilter, TimeOfDayFilter

import debugging.functs as dbf

directory = './data/pickles/strats/'

filenames = [
	'backtest-35pip25-full_set(5)-20221003-20221105.pkl',
	'backtest-35pip25-full_set(5)-20221010-20221112.pkl', #small loss
	'backtest-35pip25-full_set(5)-20221017-20221119.pkl',#loss
	'backtest-35pip25-full_set(5)-20221024-20221126.pkl', # win
	'backtest-35pip25-full_set(5)-20221031-20221203.pkl', #loss
	'backtest-35pip25-full_set(5)-20221230-20230127.pkl', #massive loss
	'backtest-35pip25-full_set(5)-20230106-20230203.pkl', #win but some large neg numbers
	'backtest-35pip25-full_set(5)-20230113-20230210.pkl', #loss
	'backtest-35pip25-full_set(5)-20230120-20230217.pkl', #win
	'backtest-35pip25-full_set(5)-20230127-20230224.pkl', #loss
	'backtest-35pip25-full_set(5)-20221116-20230224.pkl', #longer but has less - backtest limited to 1500
	'backtest-35pip25-full_set(5)-20221019-20230127.pkl', #(max 5 per day)
	'backtest-33pip30-full_set(5)-20221019-20230127.pkl',
	#''
]
filename = filenames[-1]   #3,5,6,7 is bad 


backtest_result = None

with open(directory+filename,'rb') as f:
	backtest_result = pickle.load(f)

filename_end_str = filename[-12:-4]
test_period_before_start = datetime.datetime(int(filename_end_str[:4]),int(filename_end_str[4:6]),int(filename_end_str[6:]))
test_period_start = test_period_before_start + datetime.timedelta(days=3)
test_period_end = test_period_before_start + datetime.timedelta(days=10)


trigger_block_func = tbl.full_set

stop_tool = PipStop(take_profit_pips=26,stop_loss_pips=24)

resolution = 15 #required for BT, not for strategy
combination = 5  #3
grace_period = 75 #enough?

lfr = ListFileReader()
currencies = lfr.read('fx_pairs/currencies.txt')
fx_pairs = lfr.read('fx_pairs/fx_mains.txt')


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

def try_suggestion(suggestion):
	these_signals = its2.infer(later_trade_signalling_data,suggestion)
	
	sshield = SignalShield(later_trade_signalling_data)
	these_signals = sshield.get_signals(these_signals)
	
	
	these_results = btc.perform(these_signals) 
	bts = BackTestStatistics(later_backtesting_data, these_signals, these_results)
	results = bts.calculate()
	return results

#pdb.set_trace()
#with open('data/pickles/suggestions.pkl','rb') as fp:
#	backtest_result = pickle.load(fp)

cc = CombinationChoice()
#suggestion = cc.get_individuals(backtest_result)
#suggestion = cc.get_pareto_optimals(cc.apply_bounds(backtest_result))
#suggestion = cc.get_top_each(backtest_result)
backtest_result = cc.apply_bounds(backtest_result,nlb=5,nhb=0,ratio=0.6,streak_diff=False)
#backtest_result = cc.get_pareto_optimals(backtest_result)
#backtest_result = cc.get_top_each(backtest_result,top=2)
#backtest_result = cc.get_top_each(backtest_result,top=10) #limit to 5 strat per instrument
backtest_result = backtest_result.sort_values(by=['ratio'],ascending=False).head(500)
#backtest_result = cc.get_top_each(backtest_result)
#backtest_result = backtest_result.sort_values(by=['ratio'],ascending=False).head(100)
suggestion = backtest_result

#suggestions = backtest_result[backtest_result['objective_value'] > 0]
#suggestions.sort_values('objective_value',ascending=False)

results = try_suggestion(suggestion)
print(results)







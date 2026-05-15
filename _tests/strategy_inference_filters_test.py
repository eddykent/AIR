
##test for getting best inference values 
import pickle
import datetime

from data.base.candles import CandleDataTool, PartialCandleDataTool
from data.tools.cursor import Database

from setups.setup_tools import PipStop

import pandas as pd
from backtest import BackTesterCandles, BackTestStatistics, win_statuses

from utils import ListFileReader

from strategy.setup_search import ExhaustiveSearch, TriggerBlock, SetupBlock, SetupSearch, CombinationChoice, SignalShield
import strategy.trigger_block_lists as tbl

from filters.time_based import EconomicCalendarTool, EconomicCalendarFilter, PipSpreadFilter, TimeOfDayFilter

from filters.trade_filter import FilterConfusionMatrix, TradeFilter, AntiSignalFilter
from filters.simple_filters import ForexSignalsAnchorBarFilter
from filters.time_based import EconomicCalendarFilter
from filters.meta_based import ClientSentimentFilter, FlatCorrelationFilter, CurrencyStrengthFilter, CurrencyStrengthOperator, CorrelationFilter

from indicators.moving_average import EMA 
from indicators.reversal import RSI

import debugging.functs as dbf

import pdb

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
	'backtest-35pip25-full_set(5)-20221116-20230224.pkl', #longer
	'backtest-35pip25-full_set(5)-20221019-20230127.pkl',
	####
	'backtest-35pip25-full_set(5)-20221026-20230203.pkl', #these break partial candle filters
	'backtest-35pip25-full_set(5)-20221102-20230210.pkl',
	'backtest-35pip25-full_set(5)-20221109-20230217.pkl'
	
]
filename = filenames[-4]   #3,5,6,7 is bad 


backtest_result = None

with open(directory+filename,'rb') as f:
	backtest_result = pickle.load(f)

filename_end_str = filename[-12:-4]
test_period_before_start = datetime.datetime(int(filename_end_str[:4]),int(filename_end_str[4:6]),int(filename_end_str[6:]))
test_period_start = test_period_before_start + datetime.timedelta(days=2)
test_period_end = test_period_before_start + datetime.timedelta(days=8)
#pdb.set_trace()


trigger_block_func = tbl.full_set

stop_tool = PipStop(take_profit_pips=35,stop_loss_pips=25)

resolution = 15 #required for BT, not for strategy
combination = 5  #3
grace_period = 100 #enough?

lfr = ListFileReader()
currencies = lfr.read('fx_pairs/currencies.txt')
fx_pairs = lfr.read('fx_pairs/fx_mains.txt')
instruments = fx_pairs


datatool = CandleDataTool() 
datatool.start_date = test_period_start
datatool.end_date = test_period_end
#datatool.start_date = datetime(2022,12,16)
#datatool.end_date = datetime(2022,12,23)
datatool.instruments = instruments
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



def try_suggestion(suggestion,anti_suggestion=None):
	these_signals = its2.infer(later_trade_signalling_data,suggestion)
	anti_signals = None
	if anti_suggestion is not None:
		anti_signals = its2.infer(later_trade_signalling_data,anti_suggestion)
	
	sshield = SignalShield(later_trade_signalling_data)
	original_signals = sshield.get_signals(these_signals)
	
	
	cdt2 = CandleDataTool()
	cdt2.start_date = test_period_start
	cdt2.end_date = test_period_end
	cdt2.instruments = instruments
	cdt2.chart_resolution = 240
	cdt2.candle_offset = 120
	cdt2.grace_period = 100
	cdt2.volumes = True
	cdt2.read_data_from_currencies(currencies)
	filter_data = cdt2.get_trade_signalling_data()

	pcdt = PartialCandleDataTool()
	pcdt.instruments = instruments
	pcdt.chart_resolution = cdt2.chart_resolution
	pcdt.candle_offset = cdt2.candle_offset
	pcdt.volumes = cdt2.volumes
	partial_candles = pcdt.read_data_from_currencies(currencies,original_signals['the_date'].to_list())
	
	anti = None
	if anti_signals is not None:	
		anti = AntiSignalFilter(anti_signals)
	cso = CurrencyStrengthOperator(instruments,currencies)
	ema = EMA() 
	ema.period = 5
	rsistrength = RSI(5)
	rsicorrel = RSI(5) 
	csf = CurrencyStrengthFilter(rsistrength,cso,ema,filter_data, partial_candles) #needs HTF
	crsf = CorrelationFilter(rsicorrel,filter_data,partial_candles)
	clsf = ClientSentimentFilter(filter_data, partial_candles)
	
	filtered_signals = original_signals
	#filtered_signals = crsf.filter(filtered_signals) #works with 240 TF and RSI 5 (but 120 offset implies look ahead)
	#filtered_signals = csf.filter(filtered_signals) #works with 240 TF and RSI 5 (but 120 offset implies look ahead)
	#filtered_signals = clsf.filter(filtered_signals)
	#filtered_signals = TradeFilter.filter_any([crsf,csf,anti], filtered_signals)
	filtered_signals = anti.filter(filtered_signals) if anti is not None else filtered_signals 
	
	#filters dont work together 
	
	original_results = btc.perform(original_signals) 
	bts = BackTestStatistics(later_backtesting_data, original_signals, original_results)
	original = bts.calculate()
	#print(original)
	
	won_signal_ids = original_results['signal_id'][original_results['result_status'].isin(win_statuses)]
	passed_signal_ids = filtered_signals['signal_id']
	
	fcm = FilterConfusionMatrix(original_signals)
	cm = fcm.create_confusion_matrix(won_signal_ids, passed_signal_ids)
	#pdb.set_trace()
	
	filtered_results = btc.perform(filtered_signals)
	bts = BackTestStatistics(later_backtesting_data, filtered_signals, filtered_results)
	filtered = bts.calculate()
	#print(filtered)
	
	return original,filtered, cm
	

#pdb.set_trace()
#with open('data/pickles/suggestions.pkl','rb') as fp:
#	backtest_result = pickle.load(fp)

cc = CombinationChoice()
#suggestion = cc.get_individuals(backtest_result)
#suggestion = cc.get_pareto_optimals(cc.apply_bounds(backtest_result))
#suggestion = cc.get_top_each(backtest_result)
#backtest_result = cc.apply_bounds(backtest_result,nlb=25,streak_diff=-100)
#backtest_result = cc.get_top_each(backtest_result,top=5) #limit to 5 strat per instrument
#backtest_result = backtest_result.sort_values(by=['ratio'],ascending=False).head(100)
#backtest_result = cc.get_top_each(backtest_result)

#pdb.set_trace()

#good_backtest_result = cc.apply_bounds(backtest_result.copy(),nlb=50,nhb=0,ratio=0.55,streak_diff=False)
#good_backtest_result = good_backtest_result.sort_values(by=['ratio'],ascending=False).head(500) #selects loads of 1-hits
good_backtest_result = cc.get_top_each(backtest_result,top=25)

high_wr_lots = backtest_result[backtest_result['ratio'] > 0.8].sort_values(by=['N'], ascending=False).head(500)
med_wr_lots = backtest_result[backtest_result['ratio'] > 0.65].sort_values(by=['N'], ascending=False).head(250)

won_hits = backtest_result[(backtest_result['N'] == 1) & (backtest_result['ratio'] == 1)]
won_5s = backtest_result[(backtest_result['N'] >= 5) & (backtest_result['ratio'] == 1)]


#bad_backtest_result = backtest_result[backtest_result['N'] >= 50]
#bad_backtest_result = bad_backtest_result.sort_values(by=['ratio']).head(2000)
bad_backtest_result = cc.get_bottom_each(backtest_result,top=50)

pdb.set_trace()

#suggestion = pd.concat([high_wr_lots,med_wr_lots])
suggestion =  med_wr_lots
anti_suggestion = bad_backtest_result#.head(1)

#pdb.set_trace()

#suggestions = backtest_result[backtest_result['objective_value'] > 0]
#suggestions.sort_values('objective_value',ascending=False)



#filtered_signals  = csf.filter(signals)
#filtered_signals = clsf.filter(filtered_signals)
#filtered_signals = crsf.filter(filtered_signals)
#print(str(len(signals)) + ' -> ' + str(len(filtered_signals)))


original, filtered, cm = try_suggestion(suggestion, anti_suggestion)
print(original)
print(filtered)
print(cm)

print(f"Orignal: {original['output_balance'].sum()}")
print(f"Filtered: {filtered['output_balance'].sum()}")









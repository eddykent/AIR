
##test for getting best inference values 
import pickle
import datetime

from data.base.candles import CandleDataTool, PartialCandleDataTool
from data.tools.cursor import Database

from setups.setup_tools import PipStop

from backtest import BackTesterCandles, BackTestStatistics, win_statuses

from utils import ListFileReader

from strategy.setup_search import ExhaustiveSearch, TriggerBlock, SetupBlock, SetupSearch, CombinationChoice, SignalShield
import strategy.trigger_block_lists as tbl

from filters.time_based import EconomicCalendarTool, EconomicCalendarFilter, PipSpreadFilter, TimeOfDayFilter

from filters.trade_filter import FilterConfusionMatrix, LambdaSelectFilter
from filters.simple_filters import ForexSignalsAnchorBarFilter
from filters.time_based import EconomicCalendarFilter
from filters.ai_based import AIInvokeFilter
#from filters.meta_based import ClientSentimentFilter, FlatCorrelationFilter, CurrencyStrengthFilter, CurrencyStrengthOperator, CorrelationFilter

#from indicators.moving_average import EMA 
#from indicators.reversal import RSI



from models.trade_inspector_model import TradeInspectorModel



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
	
]
filename = filenames[-1]   #3,5,6,7 is bad 


filename_end_str = filename[-12:-4]
test_period_before_start = datetime.datetime(int(filename_end_str[:4]),int(filename_end_str[4:6]),int(filename_end_str[6:]))
train_period_end = test_period_before_start
train_period_start = train_period_end - datetime.timedelta(days=14)
test_period_start = test_period_before_start + datetime.timedelta(days=2)
test_period_end = test_period_before_start + datetime.timedelta(days=7)

trigger_block_func = tbl.full_set

stop_tool = PipStop(take_profit_pips=35,stop_loss_pips=25)

resolution = 15 #required for BT, not for strategy
combination = 5  #3
grace_period = 75 #enough?

lfr = ListFileReader()
currencies = lfr.read('fx_pairs/currencies.txt')
fx_pairs = lfr.read('fx_pairs/fx_mains.txt')
instruments = fx_pairs


datatool = CandleDataTool() 
datatool.start_date = train_period_start
datatool.end_date = train_period_end
#datatool.start_date = datetime(2022,12,16)
#datatool.end_date = datetime(2022,12,23)
datatool.instruments = instruments
datatool.volumes = True
datatool.grace_period = grace_period
#datatool.ask_candles = True
datatool.chart_resolution = resolution
#datatool.candle_offset = 15


dbf.stopwatch('fetch train candles')
datatool.read_data_from_currencies(currencies)
train_signalling_data = datatool.get_trade_signalling_data()

dbf.stopwatch('fetch train candles')

datatool.backtesting = True 
dbf.stopwatch('fetch bt train candles')
datatool.read_data_from_currencies(currencies)
train_backtesting_data = datatool.get_trade_signalling_data()

dbf.stopwatch('fetch bt train candles')



ect2 = EconomicCalendarTool(train_period_start,train_period_end)
ecf2 = EconomicCalendarFilter(ect2.get_df())
psf2 = PipSpreadFilter(train_backtesting_data) 
tdf2 = TimeOfDayFilter()

training_filters = [ecf2, psf2, tdf2]

its2 = ExhaustiveSearch(combination)
its2.trigger_blocks = trigger_block_func(train_signalling_data)

its2.stop_tool = stop_tool
its2.filters = training_filters


backtest_result = None

with open(directory+filename,'rb') as f:
	backtest_result = pickle.load(f)
	
backtest_result_sub = backtest_result
backtest_result_sub = backtest_result_sub[backtest_result_sub['N'] > 50]
backtest_result_sub = backtest_result_sub[(backtest_result_sub['ratio'] >= 0.48) & (backtest_result_sub['ratio'] >= 0.51)]


train_signals = its2.infer(train_signalling_data,backtest_result_sub)
#pdb.set_trace()
sshield = SignalShield(train_signalling_data)
training_signals = sshield.get_signals(train_signals)

btc_train = BackTesterCandles(train_backtesting_data)
training_results = btc_train.perform(training_signals)

#pdb.set_trace()
trade_inspector_model = TradeInspectorModel(train_signalling_data)
trade_inspector_model.create_model()
model = trade_inspector_model.model
X = trade_inspector_model.preprocess_x(training_signals)
Y = trade_inspector_model.preprocess_y(training_results)

pdb.set_trace() 
model.fit(X,Y, epochs=25)

#pdb.set_trace()
#print('test model id')




def indexer_ai(y_pred):
	return ~(y_pred[:,1] == 1)



datatool.start_date = test_period_start
datatool.end_date = test_period_end

dbf.stopwatch('fetch test candles')
datatool.read_data_from_currencies(currencies)
later_signalling_data = datatool.get_trade_signalling_data()

dbf.stopwatch('fetch test candles')

datatool.backtesting = True 
dbf.stopwatch('fetch bt test candles')
datatool.read_data_from_currencies(currencies)
later_backtesting_data = datatool.get_trade_signalling_data()

dbf.stopwatch('fetch bt test candles')



ect3 = EconomicCalendarTool(test_period_start,test_period_end)
ecf3 = EconomicCalendarFilter(ect3.get_df())
psf3 = PipSpreadFilter(later_backtesting_data) 
tdf3 = TimeOfDayFilter()



testing_filters = [ecf3,psf3,tdf3]

its2.trigger_blocks = trigger_block_func(later_signalling_data)
its2.filters = testing_filters 



def try_suggestion(suggestion):
	
	
	
	these_signals = its2.infer(later_signalling_data,suggestion)
	
	sshield = SignalShield(later_signalling_data)
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
	
	ai_filter = AIInvokeFilter(trade_inspector_model, indexer_ai)
	filtered_signals = ai_filter.filter(filtered_signals)  
	
	
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


print('use backtest_result to get a suggestion then call try_suggestion()')
#pdb.set_trace()

sugg = backtest_result[(backtest_result['ratio'] > 0.6 ) & (backtest_result['N'] > 50)]
try_suggestion(sugg) 





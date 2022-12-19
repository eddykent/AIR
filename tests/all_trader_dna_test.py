
import datetime
import pdb
from collections import Counter
import pickle

# test the setup object and also test its trade signals 
from setups.setup_tools import CandleDataTool, PipStop, ATRStop, RollingExtremeStop
#from setups.custom_setups import Harmony
from setups.trader_dna import *
from utils import ListFileReader, Database
from backtest import BackTesterDatabase, BackTestStatistics, BackTesterCandles
from filters.simple_filters import LambdaSelectFilter

lfr = ListFileReader()


import debugging.functs as dbf

bt_with_db = False
currencies = lfr.read('fx_pairs/currencies.txt')



#setups = [TripleRSIADX, DoubleCCICross, RSI_MACD_STOCH, MACD123, ZeroLagEMA, MACD_DOUBLE_DIV]
setups = [MACD_DOUBLE_DIV] 

datatool = CandleDataTool() 
datatool.start_date = datetime.datetime(2022,5,4)
datatool.end_date = datetime.datetime(2022,9,4)
datatool.instruments = lfr.read('fx_pairs/fx_mains.txt')
datatool.volumes = True
datatool.chart_resolution = 15 #15
dbf.stopwatch('fetch candles')
#datatool.read_data_from_currencies(currencies)
#tsd = datatool.get_trade_signalling_data()
dbf.stopwatch('fetch candles')

#with open('./data/pickles/candles.pkl','wb') as f: 
#	pickle.dump(tsd,f)

with open('./data/pickles/candles.pkl','rb') as f: 
	tsd = pickle.load(f)

signals = [] 

for setup in setups:  
	setup = setup()
	setup.stop_calculator = PipStop(take_profit_pips=30,stop_loss_pips=20)
	#setup.stop_calculator = RollingExtremeStop()
	#try:
	print('trying '+setup.get_name())
	signals += setup.get_setups(tsd)
	#except Exception as e:
		#pdb.set_trace()
		#raise e

#pdb.set_trace()

#bbckrsi = BB_KC_RSI() 
#axemrsi = ADX_EMA_RSI()

import random

#signals1 = bbckrsi.get_setups(tsd) 
#signals2 = axemrsi.get_setups(tsd)
#random.shuffle(signals1)
#random.shuffle(signals2)
#signals = signals1 + signals2 #use when stress testing
#signals = signals1[:2500] + signals2[:2500] 




random.shuffle(signals)



#harmony = Harmony(instruments)
#harmony.orders = [12,13,14,15]
#harmony.timeframe = 30
#signals = harmony.get_setups(start_date,end_date)

#import random
#random.shuffle(signals) 
#signals = signals[:10]
#hablah = FastRSI(instruments)

#signals = signals[9:10]

#signals = hablah.get_setups(start_date,end_date)
#lsf = LambdaSelectFilter(lambda t : t.instrument in ['EUR/USD'])
#signals = lsf.filter(signals)

#now backtest
#use this instead? 
#btp = BackTesterCandles()


#remove when wanting to do stress tests
#pdb.set_trace()
print(f'Number of signals is {len(signals)}')

#bt with db
if bt_with_db:
	cursor = Database(cache=False,commit=False)
	btd = BackTesterDatabase(cursor)

	dbf.stopwatch('backtesting')
	result = btd.perform(signals) #,profit_lock=(0.75,0.5,0)
	#backteststats = BacktestStatistics(...) 
	dbf.stopwatch('backtesting')
else:

	datatool = CandleDataTool() 
	datatool.start_date = datetime.datetime(2022,5,4)
	datatool.end_date = datetime.datetime(2022,9,4)
	datatool.instruments = lfr.read('fx_pairs/fx_mains.txt')
	datatool.volumes = True
	datatool.chart_resolution = 15 #15
	datatool.backtesting = True
	dbf.stopwatch('fetch candles')
	datatool.read_data_from_currencies(currencies)
	tsd2 = datatool.get_trade_signalling_data()
	dbf.stopwatch('fetch candles')

	btc = BackTesterCandles(tsd2)
	dbf.stopwatch('backtesting')
	
	result = btc.perform(signals) #,profit_lock=(0.75,0.5,0)
	#backteststats = BacktestStatistics(...) 
	dbf.stopwatch('backtesting')


with open('data/pickles/backtestdata.pkl','wb') as f:
	pickle.dump((tsd,signals,result),f)

bts = BackTestStatistics(tsd, signals, result)
some_result = bts.calculate() #todo! pass query params


statuses = [r.result_status for r in result]
cc = Counter(statuses)

print(cc)
#print(result)











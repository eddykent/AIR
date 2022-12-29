
import datetime
import pdb
from collections import Counter
import pickle

# test the setup object and also test its trade signals 
from setups.setup_tools import CandleDataTool, PipStop, ATRStop, RollingExtremeStop
#from setups.custom_setups import Harmony
from setups.trade_pro import *
from utils import ListFileReader, Database
from backtest import BackTesterDatabase, BackTestStatistics
from filters.simple_filters import LambdaSelectFilter

lfr = ListFileReader()


import debugging.functs as dbf


currencies = lfr.read('fx_pairs/currencies.txt')



setups = [MACD_MFT, RSIS_EMA_X, RSIS_EMA_1, CMF_MACD_ATR, ENGULFING, SIMPLE_MONEY]
#setups = [MACD_MFT] #[RSIS_EMA_X, ENGULFING, CMF_MACD_ATR] #highest winrate ones

datatool = CandleDataTool() 
datatool.start_date = datetime.datetime(2022,5,4)
datatool.end_date = datetime.datetime(2022,9,4)
datatool.instruments = lfr.read('fx_pairs/fx_mains.txt')
datatool.volumes = True
datatool.chart_resolution = 15 #15
dbf.stopwatch('fetch candles')
datatool.read_data_from_currencies(currencies)
tsd = datatool.get_trade_signalling_data()
dbf.stopwatch('fetch candles')


signals = [] 

for setup in setups:  
	setup = setup()
	#setup.stop_calculator = PipStop(take_profit_pips=30,stop_loss_pips=20)
	setup.stop_calculator = RollingExtremeStop()
	#try:
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
cursor = Database(cache=False,commit=False)
btd = BackTesterDatabase(cursor)


datatool2 = CandleDataTool() 
datatool2.start_date = datetime.datetime(2022,5,4)
datatool2.end_date = datetime.datetime(2022,9,4)
datatool2.instruments = lfr.read('fx_pairs/fx_mains.txt')
datatool2.volumes = True
datatool2.backtesting = True
datatool2.chart_resolution = 15 #15
dbf.stopwatch('fetch backtesting data')
datatool2.read_data_from_currencies(currencies)
bsd = datatool2.get_trade_signalling_data()
dbf.stopwatch('fetch backtesting data')

#use this instead? 
btc = BackTesterCandles(bsd)



 #remove when wanting to do stress tests
#pdb.set_trace()
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











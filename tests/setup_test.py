
import datetime
import pdb
from collections import Counter
import pickle

# test the setup object and also test its trade signals 
from setups.setup_tools import CandleDataTool, PipStop, ATRStop
#from setups.setups1 import BB_KC_RSI, ADX_EMA_RSI, HA_VWAP_RSI_DIVERGENCE
#from setups.custom_setups import Harmony
#from setups.collected_setups import Harmony 
#from setups.simple_setups import *
#from setups.trade_pro import *
#from setups.trader_dna import *
from setups.trading_rush import *
from utils import ListFileReader, Database
from backtest import BackTesterDatabase, BackTestStatistics
from filters.simple_filters import LambdaSelectFilter

from charting.chart_viewer import PlotlyChartPainter
lfr = ListFileReader()


import debugging.functs as dbf


currencies = lfr.read('fx_pairs/currencies.txt')



#bbckrsi = BB_KC_RSI() 
#axemrsi = ADX_EMA_RSI()


datatool = CandleDataTool() 
#datatool.start_date = datetime.datetime(2022,10,3)
#datatool.end_date = datetime.datetime(2022,12,16)
datatool.start_date = datetime.datetime(2022,12,16)
datatool.end_date = datetime.datetime(2022,12,23)
datatool.instruments = lfr.read('fx_pairs/fx_mains.txt')
datatool.volumes = True
#datatool.ask_candles = True
datatool.chart_resolution = 15
#datatool.candle_offset = 15
dbf.stopwatch('fetch candles')
datatool.read_data_from_currencies(currencies)
tsd = datatool.get_trade_signalling_data()
dbf.stopwatch('fetch candles')
#
#with open('./data/pickles/setup_test_candles.plk','wb') as fh:
#	pickle.dump(tsd,fh)
#
#with open('./data/pickles/setup_test_candles.pkl','rb') as fh:
#	tsd = pickle.load(fh) #15m candles

#pdb.set_trace()

#fxss = BollingerBandsRSISetup() #MACD_MFT()
#fxss = TripleRSIADX()
#fxss = ICHIMOKU() #from trading_rush
#fxss = RSIS_EMA_X() 
#signals = mrffx.get_setups(start_date,end_date) #+ axemrsi.get_setups(start_date,end_date)
#msda = HA_VWAP_RSI_DIVERGENCE()
#msda.stop_calculator = PipStop(take_profit_pips=30,stop_loss_pips=20)
fxss.stop_calculator = ATRStop()
#fxss.stop_calculator = PipStop(take_profit_pips=30,stop_loss_pips=20)


#from indicators.momentum import MACD 
#macd = MACD(11,12,3)
#tt = macd.title()
#pdb.set_trace()

signals = fxss.get_setups(tsd)

trade_setup_view = fxss.draw(tsd,instrument='GBP/USD')
#check signals here 
trade_setup_view.signals(signals)


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



# #remove when wanting to do stress tests
#dbf.stopwatch('backtesting')
result = btd.perform(signals) #,profit_lock=(0.75,0.5,0)
##backteststats = BacktestStatistics(...) 
#dbf.stopwatch('backtesting')

#pdb.set_trace()
trade_setup_view.backtest(signals, result)

pcp = PlotlyChartPainter()
pcp.paint(trade_setup_view.charts['candlesticks'])
pcp.show()


bts = BackTestStatistics(tsd, signals, result)
bts.set_exchange_rate_tool()
full_results = bts.calculate() #pass query params


#statuses = [r.result_status for r in result]
#cc = Counter(statuses)

#print(cc)
#print(result)











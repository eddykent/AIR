
import datetime
import time
import pdb
from collections import Counter
import pickle 

# test the setup object and also test its trade signals 
from setups.trade_setup import CandleDataTool, PipStop
from setups.setups1 import BB_KC_RSI, ADX_EMA_RSI, HA_VWAP_RSI_DIVERGENCE
from setups.custom_setups import Harmony
from setups.simple_setups import *
from utils import ListFileReader, Database
from backtest import BackTesterDatabase, BackTesterCandles
from filters.simple_filters import LambdaSelectFilter

lfr = ListFileReader()


currencies = lfr.read('fx_pairs/currencies.txt')



#bbckrsi = BB_KC_RSI() 
#axemrsi = ADX_EMA_RSI()

signals = []

#datatool = CandleDataTool() 
#datatool.start_date = datetime.datetime(2022,6,4)
#datatool.end_date = datetime.datetime(2022,9,4)
#datatool.instruments = lfr.read('fx_pairs/fx_mains.txt')
#datatool.volumes = True
#datatool.read_data_from_currencies(currencies)
#tsd = datatool.get_trade_signalling_data()
#
#fxss = ForexSignalsCandles() 
##signals = mrffx.get_setups(start_date,end_date) #+ axemrsi.get_setups(start_date,end_date)
##msda = HA_VWAP_RSI_DIVERGENCE()
##msda.stop_calculator = PipStop(take_profit_pips=30,stop_loss_pips=20)
#signals = fxss.get_setups(tsd)
#with open('data/pickles/signals_11Oct2022.pkl','wb') as f:
#	pickle.dump(signals,f)

with open('data/pickles/signals_11Oct2022.pkl','rb') as f:
	signals = pickle.load(f)


#bbckrsi = BB_KC_RSI() 
#axemrsi = ADX_EMA_RSI()
#signals1 = bbckrsi.get_setups(tsd) 
#signals2 = axemrsi.get_setups(tsd)
#random.shuffle(signals1)
#random.shuffle(signals2)
#signals = signals1 + signals2 #use when stress testing
#signals = signals1[:2500] + signals2[:2500] 





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
all_dates = [s.the_date for s in signals]
bt_start_date = min(all_dates) - datetime.timedelta(days=4)
bt_end_date = max(all_dates) + datetime.timedelta(days=4)

btdatatool = CandleDataTool() 
btdatatool.start_date = datetime.datetime(2022,6,4)
btdatatool.end_date = datetime.datetime(2022,9,4)
btdatatool.instruments = lfr.read('fx_pairs/fx_mains.txt')
btdatatool.chart_resolution = 15 

#gct = time.time() 
#btdatatool.ask_candles = False 
#btdatatool.read_data_from_currencies(currencies)
#btsd_bid = btdatatool.get_trade_signalling_data()
#
#btdatatool.ask_candles = True 
#btdatatool.read_data_from_currencies(currencies)
#btsd_ask = btdatatool.get_trade_signalling_data()
#gcttt = time.time() - gct 
#
#print("Time taken to get bid & ask candles = "+str(gcttt))

btdatatool.backtesting = True
fctt = time.time() 
btdatatool.read_data_from_currencies(currencies)
btsd = btdatatool.get_trade_signalling_data()
print("Time taken to get full candles = "+str(time.time() - fctt))


btc = BackTesterCandles(btsd)
#btc.set_profit_lock(profit_lock=(0.75,0.5,0))

#remove when wanting to do stress tests
stt = time.time() 
result1 = btc.perform(signals)
ttt = time.time() - stt
print('Time taken for backtest np candles = '+str(ttt))
#backteststats = BacktestStatistics(...) 

statuses1 = [r.result_status for r in result1]
cc1 = Counter(statuses1)

cur = Database(commit=False,cache=False)

btd = BackTesterDatabase(cur)

#btd.set_profit_lock(profit_lock=(0.75,0.5,0))

dtt = time.time()
result2 = btd.perform(signals)
ttt = time.time() - dtt
print('Time taken for backtest in database = '+str(ttt))

statuses2 = [r.result_status for r in result2]
cc2 = Counter(statuses2)

print(cc1)
print(cc2)
#print(result)

srs = {s.signal_id : {'s':s} for s in signals}
for r in result1: 
	srs[r.signal_id]['r1'] = r
for r in result2: 
	srs[r.signal_id]['r2'] = r
srs_keys = list(srs.keys())

#problems discovered: 
#exit price wrong from query when hitting tp/sl (it should be the tp/sl!)
#exit happens on weekends at 21:45 for the query version and continues on monday for the np version
#exit SL happens on candle 0 - is this possible in query? (ensure it is always SL not TP, TP index > entry index always)

##need to do profit lock problems too

#srs_diff_keys = [s for s in srs if srs[s]['r1'].result_status != srs[s]['r2'].result_status] #dont worry about weekends 

#wprry about weeekends 
srs_diff_keys = [s for s in srs if srs[s]['r1'].result_status != srs[s]['r2'].result_status and srs[s]['r1'].exit_candle < srs[s]['r2'].exit_candle]

#worry about candles that died right away too 
srs_diff_keys = [s for s in srs if srs[s]['r1'].result_status != srs[s]['r2'].result_status and srs[s]['r1'].exit_candle < srs[s]['r2'].exit_candle and srs[s]['r1'].exit_candle > 0]















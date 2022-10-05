
import datetime
import pdb
from collections import Counter
# test the setup object and also test its trade signals 
from setups.trade_setup import CandleDataTool
from setups.setups1 import BB_KC_RSI, ADX_EMA_RSI, HA_VWAP_RSI_DIVERGENCE
from setups.custom_setups import Harmony
from setups.simple_setups import ForexSignalsAnchorBar, MACD_EMA_SR, FastRSI, MeanReversionFFXS, MediumScalpDaviddAnthony
from utils import ListFileReader, Database
from backtest import BackTesterDatabase
from filters.simple_filters import LambdaSelectFilter

lfr = ListFileReader()


currencies = lfr.read('fx_pairs/currencies.txt')



#bbckrsi = BB_KC_RSI(instruments) 
#axemrsi = ADX_EMA_RSI(instruments)
datatool = CandleDataTool() 
datatool.start_date = datetime.datetime(2022,6,4)
datatool.end_date = datetime.datetime(2022,7,21)
datatool.instruments = lfr.read('fx_pairs/fx_mains.txt')
datatool.read_data_from_currencies(currencies)
tsd = datatool.get_trade_signalling_data()



#mrffx = MeanReversionFFXS(instruments) 
#signals = mrffx.get_setups(start_date,end_date) #+ axemrsi.get_setups(start_date,end_date)
msda = HA_VWAP_RSI_DIVERGENCE()
#msda.stop_calculator = PipStop(take_profit_pips=30,stop_loss_pips=20)
signals = msda.get_setups(tsd)



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
lsf = LambdaSelectFilter(lambda t : t.instrument in ['EUR/USD'])
signals = lsf.filter(signals)

#now backtest
cursor = Database(cache=False,commit=False)
btd = BackTesterDatabase(cursor)
#pdb.set_trace()
result = btd.perform(signals)
statuses = [r.result_status for r in result]
cc = Counter(statuses)

print(cc)
#print(result)

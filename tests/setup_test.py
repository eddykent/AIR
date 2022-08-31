
import datetime
import pdb
from collections import Counter
# test the setup object and also test its trade signals 

from setups.setups1 import BB_KC_RSI, ADX_EMA_RSI, HA_VWAP_RSI_DIVERGENCE
from setups.custom_setups import Harmony
from setups.simple_setups import ForexSignalsAnchorBar, MACD_EMA_SR
from utils import ListFileReader, Database
from backtest import BackTesterDatabase

lfr = ListFileReader()


start_date = datetime.datetime(2021,6,4)
end_date = datetime.datetime(2022,7,21)
instruments = lfr.read('fx_pairs/fx_mains.txt')

#bbckrsi = BB_KC_RSI(instruments) 
#axemrsi = ADX_EMA_RSI(instruments)
#signals = bbckrsi.get_setups(start_date,end_date) + axemrsi.get_setups(start_date,end_date)

#harmony = Harmony(instruments)
#harmony.orders = [12,13,14,15]
#harmony.timeframe = 30
#signals = harmony.get_setups(start_date,end_date)


hablah = MACD_EMA_SR(instruments)


#signals = signals[9:10]

signals = hablah.get_setups(start_date,end_date)


#now backtest
cursor = Database(cache=False,commit=False)
btd = BackTesterDatabase(cursor)
#pdb.set_trace()
result = btd.perform(signals)
statuses = [r.result_status for r in result]
cc = Counter(statuses)

print(cc)
#print(result)

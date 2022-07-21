
import datetime
import pdb
from collections import Counter
# test the setup object and also test its trade signals 

#from setups.setups1 import BB_KC_RSI, ADX_EMA_RSI
from setups.custom_setups import Harmony
from utils import ListFileReader, Database
from backtest import BackTesterDatabase

lfr = ListFileReader()


start_date = datetime.datetime(2022,4,1)
end_date = datetime.datetime(2022,7,8)
instruments = lfr.read('fx_pairs/fx_mains.txt')

#bbckrsi = BB_KC_RSI(instruments) 
#axemrsi = ADX_EMA_RSI(instruments)
#signals = bbckrsi.get_setups(start_date,end_date) + axemrsi.get_setups(start_date,end_date)

harmony = Harmony(instruments)
harmony.orders = [6,7,8]
harmony.timeframe = 15
signals = harmony.get_setups(start_date,end_date)


#now backtest
cursor = Database(cache=False,commit=False)
btd = BackTesterDatabase(cursor)
result = btd.perform(signals)
statuses = [r.result_status for r in result]
cc = Counter(statuses)
pdb.set_trace()
print(cc)
print(result)

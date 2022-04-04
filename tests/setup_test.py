
import datetime
import pdb
# test the setup object and also test its trade signals 

from setups.setups1 import BB_KC_RSI
from utils import ListFileReader, Database
from backtest import BackTesterDatabase

lfr = ListFileReader()


start_date = datetime.datetime(2022,1,11)
end_date = datetime.datetime(2022,1,20)
instruments = lfr.read('fx_pairs/fx_mains.txt')

bbckrsi = BB_KC_RSI(instruments)
signals = bbckrsi.get_setups(start_date,end_date)



#now backtest
cursor = Database(cache=False,commit=False)
btd = BackTesterDatabase(cursor)
result = btd.perform(signals)
pdb.set_trace()
print(len(result))

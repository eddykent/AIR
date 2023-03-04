
import datetime
import pdb
from collections import Counter
import numpy as np
import time
# test the setup object and also test its trade signals 

from data.tools.cursor import Database, DataComposer

from data.base.candles import CandleDataTool, PartialCandleDataTool

from setups.setups1 import BB_KC_RSI, ADX_EMA_RSI, HA_VWAP_RSI_DIVERGENCE
from setups.custom_setups import Harmony
from setups.simple_setups import ForexSignalsAnchorBar

#from filters.simple_filters import ForexSignalsAnchorBarFilter, RSIFilter
from filters.indicator_based import RSIFilterSlow, RSIFilter, ADXFilter
from filters.time_based import EconomicCalendarFilter
#from filters.meta_based import ClientSentimentFilter


from utils import ListFileReader
from backtest import BackTesterDatabase

lfr = ListFileReader()



start_date = datetime.datetime(2022,7,4,14,0)
end_date = datetime.datetime(2022,7,21,14,0)
instruments = lfr.read('fx_pairs/fx_mains.txt')
currencies = lfr.read('fx_pairs/currencies.txt')

datatool = CandleDataTool()
datatool.start_date = start_date
datatool.end_date = end_date
datatool.instruments = instruments
#datatool.timeframe = 15
#datatool.volumes = True
datatool.read_data_from_currencies(currencies)
tsd = datatool.get_trade_signalling_data()


hablah = ADX_EMA_RSI()
signals = hablah.get_setups(tsd) #do same for filters?

import random
random.shuffle(signals)
#signals = signals[:12]


#fsf = ForexSignalsAnchorBarFilter(filter_candle_streams,available_instruments,filter_resolution)
#ecf = EconomicCalendarFilter()
filter_data_tool = CandleDataTool()
filter_data_tool.start_date = start_date
filter_data_tool.end_date = end_date
filter_data_tool.instruments = instruments
filter_data_tool.chart_resolution  = 240 #filter_resolution = 60
filter_data_tool.candle_offset = 120
filter_data_tool.read_data_from_currencies(currencies)
fsd = filter_data_tool.get_trade_signalling_data()


tt = time.time()
pcdt = PartialCandleDataTool()
pcdt.instruments = instruments
pcdt.chart_resolution  = 60 #filter_resolution = 60
pcdt.candle_offset = 0
pcs = pcdt.read_data_from_currencies(currencies,[ts.the_date for ts in signals])

print("total partial query time for " + str(len(signals)) + " signals = " + str(time.time() - tt))

pdb.set_trace()

#rsf = RSIFilterSlow(filter_data_tool)
rsf = ADXFilter(fsd,pcs)


filtered_signals  = rsf.filter(signals)
cursor = Database(cache=False,commit=False)
#now backtest
btd = BackTesterDatabase(cursor)
#pdb.set_trace()

def show_result_summary(sigs):
	result = btd.perform(sigs)
	statuses = [r.result_status for r in result]
	cc = Counter(statuses)
	print(cc)

print('original:')
show_result_summary(signals)

print('filtered:')
show_result_summary(filtered_signals)
#print(result)








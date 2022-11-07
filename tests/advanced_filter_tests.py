
import datetime
import pdb
from collections import Counter
import numpy as np
# test the setup object and also test its trade signals 

from setups.setups1 import BB_KC_RSI, ADX_EMA_RSI, HA_VWAP_RSI_DIVERGENCE
from setups.custom_setups import Harmony
from setups.simple_setups import ForexSignalsAnchorBar, MeanReversionFFXS
from setups.trade_setup import CandleDataTool
from filters.trade_filter import PartialCandleDataTool

from filters.simple_filters import ForexSignalsAnchorBarFilter
from filters.time_based import EconomicCalendarFilter
from filters.meta_based import ClientSentimentFilter, FlatCorrelationFilter, CurrencyStrengthFilter, CurrencyStrengthOperator, CorrelationFilter

from indicators.moving_average import EMA 
from indicators.reversal import RSI

from utils import ListFileReader, Database, DataComposer
from backtest import BackTesterDatabase

lfr = ListFileReader()


start_date = datetime.datetime(2022,10,1,8,0)
end_date = datetime.datetime(2022,10,13,18,0)
instruments = lfr.read('fx_pairs/fx_mains.txt')
currencies = lfr.read('fx_pairs/currencies.txt')


cdt = CandleDataTool()
cdt.start_date = start_date
cdt.end_date = end_date
cdt.instruments = instruments
cdt.chart_resolution = 15
cdt.grace_period = 50 
cdt.volumes = True
cdt.read_data_from_currencies(currencies)
candle_data = cdt.get_trade_signalling_data()


hablah = ADX_EMA_RSI()
signals = hablah.get_setups(candle_data) #do same for filters?


cdt2 = CandleDataTool()
cdt2.start_date = start_date
cdt2.end_date = end_date
cdt2.instruments = instruments
cdt2.chart_resolution = 240
cdt2.candle_offset = 120
cdt2.grace_period = 50 
cdt2.volumes = True
cdt2.read_data_from_currencies(currencies)
filter_data = cdt2.get_trade_signalling_data()

pcdt = PartialCandleDataTool()
pcdt.instruments = instruments
pcdt.chart_resolution = 240
pcdt.candle_offset = 120
pcdt.volumes = True
partial_candles = pcdt.read_data_from_currencies(currencies,[ts.the_date for ts in signals])

#pdb.set_trace()

cso = CurrencyStrengthOperator(instruments,currencies)
ema = EMA() 
ema.period = 5
rsi = RSI()
csf = CurrencyStrengthFilter(rsi,cso,ema,filter_data, partial_candles)
crsf = CorrelationFilter(None,filter_data,partial_candles)
clsf = ClientSentimentFilter(filter_data, partial_candles)

filtered_signals  = csf.filter(signals)
filtered_signals = clsf.filter(filtered_signals)
filtered_signals = crsf.filter(filtered_signals)
print(str(len(signals)) + ' -> ' + str(len(filtered_signals)))

cursor = Database(cache=False,commit=False)
#now backtest
btd = BackTesterDatabase(cursor)
#pdb.set_trace()

def show_result_summary(sigs):
	result = btd.perform(sigs)
	statuses = [r.result_status for r in result]
	cc = Counter(statuses)
	print(cc)
	return result

print('original:')
results = show_result_summary(signals)

print('filtered:')
show_result_summary(filtered_signals)
#print(result)

#corrs = np.array(csf._correlation_reports)
#print(np.mean(corrs,axis=0))








import datetime
import pdb
from collections import Counter
import numpy as np
# test the setup object and also test its trade signals 

from setups.setups1 import BB_KC_RSI, ADX_EMA_RSI, HA_VWAP_RSI_DIVERGENCE
from setups.custom_setups import Harmony
from setups.simple_setups import ForexSignalsAnchorBar

from filters.simple_filters import ForexSignalsAnchorBarFilter, RSIFilter
from filters.time_based import EconomicCalendarFilter
from filters.meta_based import ClientSentimentFilter


from utils import ListFileReader, Database, DataComposer
from backtest import BackTesterDatabase

lfr = ListFileReader()


start_date = datetime.datetime(2022,7,4,14,0)
end_date = datetime.datetime(2022,7,21,14,0)
instruments = lfr.read('fx_pairs/fx_mains.txt')
currencies = lfr.read('fx_pairs/currencies.txt')

hablah = ForexSignalsAnchorBar(instruments)

signals = hablah.get_setups(start_date,end_date) #do same for filters?


tdelta = end_date - start_date
days_back = tdelta.days + 10 

###add filter here!
filter_candles = None 
volumes = True
available_instruments = None 

#chart resolution not working 
with Database(cache=False,commit=False) as cursor:
	composer = DataComposer(cursor,True) #.candles(params).call()...
	composer.call('get_candles'+('_volumes_' if volumes else '_') + 'from_currencies',{
		'currencies':currencies,
		'this_date':end_date,
		'days_back':days_back,
		'chart_resolution':240,
		'candle_offset':120
	})
	#pdb.set_trace()
	candle_result = composer.result(as_json=True)
	filter_candles = DataComposer.as_candles_volumes(candle_result,instruments) if volumes else DataComposer.as_candles(candle_result,instruments)
	filter_candle_streams = [filter_candles[instr] for instr in instruments if filter_candles.get(instr)]
	available_instruments = [instr for instr in instruments if filter_candles.get(instr)]

#pdb.set_trace()
#
#query = ''
#with open('queries/candle_stick_selector.sql','r') as f:
#	query = f.read()
#
#params = {
#	'chart_resolution':60,
#	'the_date':end_date,
#	'candle_offset':0,
#	'hour':end_date.hour,
#	'days_back':days_back,
#	'currencies':currencies
#}
#cursor.execute(query,params)

#candlestreams = cursor.fetchcandles(instruments)
#filter_candle_block = [candlestreams[fx] for fx in instruments if fx in candlestreams]
#available_instruments = [fx for fx in instruments if fx in candlestreams]


#fsf = ForexSignalsAnchorBarFilter(filter_candle_streams,available_instruments,240)
#ecf = EconomicCalendarFilter()

rsf = RSIFilter(filter_candle_streams,available_instruments,240)
#csf.set_chart_resolution(240)

filtered_signals  = rsf.filter(signals)
cursor = Database(cache=False,commit=False)
#now backtest
btd = BackTesterDatabase(cursor)
pdb.set_trace()

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








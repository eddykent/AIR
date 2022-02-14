import datetime
import psycopg2
import numpy as np

from statsmodels.tsa.arima.model import ARIMA 
from plotly import graph_objects as chart

import pdb

from utils import ListFileReader, SplitAndPrepare, Configuration

config = Configuration()
con = psycopg2.connect(config.database_connection_string())
cur = con.cursor()

lft = ListFileReader()
currencies = lft.read('fx_pairs/currencies.txt')

the_date = datetime.datetime(2022,1,20,14,0)


query = ''
with open('queries/candles_and_indicators.sql','r') as f:
	query = f.read()

params = config.get_default_parameters()
params.update({
	'currencies':currencies,
	'the_date':the_date,
	'hour':the_date.hour,
	'chart_resolution':60,
	'days_back':100,
	'normalisation_window':500
})

cur.execute(query,params)
all_candles = cur.fetchall()
all_candles.reverse() #put into asc order since the query returns desc 

sap = SplitAndPrepare()
sap.sequential = False
sap.validate_size = 10
sap.test_size = 10
sap.instruments = ['EUR/USD']
sap.features = ['normed_open_price','normed_high_price','normed_low_price','normed_close_price','ema50','ema100','ema200','macd_line','macd_signal','the_date']
train, validate,test = sap.prepare(all_candles)

x=[candle[0][-1] for candle in train]
candlestick_chart_data = chart.Candlestick(
	#x=x,
	open=[candle[0][0] for candle in train],
	high=[candle[0][1] for candle in train],
	low=[candle[0][2] for candle in train],
	close=[candle[0][3] for candle in train],
	name='EUR/USD'
)

ema50 = np.array([candle[0][4] for candle in train]).astype(np.float64)
ema100 = np.array([candle[0][5] for candle in train]).astype(np.float64)
ema200 = np.array([candle[0][6] for candle in train]).astype(np.float64)
macd_line = np.array([candle[0][7] for candle in train]).astype(np.float64)
pdb.set_trace()
macd_signal = np.array([candle[0][8] for candle in train]).astype(np.float64)

ema50_trace = chart.Scatter(y=ema50,mode='lines',name='ema50')
ema100_trace = chart.Scatter(y=ema100,mode='lines',name='ema100')
ema200_trace = chart.Scatter(y=ema200,mode='lines',name='ema200')

macd_line_trace = chart.Scatter(y=macd_line,mode='lines',name='macd')
macd_signal_trace = chart.Scatter(y=macd_signal,mode='lines',name='signal')


fig = chart.Figure(data=[candlestick_chart_data])
#fig.add_trace(ema50_trace)
fig.add_trace(ema100_trace)
#fig.add_trace(ema200_trace)
#fig = chart.Figure(data=[macd_line_trace])
#fig.add_trace(macd_signal_trace)

fig.show()
pdb.set_trace()

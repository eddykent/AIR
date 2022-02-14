import datetime
import psycopg2
import numpy as np
import sys

from statsmodels.tsa.arima.model import ARIMA 
from plotly import graph_objects as chart

import pdb

from utils import ListFileReader, SplitAndPrepare, Configuration

config = Configuration()
con = psycopg2.connect(config.database_connection_string())
cur = con.cursor()

from trade_schedule import TradeSchedule,Trade 

lft = ListFileReader()
currencies = lft.read('fx_pairs/currencies.txt')
fx_pairs = lft.read('fx_pairs/fx_mains.txt')

the_date = datetime.datetime(2022,1,17,12,0)

def rmse(y1,y2):
	return (((y1-y2)**2).mean())*0.5

query = ''
with open('queries/candles_with_percent_change.sql','r') as f:
	query = f.read()

params = config.get_default_parameters()
params.update({
	'currencies':currencies,
	'the_date':the_date,
	'hour':the_date.hour,
	'chart_resolution':240,
	'days_back':200,
	'normalisation_window':250
})

cur.execute(query,params)
all_candles = cur.fetchall()
all_candles.reverse() #put into asc order since the query returns desc 

sap = SplitAndPrepare()
sap.sequential = False
sap.validation_size = 0
sap.test_size = 10
#sap.features = ['close_price'] #only care about close prices for ARIMA -- nah, we want percent change
sap.features = ['percent_change']


def direction(pcs):
	s = sum(pcs[:4])
	d = 'None'
	if s > 0.01:
		d = 'BUY'
	if s < -0.01:
		d = 'SELL'
	return d

def run_arima_for(pair):
	best_p = 0 
	best_q = 0
	best_d = 0
	best_rmse = 99999999
	best_y_hat = []
	sap.instruments = [pair]
	tries = []
	train,validate,test = sap.prepare(all_candles,np.ravel)#dump out all sequences as a flat list 
	train = train[1:] #first value will be nan for percent change 
	arima_failures = 0
	#pdb.set_trace()
	for p in range(0,10):
		for q in range(0,10):
			for d in range(0,4):
				print('%(pair)s - ARIMA(%(p)s,%(d)s,%(q)s)...' % {'p':p,'d':d,'q':q,'pair':pair},end='\r')
				model = None
				model_fit = None
				try:
					model = ARIMA(train[20:],order=(p,d,q))
					model_fit = model.fit()
				except:
					print('%(pair)s - ARIMA(%(p)s,%(d)s,%(q)s)... FAILED' % {'p':p,'d':d,'q':q,'pair':pair})
					arima_failures += 1
					continue
				y_hat = model_fit.forecast(steps=len(test))# for p in range(0,10)
				obj = rmse(y_hat,test)
				print('%(pair)s - ARIMA(%(p)s,%(d)s,%(q)s)... MSE = %(obj)s' % {'obj':obj,'p':p,'d':d,'q':q,'pair':pair})
				if obj < best_rmse:
					(best_p,best_q,best_d) = (p,q,d)
					best_rmse = obj
					best_y_hat = y_hat
				tries.append({'pair':pair,'arima':(p,d,q),'predict':y_hat,'rmse':obj,'fails':arima_failures})
	
	return tries

trades = []
arima_info = []


for pair in fx_pairs:
	tries = run_arima_for(pair)
	best = sorted(tries, key=lambda t:t['rmse'])[0]
	direct = direction(best['predict'])
	trades.append((Trade(pair,direct,None),best['rmse']))
	arima_info.append(best)


trades = sorted(trades,key=lambda t:t[1]) #sort by their root mean squared errors
ts = TradeSchedule(the_date)
ts.trades = [t[0] for t in trades]
result = ts.run_test(cur)
ps = [print(r) for r in result]
pdb.set_trace()










import datetime
from statsmodels.tsa.statespace.varmax import VARMAX
import psycopg2
import numpy as np

import pdb

import tensorflow as tf
from tensorflow import keras

import pickle


from configuration import Configuration
from data.tools.cursor import Database

#hack to allow our test to import from parent directory
from sys import path
path.append('..')

from trade_schedule import TradeSchedule
from utils import ListFileReader


lfr = ListFileReader()
currencies = lfr.read('fx_pairs/currencies.txt')

query = ''
with open('queries/currency_strength_rsi.sql','r') as f:
	query = f.read() #stochastic seems to give weird strength values!

#pdb.set_trace()
config = Configuration()
#con = psycopg2.connect(config.database_connection_string())
#cur = con.cursor()
cur = Database()

the_date = datetime.datetime(2022,1,20,12,0)

candle_length = 240
n_candles_per_day = (24*60) // candle_length

#gets = ['rank','ranked_average']
gets = ['rank']


params = {
	'the_date':the_date.date(),
	'hour':the_date.hour,
	'days_back':1000, 
	'currencies':currencies,
	'chart_resolution':candle_length, # 1h chart
	'diff':6, #check what it was 6*4 hours ago 
	'relative_strength_index_period':14,
	'stochastic_oscillator_period':14,
	'stochastic_oscillator_fast_d':3,
	'ema_window':6 #average over 4 candles
}


#currencies = ['AUD','CAD','CHF','EUR','GBP','NZD','JPY','USD']
raw_currency_data =[]


cur.execute(query,params)
raw_currency_data = cur.fetchall()
#with open('pickles/raw_currency_data.pickle','wb') as f:
#	pickle.dump(raw_currency_data, f)
#with open('pickles/raw_currency_data.pickle','rb') as f:
#	raw_currency_data = pickle.load(f)
#cur.close()
#con.close() #close connection after!

parameters = config.get_default_parameters()
parameters.update(params)


raw_indicator_data = [] 


currency_data_dicts = [[cd[2][k] for k in currencies] for cd in raw_currency_data] #4h chart - get rid of intermediate between each 4h
movements = [[[c[g] for g in gets] for c in cur_data_dict] for cur_data_dict in currency_data_dicts]

currency_data = [[x for xs in movement for x in xs] for movement in movements]

#chop currency_data a bit 
#currency_data = currency_data[::2]


currs = np.array(currency_data)

sequence_len = 64
n_sequences = 500

currs=  currs[::-1] #reverse the list 
subsequences = [currs[i: i + sequence_len] for i in range(0,len(currs),n_candles_per_day)]
subsequences = subsequences[:n_sequences+1]
subsequences = [ss[::-1] for ss in subsequences[::-1]] #put em back to their correct way round 

train = subsequences[0:-1]
test = subsequences[-1:] #last candle 

train_x = [ss[:-1] for ss in train]
train_y = [t[0] for t in [[s[::len(gets)] for s in ss[-1:]] for ss in train]] #select only the actual movement not the averages

test_x =  [ss[:-1] for ss in test]
test_y =  [t[0] for t in [[s[::len(gets)] for s in ss[-1:]] for ss in test]]

#pdb.set_trace()
reg = keras.regularizers.l1_l2(0.05, 0.05)

lstm_hidden_units = 32


#make a simple model 
data_input = keras.layers.Input(shape=(sequence_len-1,len(gets)*len(currencies)))
#data_input = keras.layers.BatchNormalization()(data_input) #ok?

#whole seqwuence in dense
#seq = keras.layers.LSTM(lstm_hidden_units, return_sequences=True)(data_input)
#reshape = keras.layers.Reshape(((sequence_len-6)*lstm_hidden_units,))(seq)
#dense = keras.layers.Dense((sequence_len-6)*16 / 2, activation='relu')(reshape)
#dense = keras.layers.Dropout(0.1)(dense)

#seq = keras.layers.LSTM(lstm_hidden_units, return_sequences=False)(data_input)
seq = keras.layers.GRU(lstm_hidden_units,return_sequences=False)(data_input)
dense = keras.layers.Dense(lstm_hidden_units,activation='sigmoid')(seq)
dense = keras.layers.Dropout(0.2)(dense)

dense = keras.layers.Dense(lstm_hidden_units // 2, activation='sigmoid')(dense)
dense = keras.layers.Dropout(0.2)(dense)


#act = keras.layers.ReLU()(de1)
out = keras.layers.Dense(len(currencies))(dense)
#out = keras.layers.ReLU(out)

model = keras.Model(data_input,out)
#model.summary()
adam = keras.optimizers.Adam()

#loss_func = tfr.keras.losses.PairwiseHingeLoss()
loss_func = 'mse'

model.compile(optimizer=adam,loss=loss_func)

#first do a general train - 80 epochs
model.fit(np.array(train_x), np.array(train_y), \
	shuffle=True, \
	epochs=80, batch_size=10, \
	verbose=True,validation_data=(np.array(test_x),np.array(test_y)))

#then specialise  - 20 epochs
model.fit(np.array(train_x), np.array(train_y), \
	shuffle=False, \
	epochs=20, batch_size=10, \
	verbose=True,validation_data=(np.array(test_x),np.array(test_y)))


y_hat = model.predict(np.array(test_x))[0]

y_h = np.array([sorted(y_hat).index(x)+1 for x in y_hat]) # rank numbers 

#lowest = [y_h.index(1), y_h.index(2),y_h.index(3)]
#highest = [y_h.index(8), y_h.index(7), y_h.index(6)]
#
#selection = [\
#	currencies[highest[0]] + '/' + currencies[lowest[0]],\
#	currencies[highest[1]] + '/' + currencies[lowest[0]],\
#	currencies[highest[0]] + '/' + currencies[lowest[1]],\
#	currencies[highest[1]] + '/' + currencies[lowest[1]]\
#]

result_data = {
	'predicted_ranks':y_hat,
	'currencies':currencies
}

ts = TradeSchedule(the_date)
ts.build_from(result_data,'currency_strengths')
result = ts.run_test(cur)
#print('\n'.join(result)) #result is of tuples!
cur.close()
con.close() #close connection after!

pdb.set_trace()
print('worked?')









#dense = keras.layers.Dense(150, activation='relu', kernel_regularizer=reg)(dense)
#dense = keras.layers.Dense(100, activation='relu', kernel_regularizer=reg)(dense)
#seq = keras.layers.LSTM(64, return_sequences=True, activation='relu')(data_input)
#seq = keras.layers.LSTM(64, return_sequences=False)(seq)


#dense = keras.layers.Dense((sequence_len-6)*16 / 2, activation='relu')(dense)
#dense = keras.layers.BatchNormalization()(dense)
#dense = keras.layers.Dropout(0.1)(dense)




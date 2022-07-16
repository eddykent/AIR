import datetime
from statsmodels.tsa.statespace.varmax import VARMAX
import psycopg2
import numpy as np

import pdb

import tensorflow as tf
from tensorflow import keras
from trade_schedule import TradeSchedule

from utils import ListFileReader, Configuration, TimeZipper, SplitAndPrepare

import pickle

#hack to allow our test to import from parent directory
from sys import path
path.append('..')

the_date = datetime.datetime(2022,1,17,12,0) 
lfr = ListFileReader()
currencies = lfr.read('fx_pairs/currencies.txt')
fx_pairs = lfr.read('fx_pairs/fx_mains.txt')
#fx_pairs = ['GBP/USD','EUR/USD','USD/JPY']
#fx_pairs = fx_pairs[5:18]
#fx_pairs = ['GBP/USD']

#fx_y = ['EUR/USD','USD/JPY','GBP/CAD','CAD/CHF','GBP/JPY'] 
fx_y = fx_pairs
#fx_pairs = fx_y


#fx_pairs = fx_pairs[6:16] 

#massive list of all possible parameters 
parameters = {
	'take_profit_factor':6, #movement required (in multiples of average true range) to hit a take profit
	'stop_loss_factor':5, #movement required (in multiples of average true range) to hit a stop loss
	'spread_penalty':3, #penalty added (in multiples of average true range) that change the price at 10pm to account for crazy spread times
	'normalisation_window':200, #where to find max and min values for normalising data to between 0 and 1
	'starting_candle':2,#which 15 minute candle to start from when evaluating trading schedules (to account for computation time)
	'the_date':the_date.date(),#date in which the trade will happen (and all learning is from subsequent candles before etc) 
	'hour':the_date.hour, #the time in which the trade will happen 
	'days_back':1500, #rough estimate of how much data needs to be read to get enough to generate all sequences
	'trade_length_days':1, #the length a trade is expected to last (close the trade if it elapses this time)
	'currencies':currencies, #list of contributing currencies for currency strength and other calculations 
	'chart_resolution':60, #use the 1h chart (15mins, 30mins, 1h and 4h available!) 
	'average_true_range_period':14,
	'relative_strength_index_period':14,
	'stochastic_oscillator_period':14,
	'stochastic_oscillator_fast_d':3,
	'stochastic_oscillator_slow_d':3,
	'macd_slow_period':23,
	'macd_fast_period':12,
	'macd_signal_period':8,
	'custom_sma_period':10, 
	'custom_ema_period':10,
}

#There are lots of keys available in x data, it is up to experimentation to pick the best impacting ones
#
#Note: Anything "normed" will be scaled between 0 and 1 using the normalisation_window paramater. Unless 
#otherwise stated, the moving averages are on normed values to keep them between 0 and 1
#
#AVAILABLE KEYS IN X DATA: 
#open_price, high_price, low_price, close_price
#normed_open_price, normed_high_price, normed_low_price, normed_close_price 
#min_price, max_price
#sma_custom, ema_custom
#sma50, sma100, sma200
#ema50, ema100, ema200
#average_true_range
#relative_strength_index
#stochastic_oscillator_k, stochastic_oscillator_d, stochastic_oscillator_slow_d
#macd_line, macd_signal, normed_macd_line, normed_macd_signal

x_keys = [ #change this for different experimental results! :) 
	#'normed_open_price',
	#'normed_high_price',
	#'normed_low_price',
	#'normed_close_price', #moving averages? eg ema200?
	'average_true_range',
	'relative_strength_index',
	'stochastic_oscillator_d', #k? 
	'stochastic_oscillator_k',
	#'stochastic_oscillator_slow_d',
	'normed_macd_line',
	'normed_macd_signal', #what about the line?
	'ema200',
	'ema_custom'
]

y_keys = ['BUY','SELL']#['BUY','SELL']

##perform database operations to read all the data for this date
#alternatively, unjar a pickle for this test


query_x_values = ''
query_y_values = ''
with open('queries/candles_and_indicators.sql','r') as f:
	query_x_values = f.read()

with open('queries/get_y_data.sql','r') as f:
	query_y_values = f.read()


config = Configuration()
database_connection = psycopg2.connect(config.database_connection_string())
database_cursor = database_connection.cursor()


database_cursor.execute(query_x_values,parameters)
raw_sequence_data = database_cursor.fetchall()

database_cursor.execute(query_y_values,parameters)
raw_result_data = database_cursor.fetchall()

all_raw_data = {
	'x':raw_sequence_data,
	'y':raw_result_data
}

with open('pickles/test_data.pickle','wb') as f:
	pickle.dump(all_raw_data,f)

'''

all_raw_data = {}
with open('pickles/test_data.pickle','rb') as f:
	all_raw_data = pickle.load(f)


raw_sequence_data = all_raw_data['x']
raw_result_data = all_raw_data['y']
'''

tz = TimeZipper()
tz.n_sequences = 1000
tz.x_sequence_lengths = [int(24*1.5)]
Xs, Y = tz.process([raw_sequence_data],raw_result_data)

sap = SplitAndPrepare() 
sap.test_size = 1
sap.validation_size = 0
sap.instruments = fx_pairs
sap.features = x_keys
sap.sequential = True
train_x, validate_x, test_x = sap.prepare(Xs[0]) #we must process each x individually


sap.features = y_keys #['BUY','SELL']
sap.instruments = fx_y
sap.sequential = False
train_y, validate_y, test_y = sap.prepare(Y)



input_shape = (tz.x_sequence_lengths[0],len(fx_pairs),len(x_keys))
output_shape = (len(fx_y),len(y_keys))

#small simple model for testing only
inp = keras.layers.Input(shape=input_shape)
out = keras.layers.Reshape((input_shape[0],input_shape[1]*input_shape[2]))(inp)
#out = keras.layers.GRU(300,return_sequences=True)(out)
#out = keras.layers.PReLU()(out)
#out = keras.layers.Dropout(0.1)(out)
out = keras.layers.LSTM(100,return_sequences=True)(out)
out = keras.layers.Dropout(0.2)(out)
out = keras.layers.GRU(80,return_sequences=False)(out)
out = keras.layers.BatchNormalization()(out)
out = keras.layers.Dropout(0.1)(out)
out = keras.layers.Dense(output_shape[0] * output_shape[1])(out)
out = keras.layers.PReLU()(out)
out = keras.layers.BatchNormalization()(out)
out = keras.layers.Dropout(0.1)(out)
out = keras.layers.Dense(output_shape[0] * output_shape[1], activation='sigmoid')(out)
out = keras.layers.Reshape(output_shape)(out)

mod = keras.Model(inp,out)

model = keras.Model(inp,out)
#model.summary()
adam = keras.optimizers.Adam()
#loss_func = tfr.keras.losses.PairwiseHingeLoss()
loss_func = 'binary_crossentropy'
model.compile(optimizer=adam,loss=loss_func,metrics=['accuracy'])

#first do a general train - 80 epochs
model.fit(train_x, train_y, \
	shuffle=False, \
	epochs=75, batch_size=20, \
	verbose=True,\
	validation_data=(test_x,test_y)
)

model.fit(train_x, train_y, \
	shuffle=False, \
	epochs=25, batch_size=20, \
	verbose=True,\
	validation_data=(test_x,test_y)
)

#model.fit(train_x, train_y, \
#	shuffle=False, \
#	epochs=10, batch_size=20, \
#	verbose=True,\
#	validation_data=(test_x,test_y)
#)

y_hat = model.predict(test_x)[0]

resulting_stuff = {
	'fx_pairs':fx_y,
	'predicted':y_hat > 0.75
}

ts = TradeSchedule(the_date)
ts.build_from(resulting_stuff,'buy_sell_fx_pairs')
result = ts.run_test(database_cursor)

print(result)

database_cursor.close()
database_connection.close()























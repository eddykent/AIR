import datetime
from statsmodels.tsa.statespace.varmax import VARMAX
import psycopg2
import numpy as np

import pdb

import tensorflow as tf
from tensorflow import keras

import pickle

from trade_schedule import TradeSchedule
from utils import ListFileReader, Configuration, Database, TimeZipper, SplitAndPrepare

#TODO: put this into an easy function to create a currency strength filter 

lfr = ListFileReader()
currencies = lfr.read('fx_pairs/currencies.txt')
fx_pairs = lfr.read('fx_pairs/fx_mains.txt')

query = ''
with open('queries/currency_strength_rsi.sql','r') as f:
	query = f.read() #stochastic seems to give weird strength values!

#pdb.set_trace()
config = Configuration()
#con = psycopg2.connect(config.database_connection_string())
#cur = con.cursor()
cur = Database()

the_date = datetime.datetime(2022,2,3,12,0)

candle_length = 240

params = {
	'the_date':the_date.date(),
	'hour':the_date.hour,
	'days_back':600, 
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


parameters = config.get_default_parameters()
parameters.update(params)

query2 = ''
with open('queries/candles_and_indicators.sql','r') as f:
	query2 = f.read()

cur.execute(query2,parameters)
raw_indicator_data = cur.fetchall()


tz = TimeZipper()
tz.x_sequence_lengths = [64,64]
tz.number_of_sequences = 700  + 1 #add one for the step 

#perhaps only get Y for each day ?

Xs,Y = tz.process([raw_indicator_data,raw_currency_data],raw_currency_data)

#we want to predict the NEXT Y, not the current one - we already have that! 
#So lets step accordingly - 
#Xs_stepped = [X[:-1] for X in Xs]
#Y_stepped = Y[1:]

#to_sigmoid_output = lambda x : (np.array(x) / 10.0) - 0.5
to_sigmoid_output = lambda x: x

n_currencies = len(currencies)
zeroand1 = lambda x : np.array(x) / n_currencies

sap_ind = SplitAndPrepare()
sap_ind.features = ['relative_strength_index']
sap_ind.instruments = fx_pairs
sap_ind.validation_size = 0
sap_ind.test_size = 1
sap_ind.sequential = True
train_x1, validate_x1, test_x1 = sap_ind.prepare(Xs[0][:-1]) # we are learning up to what we know which is up to Y[-1]

sap_cs = SplitAndPrepare()
sap_cs.features = ['rank','ranked_average']
sap_cs.instruments = currencies
sap_cs.validation_size = 0
sap_cs.test_size = 1
sap_cs.sequential = True
train_x2, validate_x2, test_x2 = sap_cs.prepare(Xs[1][:-1],zeroand1)

sap_y = SplitAndPrepare()
sap_y.features = ['rank']
sap_y.instruments = currencies
sap_y.validation_size = 0 
sap_y.test_size = 1
sap_y.sequential = False
train_y, validate_y, test_y = sap_y.prepare(Y[1:],zeroand1)

##create the model here and automatically append together all the X info before putting into an LSTM/GRU
inp1 = keras.layers.Input(shape=(tz.x_sequence_lengths[0],len(sap_ind.instruments),len(sap_ind.features) ) )
inp2 = keras.layers.Input(shape=(tz.x_sequence_lengths[1],len(sap_cs.instruments),len(sap_cs.features) ) )

reshape1 = keras.layers.Reshape((tz.x_sequence_lengths[0],len(sap_ind.instruments) * len(sap_ind.features)))(inp1)
reshape2 = keras.layers.Reshape((tz.x_sequence_lengths[1],len(sap_cs.instruments) * len(sap_cs.features)))(inp2)

cat = keras.layers.Concatenate(axis=2)([reshape1,reshape2]) #tz.x_sequence_lengths[0] == tz.x_sequence_lengths[1]!

#gru = reshape2 #cat
gru = cat
#gru = keras.layers.GRU(200,return_sequences=True)(gru)
gru = keras.layers.GRU(160,return_sequences=False)(gru)
dense = keras.layers.Dropout(0.3)(gru)

dense = keras.layers.Dense(128,activation='sigmoid')(gru)
dense = keras.layers.Dropout(0.2)(dense)

dense = keras.layers.Dense(64,activation='relu')(gru)
dense = keras.layers.Dropout(0.1)(dense)

dense = keras.layers.Dense(32,activation='relu')(dense)
dense = keras.layers.Dense(8)(dense)


model = keras.Model([inp1,inp2],dense)
#model.summary()

#use this with values between 0 and 1 as Y or it does not optimise correctly
def ranking_loss(y_true, y_pred):
    y_true_ = tf.cast(y_true, tf.float32)
    partial_losses = tf.maximum(0.0, 1 - y_pred[:, None, :] + y_pred[:, :, None])
    loss = partial_losses * y_true_[:, None, :] * (1 - y_true_[:, :, None])
    return tf.reduce_sum(loss)

model.compile(loss=ranking_loss,optimizer=keras.optimizers.Adam())
#model.compile(loss='mse',optimizer=keras.optimizers.Adam())

model.fit([train_x1,train_x2],train_y,
	batch_size=20,
	shuffle=True,
	epochs=200,
	validation_data=([test_x1,test_x2],test_y))
	
#model.fit([train_x1,train_x2],train_y,
#	batch_size=10,
#	shuffle=False,
#	epochs=20,
#	validation_data=([test_x1,test_x2],test_y))

y_hat = model.predict([test_x1,test_x2])[0]

sorted_ranks = sorted(y_hat)
predicted_ranks = np.array([sorted_ranks.index(x)+1 for x in y_hat],dtype=int)

sorted_orig = sorted(test_y[0])
actual_ranks = np.array([sorted_orig.index(x)+1 for x in test_y[0]],dtype=int)

print(predicted_ranks)
print(actual_ranks)































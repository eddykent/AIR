
import numpy as np

import tensorflow as tf
from tensorflow import keras

from keras.models import Sequential,Model
from keras.layers import Dense
from keras.layers import LSTM, Bidirectional, Input, Concatenate

from air.setups.signal import TradeDirection

import air.charting.candle_stick_functions as csf

from air.models.model_base import ModelMaker
from air.utils import overrides 
from air.backtest import TradeResultStatus


import pdb


class TradeInspectorModel(ModelMaker):
	
	signalling_data = None
	parameters = {'n_candles':50} 
	
	@overrides(ModelMaker)
	def __init__(self,signalling_data,**kwargs):
		self.signalling_data = signalling_data
		super().__init__(kwargs)
	
	#def _init
	
	@overrides(ModelMaker)
	def preprocess_x(self,trade_signals):
		X_candles = [] 
		X_vals = []
		n_candles_back = self.parameters['n_candles']
		trade_signals = trade_signals.copy()
		trade_signals = trade_signals.sort_values(by=['signal_id'])
		np_candles = self.signalling_data.np_candles
		
		#pdb.set_trace() 
		trade_signals['timeline_index'] = self.signalling_data.timeline_indexs(trade_signals['the_date'].to_numpy())
		trade_signals['instrument_index'] = self.signalling_data.instrument_indexs(trade_signals['instrument'].to_numpy())
		trade_signals['direction_mult'] = 0
		trade_signals.loc[trade_signals['direction'] == TradeDirection.BUY, 'direction_mult'] = 1
		trade_signals.loc[trade_signals['direction'] == TradeDirection.SELL, 'direction_mult'] = -1
		
		for ts in trade_signals.itertuples(name='TradeSignal'):	
			ii = ts.instrument_index
			ti = ts.timeline_index#? CHECK
			dm = ts.direction_mult
			start_price = np.mean(np_candles[ii,ti,1:]) #typical
			tpv = start_price + (dm * ts.take_profit_distance)
			slv = start_price + (dm * ts.stop_loss_distance)
			these_candles = np_candles[ii,(ti - 1) - n_candles_back : ti -1,:4]
			high = np.max(these_candles[:,csf.high])
			low = np.min(these_candles[:,csf.low])
			
			take_profit_val = (tpv - low) / (high - low)
			stop_loss_val = (slv - low) / (high - low)
			
			normed_candles = (these_candles / low) / (high - low)
			
			X_candles.append(normed_candles)
			X_vals.append([take_profit_val, stop_loss_val])
			
		return np.array(X_candles),np.array(X_vals)
		
	@overrides(ModelMaker)
	def preprocess_y(self,trade_results):
		trade_results = trade_results.copy()
		trade_results = trade_results.sort_values(by=['signal_id'])
		wins_tp = (trade_results['result_status'] == TradeResultStatus.WON_TP).astype(int)
		loses_sl = (trade_results['result_status'] == TradeResultStatus.LOST_SL).astype(int)
		return np.stack([wins_tp,loses_sl],axis=1)
		
		
	@overrides(ModelMaker)
	def postprocess_y(self,tensors):
		return tensors #dunno yet
	
	@overrides(ModelMaker)
	def _define(self):
		n_candles_back = self.parameters['n_candles']
		inp1 = Input(shape=(n_candles_back,4)) #candles
		inp2 = Input(shape=2) #tarets 
		lstm = LSTM(8,return_sequences=False,input_shape=inp1.shape)(inp1)
		#lstm = LSTM(50)(lstm)  #think about flattening instead
		cat = Concatenate()([lstm,inp2])
		dense = Dense(50,activation='relu')(cat)
		dense = Dense(25,activation='relu')(dense)
		dense = Dense(10,activation='relu')(dense)
		output = Dense(2,activation='sigmoid')(dense)
		model = keras.Model([inp1,inp2],output)
		model.compile(loss='mse',optimizer=keras.optimizers.Adam(learning_rate=0.00001))
		#model(tf.ones(input_shape))
		return model
		














import numpy as np

import tensorflow as tf
from tensorflow import keras


import pdb
from models.model_base import ModelMaker
from utils import overrides

class CurrencyStrengthModel(ModelMaker):
	
	dropout_chance = 0.3
	
	parameter_settings = {
		'rsi_sequence_length':0,
		'currency_strength_sequence_length':0,
		'rsi_features':['rsi'],
		'currency_features':['ema_value','ranking'],
		'currencies':[],
		'fx_pairs':[]
	}
	
	
	@overrides(ModelMaker)
	def _init(self):
		self.n_inputs = 2
	
	@overrides(ModelMaker)
	def preprocess_x(self,something):
		currencies = self.parameter_settings['currencies']
		fx_pairs = self.parameter_settings['fx_pairs']
		rsi_features = self.parameter_settings['rsi_features']
		cs_features = self.parameter_settings['currency_features']
		
		Xs = []
		
		for (rsi_seq,cs_seq) in something:
			rsi_list = []
			cs_list = []
			
			for rsi_row in rsi_seq:
				rsi_dict = rsi_row[2]
				rsis = []
				for fx in fx_pairs:	
					rsi_values = [rsi_dict[fx][rsi_key]	for rsi_key in rsi_features] #need to divide up! 
					rsis.append(rsi_values)
				rsi_list.append(rsis)
			
			for cs_row in cs_seq:
				cs_dict = cs_row[2]
				css = []
				for c in currencies:	
					cs_values = [cs_dict[c][cs_key] for cs_key in cs_features]
					css.append(cs_values)
				cs_list.append(css)			
			
			rsi_sequence = np.array(rsi_list)
			cs_sequence = np.array(cs_list)
			Xs.append([rsi_sequence,cs_sequence]) #one pair of inputs per sample. 
		
		return Xs
			
	@overrides(ModelMaker)
	def preprocess_y(self,data_rows):
		currencies = self.parameter_settings['currencies']
		Y  = []
		for result in data_rows:
			result_dict = result[2]
			rankings = []
			for c in currencies:
				rankings.append(result_dict[c]['ranking'] / len(currencies))
			Y.append(rankings)
		return np.array(Y)
			
		
	#@overrides(ModelMaker)
	#def postprocess_y(self,tensors): #turn into list of currences or something?
	#	pass
	
	@overrides(ModelMaker)
	def _define(self):
		l2_reg = keras.regularizers.l2(0.001)
		dropout_chance = 0.3
		
		rsi_seq_len = self.parameter_settings['rsi_sequence_length']
		currency_strength_sequence_len = self.parameter_settings['currency_strength_sequence_length']
		n_currencies = len(self.parameter_settings['currencies'])
		n_fx_pairs = len(self.parameter_settings['fx_pairs'])
		n_currency_features = len(self.parameter_settings['currency_features'])
		n_rsi_features = len(self.parameter_settings['rsi_features'])
		
		
		inp1 = keras.layers.Input(shape=(rsi_seq_len, n_fx_pairs, n_rsi_features) )
		inp2 = keras.layers.Input(shape=(currency_strength_sequence_len, n_currencies, n_currency_features ) )
		reshape1 = keras.layers.Reshape((rsi_seq_len, n_fx_pairs * n_rsi_features))(inp1)
		reshape2 = keras.layers.Reshape((currency_strength_sequence_len, n_currencies * n_currency_features))(inp2)
		cat = keras.layers.Concatenate(axis=2)([reshape1,reshape2]) #tz.x_sequence_lengths[0] == tz.x_sequence_lengths[1]!
		
		#gru = reshape2 #cat
		gru = cat
		#gru = keras.layers.GRU(100,return_sequences=True,activity_regularizer=l2_reg)(gru)
		#gru = keras.layers.Dropout(dropout_chance)(gru)
		gru = keras.layers.GRU(100,return_sequences=False,activity_regularizer=l2_reg)(gru)
		dense = gru
		#dense = keras.layers.Dropout(dropout_chance)(dense)
		dense = keras.layers.Dense(75,activation='relu',activity_regularizer=l2_reg)(dense)
		dense = keras.layers.Dropout(dropout_chance)(dense)
		#dense = keras.layers.Dense(71,activation='relu',activity_regularizer=l2_reg)(dense)
		#dense = keras.layers.Dropout(dropout_chance)(dense)
		dense = keras.layers.Dense(64,activation='relu',activity_regularizer=l2_reg)(dense)
		dense = keras.layers.Dropout(dropout_chance)(dense)
		dense = keras.layers.Dense(8,activation='sigmoid')(dense)
		model = keras.Model([inp1,inp2],dense)
		
		model.compile(loss='mse',optimizer=keras.optimizers.Adam(learning_rate=0.005))
		
		return model
	
	
	
	
	
	
	
	
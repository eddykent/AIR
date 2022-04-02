import numpy as np

import tensorflow as tf
from tensorflow import keras

from keras.models import Sequential
from keras.layers import Dense
from keras.layers import LSTM,Bidirectional
import spacy

from models.model_base import ModelMaker
from utils import overrides 

from fundamental import TextAnalysis

import pdb

class NewsReaderModel(ModelMaker):
	
	text_analyser = None
	nlp = None
	
	parameters = {'story_length':650}
	
	#def __init__(**kwargs):  - parameters_label, weights_label
	#	super().__init__(**kwargs)
	
	@overrides(ModelMaker)
	def _init(self):
		self.text_analyser = TextAnalysis()
		self.nlp = spacy.load("en_core_web_lg")
	
	@overrides(ModelMaker)
	def preprocess_x(self,passages): #pass list of passages from articles
		maxlen = self.parameters.get('story_length',650)
		feature_vectors = [self.text_analyser.create_feature_vector(text,self.nlp) for text in passages]
		clipped_padded = [] 
		_,word_size = feature_vectors[0].shape
		for fv in feature_vectors:
			if fv.shape[0] >= maxlen:
				clipped_padded.append(fv[:maxlen])
			else:
				thislen = fv.shape[0]
				endpadlen = maxlen - thislen 
				padding = np.zeros((endpadlen,word_size))
				clipped_padded.append(np.concatenate([fv,padding],axis=0))
		return np.array(clipped_padded)
	
	
	
	@overrides(ModelMaker)
	def preprocess_y(self,data_rows):
		return_y = []
		for ydata in data_rows:
			#pdb.set_trace()
			summary,profit_paths = ydata
			typical = summary['typical']
			rate= typical['rate'] * 100 #this is already normalised but we want to turn it to between 0 and 1 so half then add 0.5? 
			std = (typical['std'] * 100) / typical['average']  #divide by the average so that we can compare different stds together 
			return_y.append(np.array([rate,std]))
		return np.array(return_y)
	
	@overrides(ModelMaker)
	def postprocess_y(self,tensors):
		return [{'impact':t[0],'std':(t[1]*0.5)+0.5} for t in tensors]
	
	@overrides(ModelMaker)
	def _define(self):
		maxlen = self.parameters.get('story_length',650)
		model = Sequential()
		model.add(Bidirectional(LSTM(150,return_sequences=True,input_shape=(maxlen,300))))
		model.add(Bidirectional(LSTM(100))) 
		model.add(Dense(100,activation='relu'))
		model.add(Dense(2)) #no activation?
		model.compile(loss='mse',optimizer=keras.optimizers.Adam(learning_rate=0.0001))
		return model
	
#the beauty of this is we can actually override NewsReaderModel and call a different _define function to experiment with many models!
	
	
	
	
	
	
	
	
	
	
	
	
	
	
	
	
	
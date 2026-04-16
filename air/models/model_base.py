
import tensorflow as tf
from tensorflow import keras

import json
from os.path import join as file_namer
import logging
import pdb

log = logging.getLogger(__name__)

from air.utils import ListFileReader

#documentation!
#- used to load a model and to do any preprocessing on X & Y values to turn them into feature vectors that go into the model, and post processing on Y 
class ModelMaker:
	
	model = None
	parameter_settings = {} #dynamically hold any parameters for normalisation and for model settings 
	parameters_label = ''
	weights_label = '' 
	weights_directory = './models/weights/'
	parameters_directory = './models/parameters/'
	n_inputs = 1#automate somehow?
	
	def __init__(self,parameters_label='',weights_label=''):
		
		if parameters_label:
			self.parameters_label = parameters_label
			self.load_parameters()
		self.weights_label = weights_label
		
	def create_model(self):
		self._init()
		self.model = self._define()
		
		#set n_inputs here
		
		if self.weights_label:
			self.load_weights()
	
	def save_parameters(self):
		params_json = json.dumps(self.parameter_settings)
		filename = self.__params_filename()
		with open(filename,'w') as f:
			f.write(param_json)
		
	def load_parameters(self):
		lfr = ListFileReader() #list file reader has capability of reading files that contain comments in
		lfr.not_found_none = True
		filename = self.__params_filename(self.parameters_label)
		params_json = lfr.read_full_text(filename) #if not exists we dont care! :)
		if params_json is None:
			pass #log here
		else:
			self.parameter_settings = json.loads(params_json) #dict updater?
	
	def save_weights(self):
		self.model.save_weights(self.__weights_filename(self.weights_label))
	
	def load_weights(self):
		filename = self.__weights_filename(self.weights_label)
		exists = False
		try:
			open(filename).close()
			exists = True
		except FileNotFoundError as e:
			log.warning(f"Unable to load weights {filename}. Using new weights.",exc_info=True) #stops here? #
			exists = False
		if exists:
			try:
				self.model.load_weights(filename)
			except Exception as e:
				log.warning(f"Unable to load weights {filename}. Using new weights.",exc_info=True) #stops here? 
		log.debug('Finished loading weights')
	
	def __params_filename(self,parameters_label):
		return file_namer(self.parameters_directory,self.__class__.__name__ + parameters_label+'.json')
	
	def __weights_filename(self,weights_label):
		return file_namer(self.weights_directory,self.__class__.__name__ + weights_label+'.h5')
	
	def preprocess_x(self,data):	
		return data
	
	def preprocess_y(self,result):
		return result 
		
	def postprocess_y(self,result):
		return result
	
	#consider compile options?
	def recompile(self,*args,**kwargs):
		weights = model.get_weights() 
		model.compile(*args,**kwargs)
		model.set_weights(weights) 
	
	#methods to override
	def _define(self):
		raise NotImplementedError('This method must be overridden')

	def _init(self):
		return

#- used in the production system to load a model & load the preprocessing from ModelMaker, load weights and then be able to be called from anywhere
class ModelLoader:
	
	model_maker = None
	
	def __init__(self,model_maker):
		self.model_maker = model_maker
		if self.model_maker.model is None:
			self.model_maker.create_model()
		else:
			self.model_maker.load_weights() #ensure weights are loaded
	
	def invoke(self,data):
		X = self.model_maker.preprocess_x(data)
		Y = self.model_maker.model.predict(X)
		return self.model_maker.postprocess_y(Y)
	
	
	
	
	
	




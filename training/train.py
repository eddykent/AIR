
from enum import Enum

import uuid
import zlib
import pickle

import numpy as np 
from tqdm import tqdm
import random

import tensorflow as tf
from tensorflow import keras
from os.path import join as file_namer

from models.model_base import ModelMaker,ModelLoader

import pdb
##caching with data providers could be done by row in a temp table or temp pickles. But it will make a mess so clean it up afterwards! 
#cached rows are stored in "pickles/cobwebs" since there is 1 primary dictionary object and many rows all stored as guid filenames

class ValidationMode(Enum):
	START = -1 #use the start values of the list of samples
	RANDOM = 0 #use random list of samples 
	END = 1 #use the end values of the list of samples

#a row caching system to get training data quicker once it is created the first time. Consider using multiprocessing/threading 
class CobwebCache:	
	
	row_ids = {} #stores map of index -> guid 
	cobweb_id = None
	filename = None
	the_date = None
	notes = ''#store any text that we can use to describe this cobweb - eg what the data is or why it is useful/ where it is used 
	
	def __init__(self,filename,notes=''):
		self.cobweb_id = str(uuid.uuid4())#needed?
		self.filename = filename
		self.the_date = None
		self.notes = notes 
	
	@staticmethod
	def load_cobweb(filename):
		pass #return the cobweb
	
	@staticmethod
	def save_cobweb(filename,cobweb):
		pass
	
	@staticmethod
	def clear_cobweb(filename):
		pass #remove all row pickles then remove the main cobweb pickle
	
	def save_rows(self,rows):
		new_guids = [str(uuid.uuid4()) for r in rows]
		#save guids to row ids 
		#save each row in a file called guid
	
	def fetch_rows(self,indexs):
		guids = [self.row_ids[i] for i in index]
		
	
	
class DataProvider: #cobweb functions? 
	#provde X and Y data and provide ability for caching using pickles - generator, full, validation_set 
	
	row_cache = False #if true, we will cache every sample in a pickle or in the database (decide) 
	model_maker = None #model maker holds the model AND processes for processing X and Y values into tensors 
	training_parts = [] #list of partial samples, containing information on how to get the full sample. 
	validation_parts = [] # both these lists are empty until we call begin_load()
	training_batch_size = 32
	validation_batch_size = 3
	shuffle = True
	validation_mode = ValidationMode.RANDOM  
	parameters = {} 
	#pre_training_data = {} 
	#pre_validation_data = {}
	
	cobweb_directory = './pickles/cobwebs'
	
	#__cache_forward_pass = False #set to true once we have a cobweb, if we are caching. 
	__train_cobweb = None #cobwebs for storing row data on the disk
	__valid_cobweb = None 
	
	def __init__(self,model_maker,row_cache=False,validation_mode=ValidationMode.RANDOM,training_batch_size=32,validation_batch_size=5,parameters={}): #parameter settings? start/end dates etc? 
		self.model_maker = model_maker #used for preprocess_x and preprocess_y in _generate
		self.row_cache = row_cache
		if parameters:
			self.parameters = parameters
		#if self.row_cache:
		#	self.__cobweb = CobwebCache()
	
	
		#return DataGenerator object using self as the DataProvider
	def get_training_generator(self):
		return DataGenerator(self,validation=False)
	
	#return DataGenerator object using self as the DataProvider, but use only a subset from DataProvider
	def get_validation_generator(self):
		return DataGenerator(self,validation=True)
	
	def get_full_set(self): 
		return self.generate(None,False)
	
	def get_full_validation(self):
		return self.generate(None,True)
	
	def generate(self,indexs,validation):
		#do caching thing here with cobwebs 
		full_parts = self.validation_parts if validation else self.training_parts
		instructions_list = [full_parts[i] for i in indexs] if len(indexs) else full_parts
		X,Y =  self._generate(instructions_list)
		return X,Y
	
	def begin_load(self,validation_split=0.1):
		#do some kind of check here for cobwebs first. Check validation split. if it is wrong we're better off restarting :/
		data_instruction_list = self._sample_instructions_list()
		n_samples = len(data_instruction_list)
		n_validation_samples = n_samples*validation_split 
		if self.validation_mode == ValidationMode.START:
			self.validation_parts = data_instruction_list[:n_validation_samples]
			self.training_parts = data_instruction_list[n_validation_samples:]
		if self.validation_mode == ValidationMode.END:
			self.validation_parts = data_instruction_list[:n_validation_samples]
			self.training_parts = data_instruction_list[n_validation_samples:]
		if self.validation_mode == ValidationMode.RANDOM:
			self.validation_parts = []
			self.training_parts = [] 
			count = 0
			while data_instruction_list and count < n_validation_samples:
				n = len(data_instruction_list)
				i = random.randint(0,n-1)
				self.validation_parts.append(data_instruction_list.pop(i))
				count = count + 1
			self.training_parts = data_instruction_list
	
	def load_cache(self,cobweb_label):
		pass
	
	def __cobweb_locator(self,cobweb_label):
		return file_namer(self.cobweb_directory,self.__class__.__name__+cobweb_label+'.pkl')
	
	#start loading stuff into the class data which can be used to fetch the full data rows 
	#this needs to populate pre_data and pre_validation_data. These are then used in _generate()
	def _sample_instructions_list(self):
		'''
		A function to implement that gets a set of meta data and returns it to the caller. 
		The meta data can then be used to read the full data using row indexs.
		Parameters are set from the initialisation step.
		'''
		raise NotImplementedError('This method must be overridden')
	
	#used in generators below. IMPORTANT - if the list of indexes is None, return the full dataset
	def _generate(self,instructions_list):
		'''
		Function to take a list of instruction rows and turn them into tuples. The rows can be loaded using 
		some meta data that was created in begin_load. If a cobweb is used, this step can also be bypassed 
		since rows will be cached on the file system after the first forward pass. 		
		'''
		raise NotImplementedError('This method must be overridden')
	

#helper class that is returned to create a keras generator 
class DataGenerator(keras.utils.Sequence):
	
	batch_size = 32
	shuffle = False
	data_provider = None
	n_samples = 10
	validation=False
	
	def __init__(self,data_provider,validation=False):
		self.validation=validation
		self.data_provider = data_provider
		if validation:
			self.batch_size = data_provider.validation_batch_size
			self.shuffle = False
			self.n_samples = len(data_provider.validation_parts)
		else:
			self.batch_size = data_provider.training_batch_size
			self.shuffle = data_provider.shuffle
			self.n_samples = len(data_provider.training_parts)
		self.indexes = np.arange(self.n_samples)
	
	def __len__(self):
		return int(self.n_samples / self.batch_size)
	
	def __getitem__(self,index):	
		indexs = self.indexes[index*self.batch_size:(index+1)*self.batch_size]
		X,y = self.data_provider.generate(indexs,self.validation)
		return X,y
		
	def on_epoch_end(self):
		self.indexes = np.arange(self.n_samples)
		if self.shuffle:
			np.random.shuffle(self.indexs)


 #training & testing using model.fit or model.fit_generator etc. Also used to generate models like tensorflow lite etc ?
# load a model & a data provider. Then train it and produce weights. A ModelLoader in the production system can then load the model and weights 
class ModelComposer:
	
	model_maker = None
	data_provider = None
	weights_label = None # if provided, load model weights if they exist. 
	
	def __init__(self,model_maker,data_provider,weights_label=None):
		self.model_maker = model_maker
		self.data_provider = data_provider
		self.weights_label = weights_label
	
	def train(self,epochs=20):
		if self.weights_label:
			self.model_maker.load_weights(self.weights_label)
		return self.model_maker.model.fit(
			self.data_provider.get_training_generator(),  #skip y since it is presented in the generator
			epochs=epochs,
			validation_data=self.data_provider.get_validation_generator(),
			batch_size=self.data_provider.training_batch_size,
			validation_batch_size=self.data_provider.validation_batch_size
		)
	
	def save(self,new_weights_label=None): #incase we want to save it to a different file	
		if new_weights_label is not None:
			self.model_maker.weights_label = new_weights_label
		self.model_maker.save_weights()
	
	
	def test(self,input):
		ml = ModelLoader(self.model_maker) #production based model for testing in the coding sense rather than the output :D 
		return ml.invoke(input)
 
 
 
 
 
 
 
 
 
 
 
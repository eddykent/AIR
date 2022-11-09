
from enum import Enum

import uuid
import zlib
import pickle
import datetime
import json

import numpy as np 
from tqdm import tqdm
import random

import tensorflow as tf
from tensorflow import keras
import os
from os.path import join as file_namer

import pdb

from models.model_base import ModelMaker,ModelLoader
from utils import ListFileReader


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
	cobweb_silk_directory = './data/pickles/cobwebs/silk' #directory to store loose row data
	
	
	def __init__(self,filename,notes=''):
		self.cobweb_id = str(uuid.uuid4())#needed?
		self.filename = filename
		self.the_date = datetime.datetime.now().isoformat()
		self.notes = notes 
	
	@staticmethod
	def load_cobweb(filename):
		the_cobweb = None
		try:
			lfr = ListFileReader()
			lfr.not_found_none = False
			json_str = lfr.read_full_text(filename)
			if json_str:
				cobweb_dict = json.loads(json_str)
				the_cobweb = CobwebCache(filename,cobweb_dict['notes'])
				the_cobweb.the_date = cobweb_dict['the_date']
				the_cobweb.cobweb_id = cobweb_dict['cobweb_id']
				the_list = cobweb_dict['row_guids']
				the_cobweb.row_ids = {i:the_list[i] for i in range(len(the_list))}
		except FileNotFoundError:
			pass #dont do anything 
		if the_cobweb is None:
			the_cobweb = CobwebCache(filename)
			CobwebCache.save_cobweb(filename,the_cobweb)
		return the_cobweb #return the cobweb with row_ids loaded & other data like notes etc. If it doesn't exit, create a new one
	
	@staticmethod
	def save_cobweb(filename,cobweb): #dump a json representation of the cobweb complete with row ids as list -nulls for missing indexs
		save_dict = {
			'cobweb_id':cobweb.cobweb_id,
			'filename':cobweb.filename,
			'the_date':cobweb.the_date, 
			'notes':cobweb.notes
		}
		list_size = (max(i for i in cobweb.row_ids)+1) if cobweb.row_ids else 0
		the_list = [None for i in range(list_size)]
		for i in cobweb.row_ids:
			the_list[i] = cobweb.row_ids[i]
		save_dict['row_guids'] = the_list
		with open(filename,'w') as f:
			f.write(json.dumps(save_dict))
	
	@staticmethod    #remove all row pickles then remove the main cobweb json file
	def clear_cobweb(cobweb):
		filename = cobweb.filename
		cobweb.clear_rows([cobweb.row_ids[i] for i in cobweb.row_ids if cobweb.row_ids[i] is not None])
		os.remove(filename) 
	
	def clear_rows(self,guids):
		for guid in guids:
			fn = file_namer(self.cobweb_silk_directory,guid+'.pkl')
			if os.path.exists(fn):
				os.remove(fn)

	def save_rows(self,indexs,rows):
		assert len(indexs) == len(rows)
		#overwrite old rows - prevent loads of stuff caching and wasting space
		save_guids = {i:self.row_ids.get(i) if self.row_ids.get(i) else str(uuid.uuid4()) for i in indexs}
		for index, row_data in zip(indexs,rows):
			save_guid = save_guids[index]
			with open(file_namer(self.cobweb_silk_directory,save_guid+'.pkl'),'wb') as f:
				pickle.dump(row_data,f) #compress?
		self.row_ids.update(save_guids)
		
	
	def fetch_rows(self,indexs):  #return None for any FNF/no guid etc 
		return_dict = {}
		#for each guid, get the row data. return {index:row data}
		for index in indexs:
			save_guid = self.row_ids.get(index)
			if not save_guid:
				return_dict[index] = None
			else:
				try:
					with open(file_namer(self.cobweb_silk_directory,save_guid+'.pkl'),'rb') as f:
						return_dict[index] = pickle.load(f)
				except FileNotFoundError:
					return_dict[index] = None
		return return_dict
	
	
class DataProvider: #cobweb functions? 
	#provde X and Y data and provide ability for caching using pickles - generator, full, validation_set 
	
	cobweb_label = False #if true, we will cache every sample in a pickle
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
	
	cobweb_directory = './data/pickles/cobwebs'
	
	#__cache_forward_pass = False #set to true once we have a cobweb, if we are caching. 
	cobweb = None #cobwebs for storing row data on the disk
	
	def __init__(self,model_maker,row_cache_label=False,overwrite_cache=False,validation_mode=ValidationMode.RANDOM,training_batch_size=32,validation_batch_size=5,parameters={}): #parameter settings? start/end dates etc? 
		self.model_maker = model_maker #used for preprocess_x and preprocess_y in _generate
		if parameters:
			self.parameters = parameters
		if row_cache_label:
			#pdb.set_trace()
			self.cobweb_label = row_cache_label
			self.load_cache()
			if overwrite_cache:
				CobwebCache.clear_cobweb(self.cobweb)
				self.load_cache() #start from beginning 
	
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
		
		instructions_list = [] 
		collection_indexs = indexs
		collected = {}
		
		#pdb.set_trace()
		if self.cobweb and not validation:
			collected = self.cobweb.fetch_rows(indexs) #handle when indexs = None/0 length
			collection_indexs = [i for i in indexs if i not in collected or collected[i] is None]
			instructions_list = [full_parts[i] for i in collection_indexs] 
		else:
			instructions_list = [full_parts[i] for i in indexs] if len(indexs) else full_parts
				
		#only generate the missing stuff!
		(cX,cY) =  self._generate(instructions_list) if instructions_list else ([],[])
		(X,Y) = ([],[])
		
		if self.cobweb and not validation: #we only cache the training stuff - validation should be a small dataset!
			
			#marry together cX,cY with collected! 
			generated = {}
			for i,(x,y) in zip(collection_indexs,list(zip(cX,cY))):
				generated[i] = (x,y)
			
			self.cobweb.save_rows([i for i in generated],[generated[i] for i in generated])
			cobweb_fn = self.__cobweb_locator(self.cobweb_label)
			CobwebCache.save_cobweb(cobweb_fn,self.cobweb)
			
			all = {}
			all.update(collected)
			all.update(generated)
			
			rows = [all[i] for i in sorted([i for i in all])]
			X,Y = list(zip(*rows)) #returns tuples
			X = np.array(X)
			Y = np.array(Y)
			
		else:
			X = cX
			Y = cY
		
		#pdb.set_trace()
		if self.model_maker.n_inputs > 1:
			Xs = list(zip(*X))
			#log?
			assert len(Xs) == self.model_maker.n_inputs, f"Number of inputs is incorrect. There should be {self.model_maker.n_inputs} but counted {len(Xs)}..."
			newXs = []
			for x in Xs:
				newXs.append(np.array(x))
			X = newXs
		return X,Y
	
	def begin_load(self,validation_split=0.1):
		#do some kind of check here for cobwebs first. Check validation split. if it is wrong we're better off restarting :/
		data_instruction_list = self._sample_instructions_list()
		n_samples = len(data_instruction_list)
		n_validation_samples = int(n_samples*validation_split)
		if self.validation_mode == ValidationMode.START:
			self.validation_parts = data_instruction_list[:n_validation_samples]
			self.training_parts = data_instruction_list[n_validation_samples:]
		if self.validation_mode == ValidationMode.END:
			dat_instruction_list = reversed(data_instruction_list)
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
		
	def load_cache(self):
		fn = self.__cobweb_locator(self.cobweb_label)
		self.cobweb = CobwebCache.load_cobweb(fn)	
			
	def __cobweb_locator(self,cobweb_label):
		return file_namer(self.cobweb_directory,self.__class__.__name__+'-'+cobweb_label+'.json')
	
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
	indexes = []
	
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
			np.random.shuffle(self.indexes)
		if self.data_provider.model_maker.weights_label:
			self.data_provider.model_maker.save_weights()



# After so many iterations, look for a stopping point. Do this by extending EarlyStopping
class EarlyStoppingAfter(keras.callbacks.EarlyStopping):

	start_epoch = 10

	def __init__(self, start_epoch=100,**kwargs): # add argument for starting epoch
		super(EarlyStoppingAfter, self).__init__(**kwargs) 
		self.start_epoch = start_epoch

	def on_epoch_end(self, epoch, logs=None):
		if epoch > self.start_epoch:
			super().on_epoch_end(epoch, logs)




#training & testing using model.fit or model.fit_generator etc. Also used to generate models like tensorflow lite etc ?
# load a model & a data provider. Then train it and produce weights. A ModelLoader in the production system can then load the model and weights 
class ModelComposer:
	
	model_maker = None
	data_provider = None
	
	def __init__(self,model_maker,data_provider,weights_label=None):
		self.model_maker = model_maker
		self.data_provider = data_provider
	
	def train(self,epochs=20): #extendable! can override this function :) 
		if self.model_maker.weights_label:
			self.model_maker.load_weights()
		
		return self.model_maker.model.fit(
			self.data_provider.get_training_generator(),  #skip y since it is presented in the generator
			epochs=epochs,
			validation_data=self.data_provider.get_validation_generator(),
			batch_size=self.data_provider.training_batch_size,
			validation_batch_size=self.data_provider.validation_batch_size
		)
	
	#def recompile(self, ...):
		
	
	def save(self,new_weights_label=None): #incase we want to save it to a different file	
		if new_weights_label is not None:
			self.model_maker.weights_label = new_weights_label
		self.model_maker.save_weights()
	
	
	def test(self,input):
		ml = ModelLoader(self.model_maker) #production based model for testing in the coding sense rather than the output :D 
		return ml.invoke(input)
 
 
 
 
 
 
 
 
 
 
 
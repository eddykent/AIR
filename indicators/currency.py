

import numpy as np 

import pdb 

from utils import overrides

from indicators.indicator import Indicator

#from a set of  currencies, currency pairs and an oscillator make a mapping 
#then make classes that can collect into single currencies, and distribute back into pairs 
class CurrencyBase(Indicator):
	
	currency_pairs = []
	currencies = []
	mapping = None
	name_mapping = None
	
	def __init__(self,currency_pairs, currencies):
		self.currencies = currencies
		self.currency_pairs = currency_pairs
		self._setup_map() 
	
	def _setup_map(self):
		currency_pairs = [cp.split('/') for cp in self.currency_pairs]
		dest = np.zeros((len(self.currencies),len(self.currency_pairs))).astype(np.int)
		name_dest = np.zeros((len(self.currency_pairs),2)).astype(np.int)
		for i,cur in enumerate(self.currencies):
			for j,pair in enumerate(currency_pairs):
				if len(pair) > 1:
					if pair[0] == cur:
						dest[i,j] = 1 
						name_dest[j,0] = i
					if pair[1] == cur:
						dest[i,j] = -1
						name_dest[j,1] = i
		self.mapping = dest
		self.name_mapping = name_dest
		
	
class CurrencyCollector(CurrencyBase): 
	
	candle_channel = 0
	
	def _perform(self,np_result):	
		combined = [] 
		
		for ci,this_map in enumerate(self.mapping):
			
			N = np.sum(this_map != 0) #val to divide result by 
			pos_values = np_result[np.where(this_map > 0)[0],:,self.candle_channel]
			neg_values = 1 - np_result[np.where(this_map < 0)[0],:,self.candle_channel]
			all_values = np.concatenate([pos_values,neg_values])
			combined.append(np.sum(all_values,axis=0) / N)
			#pdb.set_trace()#merge the results of np_candles into 1 per currency 
			#print('combine')
		
		currency_result = np.stack(combined)
		return currency_result[:,:,np.newaxis]
	

class CurrencyDistributor(CurrencyBase):
	
	candle_channel = 0
	
	def _perform(self,npc_result):	
		currency_result = npc_result[:,:,self.candle_channel]
		pair_combined = np.array([np.stack([currency_result[c1],currency_result[c2]],axis=1) for (c1,c2) in self.name_mapping])
		return pair_combined

#merges the currencies together, then re-distributes them 
class CurrencyMerge(CurrencyBase):
	
	candle_channel = 0
	
	def _perform(self,np_result):
		
		combined = [] 
		
		for ci,this_map in enumerate(self.mapping):
			
			N = np.sum(this_map != 0) #val to divide result by 
			pos_values = np_result[np.where(this_map > 0)[0],:,self.candle_channel]
			neg_values = 1 - np_result[np.where(this_map < 0)[0],:,self.candle_channel]
			all_values = np.concatenate([pos_values,neg_values])
			combined.append(np.sum(all_values,axis=0) / N)
			#pdb.set_trace()#merge the results of np_candles into 1 per currency 
			#print('combine')
		
		currency_result = np.stack(combined)
		pair_combined = np.array([np.stack([currency_result[c1],currency_result[c2]],axis=1) for (c1,c2) in self.name_mapping])
		return pair_combined
		

#take in the usual currency etc but also take in an oscillator and do all calcs here 
class CurrencyWrapper(CurrencyMerge):

	oscillator = None

	def __init__(self,oscillator,*args,**kwargs):
		super().__init__(*args,**kwargs)
		self.oscillator = oscillator
	
	
	def _perform(self,np_candles):
		np_result = self.oscillator(np_candles)
		return super()._perform(np_result)















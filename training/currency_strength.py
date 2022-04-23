

from tqdm import tqdm
import datetime
import numpy as np
from collections import defaultdict


import pdb

from models.currency_strength_model import CurrencyStrengthModel 
from training.train import DataProvider, ModelComposer, ValidationMode

from utils import Database, DataComposer, ListFileReader, overrides


class CurrencyStrengthData(DataProvider):

	parameters = {
		'start_date':datetime.datetime(2019,1,1),
		'end_date':datetime.datetime(2022,4,1)
	}
	
	@overrides(DataProvider)
	def _sample_instructions_list(self):
		rsi_result = [] #current RSI 
		cs_result = [] #currency strengths 
		lfr = ListFileReader()
		currencies = lfr.read('fx_pairs/currencies.txt')
		days_back_delta = self.parameters['end_date'] - self.parameters['start_date']
		days_back_buff = 20 #add extra days to end to ensure we get a good reading
		with Database(cache=False,commit=False) as cursor:
			composer = DataComposer(cursor)
			composer.call('get_candles_from_currencies',{
				'currencies':currencies,
				'this_date':self.parameters['end_date'],
				'days_back':days_back_delta.days + days_back_buff, #chart_resolution 240?
				'chart_resolution':240
			})
			composer.call('typical_price')
			composer.call('relative_strength_index',{'period':14})	
			composer.execute()
			
			rsi_branch = composer.branch()
			rsi_result = rsi_branch.result(as_json=True)
			
			composer.call('currency_strength')
			composer.call('exponential_moving_average',{'period':3})
			ecs_branch = composer.branch()
			composer.call('instrument_ranking')
			composer.join([ecs_branch])
			cs_result = composer.result(as_json=True)
		
		n_samples = 1000
		sequence_len = 20 #almost 4 days of data
		skip_len = 1
		y_sequence_len = 1 
		
		currencies = self.model_maker.parameter_settings['currencies']
		fx_pairs = self.model_maker.parameter_settings['fx_pairs']
		
		#firstly, lets join the results together by date. 
		datetime_dict = defaultdict(list)
		for rsi_row in rsi_result:
			datetime_dict[rsi_row[0]].append(rsi_row)
		for cs_row in cs_result:
			datetime_dict[cs_row[0]].append(cs_row)
		
		datetimes = sorted(datetime_dict.keys())
		correct_datetimes = [dt for dt in datetimes if len(datetime_dict[dt]) == 2] #got all results yay! 
		nice_rows = [datetime_dict[dt] for dt in correct_datetimes]
		nice_rows_reversed = list(reversed(nice_rows))
		sequence_start_indexs = range(0,(n_samples*skip_len)+sequence_len+y_sequence_len+1,skip_len)
		sequences = [nice_rows_reversed[i:i+sequence_len+y_sequence_len] for i in sequence_start_indexs]
		rsi_cs_sequences = [] 
		results = []
		for sequence in sequences:
			y_post_date = sequence[0][1]
			y_date = sequence[1][0][0]
			y_result = (y_date,y_post_date[1],y_post_date[2])
			x_rsi = [] 
			x_cs = []
			for (rsi,cs) in sequence[1:]:
				x_rsi.append(rsi)
				x_cs.append(cs)
			x_rsi = list(reversed(x_rsi)) #put back into ascending order
			x_cs = list(reversed(x_cs))
			
			rsi_cs_sequences.append([x_rsi,x_cs])
			results.append(y_result)	
			
		return list(zip(rsi_cs_sequences,results))
		
	
	@overrides(DataProvider)
	def _generate(self,instruction_list):
		rsi_cs_sequences, results =  list(zip(*instruction_list)) 
		xs = self.model_maker.preprocess_x(rsi_cs_sequences)
		ys = self.model_maker.preprocess_y(results)
		return xs,ys


def perform_training():
	lfr = ListFileReader()
	currency_strength_model = CurrencyStrengthModel(weights_label='test')
	currency_strength_model.parameter_settings.update({
		'rsi_sequence_length':20,
		'currency_strength_sequence_length':20,
		'currencies':sorted(lfr.read('fx_pairs/currencies.txt')),
		'fx_pairs':sorted(lfr.read('fx_pairs/fx_mains.txt'))
	})
	currency_strength_model.create_model()
	currency_strength_data = CurrencyStrengthData(currency_strength_model)
	currency_strength_data.begin_load()
	#pdb.set_trace()
	model_composer = ModelComposer(currency_strength_model,currency_strength_data)
	model_composer.train(epochs=50)
	#model_composer.test(' ') #put some test news snippet in here
	
	#TODO: use custom loss & recompile
	

perform_training()

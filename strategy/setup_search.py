
## file for performing basc search strategy - first search among iterators for best performing combinations
#also use more advanced search methods eg local search or gla for larger datasets 

import itertools #going to want all combinations of iterators
from collections import defaultdict
import numpy as np 
import pandas as pd
from tqdm import tqdm

import pdb


from backtest import BackTesterCandles, BackTestStatistics
from charting import candle_stick_functions as csf

from setups.trade_setup import blank_result, TradeSetup
from setups.setup_tools import Zero2OneTool
from setups.collected_setups import Harmony, Trends, Shapes

from strategy.strategy_components import TriggerBlock, SetupBlock
from strategy.trigger_block_lists import moving_averages, chart_patterns #more? 

from utils import overrides 
	
class SignalGenerator:
	
	#from an infer_bubble (a hint from previous training) create signals from trade_signalling_data
	def infer(self, trade_signalling_data, infer_bubble_df):
		raise NotImplementedError('This method must be overridden') 
	
	#perform a search through many setups and indicators to get the best configurations and return config in a infer_bubble_df object 
	def train(self, trade_signalling_data, backtesting_data):
		raise NotImplementedError('This method must be overridden') 
	
	#from this stratgy, get the minimum number of days required to ensure signals are accurate everywhere (eg, RSI(14) needs 14 and EMA(200) needs atleast 200) 
	def grace_period_hint(self):
		raise NotImplementedError('This method must be overridden') #or just return a large number!  :)
	
	@staticmethod
	def create_signals(name,bullish,bearish,stop_data,trade_signalling_data):
		(bullish_tp, bullish_sl), (bearish_tp, bearish_sl) = stop_data
		
		#copy? 
		
		trade_signalling_data.name = name 
		trade_signalling_data.bullish.signals = bullish
		trade_signalling_data.bearish.signals = bearish
		
		trade_signalling_data.bullish.entries, trade_signalling_data.bearish.entries = blank_result(trade_signalling_data)
		trade_signalling_data.bullish.entry_cuts,trade_signalling_data.bearish.entry_cuts = blank_result(trade_signalling_data)
		
		trade_signalling_data.bullish.take_profit_distances = bullish_tp
		trade_signalling_data.bearish.take_profit_distances = bearish_tp  
		trade_signalling_data.bullish.stop_loss_distances = bullish_sl
		trade_signalling_data.bearish.stop_loss_distances = bearish_sl
		
		return TradeSetup.make_trade_signals(trade_signalling_data)





class SetupSearch(SignalGenerator):
	
	setup_list = [] 
	
	#def __init__
	
	@overrides(SignalGenerator)
	def train(self, trade_signalling_data, backtesting_data):
		backtesting_data = backtesting_data if backtesting_data is not None else trade_signalling_data
		all_signals = []
		print('get trade setup signals') 
		
		for tsi, trade_setup in tqdm(list(enumerate(self.setup_list))):
			ts = trade_setup() # init 
			all_signals.append((tsi,ts.signals(trade_signalling_data)))
		
		backtester = BackTesterCandles(backtesting_data)
		full_results = [] 
		
		#pdb.set_trace() #check the number of signals
		
		
		print('perform backtests')
		for (tsi, signals) in tqdm(all_signals):
			results = backtester.perform(signals)
			statstool = BackTestStatistics(backtesting_data,signals,results)
			result_df = statstool.calculate()  #add to pile for sorting 
			result_df.insert(0,'tsi',tsi)
			full_results.append(result_df)

		full_results_df = pd.concat(full_results) 
		return full_results_df
		
	
	@overrides(SignalGenerator)
	def infer(self,trade_signalling_data, infer_bubble_df):
		result_df = infer_bubble_df.copy() 
		selected = result_df[(result_df['ratio'] > 0.5) & (result_df['N'] > 5)] #enough trades & positive W/L ratio
		executable_combs = defaultdict(list)
		for tsi, df in selected[['tsi','instrument']].groupby('tsi'):
			executable_combs[tsi] = list(df['instrument'])
		
		return_signals = []
		#pdb.set_trace()
		for tsi, trade_setup in tqdm(list(enumerate(self.setup_list))):
			if tsi not in executable_combs.keys():
				continue
			ts = trade_setup() # init 
			these_signals = ts.signals(trade_signalling_data)
			these_signals = [s for s in these_signals if s.instrument in executable_combs[tsi]]
			return_signals += these_signals		
		
		return return_signals
		
	
	#objective is to maximise profits - this always max 
	def process_full_results(self,results_df,objective='output_balance'): #sort by money on each instrument 
		
		full_results = results_df.copy()
		#pdb.set_trace()
		if callable(objective):
			full_results['objective_value'] = objective(full_results) #check - may need lambda or something
		elif objective in results_df.columns:
			full_results['objective_value'] = full_results[objective]
		else:
			raise ValueError(f"Unsure what to do with objective '{objective}'")
		
		#for every instrument, lets get the top combinations? better to get highest performers? 
		#pdb.set_trace()
		return full_results[['instrument','tsi','strategy_ref','objective_value','ratio','N']] 
	

		

#used to iterate and find best settings/indicators to use for a signal provider. train and test modes 
#have an aggregate mode - get only the top winners then collect signals together by instrument & time 
class ExhaustiveSearch(SignalGenerator):  
	
	trigger_blocks = [] 
	stop_operators = []
	N = 3 #number of indicators to combine
	likeness = 1.0 #try 0.99   (any value > 1 means don't prune. 1.0 means exact matches only 
	
	filters = []
	
	#calculated values (for pruning the search)
	_ignored_triggers = [] 
	_invalid_trigger_pairs = []
	
	def __init__(self, N = 3):
		self.N = N
	
	@overrides(SignalGenerator)
	def train(self,trade_signalling_data,backtesting_data=None):
		backtesting_data = backtesting_data if backtesting_data is not None else trade_signalling_data
		all_trigger_results = self.run_triggers(trade_signalling_data)
		
		self._invalid_trigger_pairs = self.find_invalid_pairs()
		self._ignored_triggers = self.find_similar_triggers(all_trigger_results)
		
		stop_op = self.stop_operators[0]
		stop_data = stop_op.get_stops(trade_signalling_data)
		
		full_results = self.try_all_combinations(all_trigger_results,trade_signalling_data, backtesting_data,stop_data)
		return self.process_full_results(full_results)
	
	#return signals!
	@overrides(SignalGenerator)
	def infer(self, trade_signalling_data, inference_bubble_df): #for tests and usage 
		#here, we have an instruction set for our trading to use with the same set of trigger blocks 
		infer_df = inference_bubble_df.copy() #move this bit and below to selection method? 
		#actuals = infer_df[infer_df['objective_value'] > 0].sort_values('objective_value',ascending=False)
		
		#actuals = actuals.head(len(actuals)//2)
		#actuals = infer_df[(infer_df['ratio'] > 0.55) & (infer_df['objective_value'] > 0)]#
		#actuals['N_rank'] = actuals['N'].rank(method="dense", ascending=False) #sorts by number of trades desc -set with copy warning
		#actuals = actuals[actuals['N_rank'] > 25] #top 12 results 
		
		#pdb.set_trace()
		#actuals["rank"] = actuals.groupby("instrument")["objective_value"].rank(method="dense", ascending=False)
		#actuals = actuals[actuals['rank'] < 4]
		print('check actuals') 
		executable_combs = defaultdict(list) 
		used_indicators = np.zeros(len(self.trigger_blocks)).astype(np.int)
		for comb, df in infer_df.groupby('combination'):
			executable_combs[comb] = list(df['instrument'])
			#pdb.set_trace()
			used_indicators[list(comb)] += 1
		
		trigger_results = self.run_triggers(trade_signalling_data,np.where(used_indicators > 0)[0])
		
		stop_op = self.stop_operators[0]#work out how to do this with multiple stop tools 
		stop_data = stop_op.get_stops(trade_signalling_data)
		
		#pdb.set_trace()
		combs = executable_combs.keys()
		all_signals = self.get_signals(trigger_results, trade_signalling_data, stop_data,combs)
		
		return_signals = [] 
		#remove any instruments on combinations we do not want 
		for comb, signals in zip(combs,all_signals): #crude but works 
			return_signals += [s for s in signals if s.instrument in executable_combs[comb]]
		
		#pdb.set_trace() 
		#print('todo')
		
		return return_signals
			
	
	def run_triggers(self,trade_signalling_data,trigger_indexs=None):
		num_containers = len(self.trigger_blocks)
		np_candles = trade_signalling_data.np_candles
		results = np.full((np_candles.shape[0],np_candles.shape[1],num_containers,2),False)   #size?
		for i,lc in enumerate(self.trigger_blocks):
			if trigger_indexs is not None and i not in trigger_indexs:
				continue
			bullish, bearish = lc(np_candles)
			results[:,:,i,0] = bullish
			results[:,:,i,1] = bearish
		return results 
	
	def find_similar_triggers(self,all_trigger_results):
		num_containers = len(self.trigger_blocks)
		
		similar_triggers = set() 
		
		for i in range(num_containers):
			for j in range(i+1,num_containers):
				if i in similar_triggers or j in similar_triggers: 
					continue
				trigger_i = all_trigger_results[:,:,i]
				trigger_j = all_trigger_results[:,:,j]
				
				similarity = np.sum(trigger_i == trigger_j) / (np.prod(all_trigger_results.shape[0:2]) * 2) # bullish, bearish so x2
				if similarity >= self.likeness:
					#pdb.set_trace()
					similar_triggers.add(i)
				
		return list(similar_triggers) 
		
	def find_invalid_pairs(self):	
		#return lists of pairs of trigger blocks that should not go together 
		num_containers = len(self.trigger_blocks)
		invalid_islands = [moving_averages, chart_patterns]
		
		pairs = []
		
		for i in range(num_containers):
			for j in range(i+1,num_containers):
				ind1 = self.trigger_blocks[i].indicator.__class__
				ind2 = self.trigger_blocks[j].indicator.__class__
				
				
				#pdb.set_trace() #check for class name equality 
				if ind1.__name__ == ind2.__name__: #experimental - don't have same indicators
					pairs.append((i,j))
					continue
				
				for island in invalid_islands:
					if ind1 in island and ind2 in island:
						pairs.append((i,j))
						break
				
		return pairs 
	
	#objective is to maximise profits - this always max 
	def process_full_results(self,results_df,objective='output_balance'): #sort by money on each instrument 
		
		full_results = results_df.copy()
		#pdb.set_trace()
		if callable(objective):
			full_results['objective_value'] = objective(full_results) #check - may need lambda or something
		elif objective in results_df.columns:
			full_results['objective_value'] = full_results[objective]
		else:
			raise ValueError(f"Unsure what to do with objective '{objective}'")
		
		#for every instrument, lets get the top combinations? better to get highest performers? 
		#pdb.set_trace()
		return full_results[['instrument','combination','objective_value','ratio','N']] 
	
	def pruned(self,comb):
		#first, check if any comb is in similar_triggers to prevent using  
		#pdb.set_trace()
		if np.intersect1d(comb,self._ignored_triggers).size:
			return True #prune as this combination contains a removed trigger block 
		
		#any other checks here (eg prevent EMAs being used together or something)
		all_isin = np.isin(self._invalid_trigger_pairs,comb)
		
		if np.any(np.all(all_isin,axis=1)):
			return True 
		
		return False
	
	
	def get_signals(self,trigger_results, trade_signalling_data, stop_data, combinations):				
		all_signals = []
		
		for comb in tqdm(combinations):
			#pdb.set_trace()
				
			name = comb #necessary?
			bullish = np.all(trigger_results[:,:,comb,0],axis=2) #zero to 1 tools?
			bearish = np.all(trigger_results[:,:,comb,1],axis=2)
			
			if True:
				bullish = Zero2OneTool.markup(bullish)
				bearish = Zero2OneTool.markup(bearish)
			
			all_signals.append(SignalGenerator.create_signals(name,bullish,bearish,stop_data,trade_signalling_data))
		return all_signals
	
	def try_all_combinations(self, trigger_results, trade_signalling_data, backtesting_data, stop_data):
		
		
		print('get all signals')
		num_containers = len(self.trigger_blocks)
		container_combs = itertools.combinations(range(num_containers),self.N) 
		
		pruned_comb = [comb for comb in container_combs if not self.pruned(comb)]
		all_signals = self.get_signals(trigger_results,trade_signalling_data,stop_data,pruned_comb)
			
		full_results = [] 
		
		#pdb.set_trace()
		backtester = BackTesterCandles(backtesting_data)
		
		#use a cache? 
		
		#filters? 
		
		#pdb.set_trace() 
		#signals_ns = [len(signals) for signals in all_signals]
		
		
		print('backtest all signals')
		for comb,signals in tqdm(list(zip(pruned_comb,all_signals))):
			n_signals = len(signals)
			if 0 < n_signals < 3000: ##TODO calc for: ~1000 / month?
				results = backtester.perform(signals)
				statstool = BackTestStatistics(backtesting_data,signals,results)
				result_df = statstool.calculate()  #add to pile for sorting 
				result_df.insert(0,'combination',[comb]*len(result_df))
				full_results.append(result_df)

		full_results_df = pd.concat(full_results) 
		
		#with open('results/full_results.pkl','wb') as f: #save result for faster playing with later 
		#	pickle.dump(full_results_df,f)
			
		return full_results_df
	
	
	
	
	
	

## file for performing basc search strategy - first search among iterators for best performing combinations
#also use more advanced search methods eg local search or gla for larger datasets 

import itertools #going to want all combinations of iterators
from collections import defaultdict
from enum import Enum
import numpy as np 
import pandas as pd
from tqdm import tqdm
import uuid

import pdb


from backtest import BackTesterCandles, BackTesterCache, BackTestStatistics
from charting import candle_stick_functions as csf

from setups.trade_setup import blank_result, TradeSetup, TradeDirection
from setups.setup_tools import Zero2OneTool
from setups.collected_setups import Harmony, Trends, Shapes

from strategy.strategy_components import TriggerBlock, SetupBlock
from strategy.trigger_block_lists import moving_averages, chart_patterns, trends_group, oscillators_group, momentum_group #more? 

from utils import overrides 

import debugging.functs as dbf


def _len_func_try(x):
	try:
		return len(x)
	except (ValueError,TypeError) as e:
		return 1 #correct? 


def is_pareto_efficient(costs, return_mask = True):
	"""
	Find the pareto-efficient points
	:param costs: An (n_points, n_costs) array
	:param return_mask: True to return a mask
	:return: An array of indices of pareto-efficient points.
		If return_mask is True, this will be an (n_points, ) boolean array
		Otherwise it will be a (n_efficient_points, ) integer array of indices.
	"""
	is_efficient = np.arange(costs.shape[0])
	n_points = costs.shape[0]
	next_point_index = 0  # Next index in the is_efficient array to search for
	while next_point_index<len(costs):
		nondominated_point_mask = np.any(costs<costs[next_point_index], axis=1)
		nondominated_point_mask[next_point_index] = True
		is_efficient = is_efficient[nondominated_point_mask]  # Remove dominated points
		costs = costs[nondominated_point_mask]
		next_point_index = np.sum(nondominated_point_mask[:next_point_index])+1
	if return_mask:
		is_efficient_mask = np.zeros(n_points, dtype = bool)
		is_efficient_mask[is_efficient] = True
		return is_efficient_mask
	else:
		return is_efficient


class SignalShieldMethod(Enum):
	XOR_COLLECT = 1 # standard way - use mainly with same TP and SL as will use first values
	DEMOCRATIC = 2 # combination way of thinking - (average?) TP and SL and go with more methods for BUY or SELL 
	HIGH_SWAYED = 3 # democratic but diff is larger than 2 - use MAX TP and SL vals and only buy or sell for overwhelming majority 1.367
	
	
#for removing duplicate signals and signals that conflict with eachother (eg signals that have the same instrument & entry times)
class SignalShield:
	
	trade_signalling_data = None
	method = SignalShieldMethod.XOR_COLLECT
	
	def __init__(self,trade_signalling_data):
		self.trade_signalling_data = trade_signalling_data 
		#if 
	
	def _build_shield(self,signals_df):	
		signals_df = signals_df.copy()  #lose changes 
		
		#get the instrument indexs 
		signals_df['instrument_index'] = self.trade_signalling_data.instrument_indexs(signals_df['instrument'])
		
		#get the timeline indexes
		signals_df['timeline_index'] = self.trade_signalling_data.timeline_indexs(signals_df['the_date'])
		
		buys_df = signals_df[signals_df['direction'] == TradeDirection.BUY]
		sells_df = signals_df[signals_df['direction'] == TradeDirection.SELL]
		
		buy_strategies_df = buys_df.groupby(['instrument','the_date'],as_index=False).agg(list)
		sell_strategies_df = sells_df.groupby(['instrument','the_date'],as_index=False).agg(list)
		
		collected_df = pd.merge(buy_strategies_df,sell_strategies_df,on=['instrument','the_date'],how='outer',suffixes=['_buy','_sell'])
		
		return collected_df			
		
	
	def xor_collect(self,collected_df):
		return_df = pd.DataFrame([]) #build this 
		
		first_func = lambda x : x[0] if x else None
		len_func = _len_func_try
		catter = lambda xs : '\n'.join(xs)
		new_guid = lambda x : str(uuid.uuid4())
		
		winnng_df = pd.DataFrame([])
		winning_df_buys = collected_df[pd.isna(collected_df['strategy_ref_sell'])]#xor bit
		winning_df_sells = collected_df[pd.isna(collected_df['strategy_ref_buy'])]
		
		winning_buys = pd.DataFrame([])
		winning_sells = pd.DataFrame([])
		
		winning_buys['instrument'] = winning_df_buys['instrument']
		winning_buys['the_date'] = winning_df_buys['the_date']
		winning_buys['strategy_ref'] = winning_df_buys['strategy_ref_buy'].apply(catter) ##collect all the strategy refs 
		winning_buys['direction'] = TradeDirection.BUY
		winning_buys['entry'] = winning_df_buys['entry_buy'].apply(first_func)
		winning_buys['entry_cut'] = winning_df_buys['entry_cut_buy'].apply(first_func)
		winning_buys['entry_expire'] = winning_df_buys['entry_expire_buy'].apply(first_func)
		winning_buys['take_profit_distance'] = winning_df_buys['take_profit_distance_buy'].apply(first_func)
		winning_buys['stop_loss_distance'] = winning_df_buys['stop_loss_distance_buy'].apply(first_func)
		winning_buys['length'] = winning_df_buys['length_buy'].apply(first_func)
		winning_buys['signal_id'] = winning_df_buys['signal_id_buy'].apply(new_guid)
		
		winning_sells['instrument'] = winning_df_sells['instrument']
		winning_sells['the_date'] = winning_df_sells['the_date']
		winning_sells['strategy_ref'] = winning_df_sells['strategy_ref_sell'].apply(catter) ##collect all the strategy refs 
		winning_sells['direction'] = TradeDirection.SELL
		winning_sells['entry'] = winning_df_sells['entry_sell'].apply(first_func)
		winning_sells['entry_cut'] = winning_df_sells['entry_cut_sell'].apply(first_func)
		winning_sells['entry_expire'] = winning_df_sells['entry_expire_sell'].apply(first_func)
		winning_sells['take_profit_distance'] = winning_df_sells['take_profit_distance_sell'].apply(first_func)
		winning_sells['stop_loss_distance'] = winning_df_sells['stop_loss_distance_sell'].apply(first_func)
		winning_sells['length'] = winning_df_sells['length_sell'].apply(first_func)
		winning_sells['signal_id'] = winning_df_sells['signal_id_sell'].apply(new_guid)
		
		#pdb.set_trace()
		return_df = return_df.append(winning_buys)
		return_df = return_df.append(winning_sells)
		
		return return_df
	
	def democratic(self,collected_df):
		
		return_df = pd.DataFrame([]) #build this 
		
		first_func = lambda x : x[0] if x else None
		len_func = _len_func_try
		catter = lambda xs : '\n'.join(xs)
		new_guid = lambda x : str(uuid.uuid4())
		
		winnng_df = pd.DataFrame([])
		collected_df['n_buys'] = collected_df['strategy_ref_buy'].str.len().fillna(0)
		collected_df['n_sells'] = collected_df['strategy_ref_sell'].str.len().fillna(0)
		
		winning_df_buys = collected_df[collected_df['n_buys'] > collected_df['n_sells']]
		winning_df_sells = collected_df[collected_df['n_sells'] > collected_df['n_buys']]
		
		winning_buys = pd.DataFrame([])
		winning_sells = pd.DataFrame([])
		
		winning_buys['instrument'] = winning_df_buys['instrument']
		winning_buys['the_date'] = winning_df_buys['the_date']
		winning_buys['strategy_ref'] = winning_df_buys['strategy_ref_buy'].apply(catter) ##collect all the strategy refs 
		winning_buys['direction'] = TradeDirection.BUY
		winning_buys['entry'] = winning_df_buys['entry_buy'].apply(first_func)
		winning_buys['entry_cut'] = winning_df_buys['entry_cut_buy'].apply(first_func)
		winning_buys['entry_expire'] = winning_df_buys['entry_expire_buy'].apply(first_func)
		winning_buys['take_profit_distance'] = winning_df_buys['take_profit_distance_buy'].apply(first_func)
		winning_buys['stop_loss_distance'] = winning_df_buys['stop_loss_distance_buy'].apply(first_func)
		winning_buys['length'] = winning_df_buys['length_buy'].apply(first_func)
		winning_buys['signal_id'] = winning_df_buys['signal_id_buy'].apply(new_guid)
		
		winning_sells['instrument'] = winning_df_sells['instrument']
		winning_sells['the_date'] = winning_df_sells['the_date']
		winning_sells['strategy_ref'] = winning_df_sells['strategy_ref_sell'].apply(catter) ##collect all the strategy refs 
		winning_sells['direction'] = TradeDirection.SELL
		winning_sells['entry'] = winning_df_sells['entry_sell'].apply(first_func)
		winning_sells['entry_cut'] = winning_df_sells['entry_cut_sell'].apply(first_func)
		winning_sells['entry_expire'] = winning_df_sells['entry_expire_sell'].apply(first_func)
		winning_sells['take_profit_distance'] = winning_df_sells['take_profit_distance_sell'].apply(first_func)
		winning_sells['stop_loss_distance'] = winning_df_sells['stop_loss_distance_sell'].apply(first_func)
		winning_sells['length'] = winning_df_sells['length_sell'].apply(first_func)
		winning_sells['signal_id'] = winning_df_sells['signal_id_sell'].apply(new_guid)
		
		#pdb.set_trace()
		return_df = return_df.append(winning_buys)
		return_df = return_df.append(winning_sells)
		return return_df
	
	def high_sway(self,collected_df):
		collected_df
		
	def get_signals(self,signals_df):
		shield = self._build_shield(signals_df)
		
		collected_signals_df = pd.DataFrame([])
		
		if self.method == SignalShieldMethod.XOR_COLLECT:
			collected_signals_df = self.xor_collect(shield)
			
		elif self.method == SignalShieldMethod.DEMOCRATIC: #take average stops and go with higher votes for buy/sell
			collected_signals_df = self.democratic(shield)
		
		elif self.method == SignalShieldMethod.HIGH_SWAYED: #take max stops and go with overly favoured buy/sell (eg 3 apart)
			collected_signals_df = self.high_sway(shield)
		
		else:
			raise NotImplementedError(f"Unknown method {self.method}.")
		
		return collected_signals_df

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
	

		
#class CombinationCutter #consider separate class for handling the pruning of combinations 
class CombinationChoice: #class for chosing best combinations from backtest results 
	
	
	#def __init__(self):
	#	#self.backtest_results_df = backtest_results_df
	
	def get_choice(self, backtest_results_df):
		suggestions = self.backtest_results_df[backtest_results_df['objective_value'] > 0]
		suggestions.sort_values('objective_value',ascending=False)
		return suggestions.head(250)
	
	def apply_bounds(self, backtest_results_df, ratio=0.5, nlb=10, nhb=0, streak_diff=5):
		good_ratio = backtest_results_df['ratio'] >= ratio
		good_n = backtest_results_df['N'] >= nlb
		good_n = good_n & (backtest_results_df['N'] <= nhb) if nhb > 0 else good_n
		streak_control = True
		if type(streak_diff) == int: 
			streak_control = backtest_results_df['win_streak'] > backtest_results_df['lose_streak'] + streak_diff
		return backtest_results_df[good_ratio & good_n & streak_control]
		
	
	def get_pareto_optimals(self,backtest_results_df): #use passed param instead?
		#set up costs here 
		#pdb.set_trace()
		#ratio, lose streak, n trades, trade duration, output balance, 
		
		costs = np.zeros((len(backtest_results_df),5))
		costs[:,0] = -backtest_results_df['ratio'].to_numpy()
		costs[:,1] = -backtest_results_df['N']
		costs[:,2] = backtest_results_df['lose_streak']
		costs[:,3] = -backtest_results_df['output_balance']
		costs[:,4] = backtest_results_df['average_duration']
		
		mask = is_pareto_efficient(costs)
		return backtest_results_df[mask]
	
	def get_top_each(self, backtest_results_df, top=10):
		#pdb.set_trace()
		instruments = backtest_results_df['instrument'].unique()
		result_dfs = []
		#backtest_sorted_df = backtest_results_df.sort_values(by=['output_balance'],ascending=False)
		
		for instrument in instruments:
			backtest_instrument_df = backtest_results_df[backtest_results_df['instrument'] == instrument]
			result_dfs.append(backtest_instrument_df.sort_values(by=['output_balance'],ascending=False).head(top))
	
		result_df = pd.concat(result_dfs)
		return result_df	
	
	def get_bottom_each(self, backtest_results_df, top=10):
		#pdb.set_trace()
		instruments = backtest_results_df['instrument'].unique()
		result_dfs = []
		#backtest_sorted_df = backtest_results_df.sort_values(by=['output_balance'],ascending=False)
		
		for instrument in instruments:
			backtest_instrument_df = backtest_results_df[backtest_results_df['instrument'] == instrument]
			result_dfs.append(backtest_instrument_df.sort_values(by=['output_balance']).head(top))
	
		result_df = pd.concat(result_dfs)
		return result_df	
			

#used to iterate and find best settings/indicators to use for a signal provider. train and test modes 
#have an aggregate mode - get only the top winners then collect signals together by instrument & time 
class ExhaustiveSearch(SignalGenerator):  
	
	trigger_blocks = [] 
	stop_tool = None
	N = 3 #number of indicators to combine
	likeness = 1.0 #try 0.99   (any value > 1 means don't prune. 1.0 means exact matches only 
	cache_backtests = False # seems caching is slower
	
	max_trades_per_day = 5 #use for upper bound on backtesting signals 
	
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
		
		full_results = self.try_all_combinations(all_trigger_results,trade_signalling_data, backtesting_data)
		return self.set_objective_value(full_results) #pass an objective function if there is one 

	
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
		
		#pdb.set_trace()
		combs = np.array(infer_df['combination'].to_list())
		used_indicators = np.full(len(self.trigger_blocks),False)
		used_indicators[combs] = True #nice trick! 
		
		
		keep_combinations = infer_df[['combination','instrument']].copy()
		keep_combinations['key'] = keep_combinations['combination'].astype(str)
		trigger_results = self.run_triggers(trade_signalling_data,np.where(used_indicators)[0])
				
		#pdb.set_trace()
		#pdb.set_trace()
		run_combs = np.unique(combs,axis=0)
		#pdb.set_trace()
		all_signals = self.get_signals(trigger_results, trade_signalling_data, run_combs)
	
		return_signals = pd.DataFrame([])
		
		keys = [str(list(comb)) for comb in run_combs] #match up with astype(str) from DF above 
		for this_key, signals in zip(keys,all_signals):
			keep_instruments = keep_combinations[keep_combinations['key'] == this_key]['instrument']
			return_signals = return_signals.append(signals[signals['instrument'].isin(keep_instruments)])
		
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
				tb1 = self.trigger_blocks[i]
				tb2 = self.trigger_blocks[j]
				ind1 = tb1.indicator
				ind2 = tb2.indicator
				
				if type(self.trigger_blocks[i]) == SetupBlock and type(self.trigger_blocks[j]) == SetupBlock:
					pairs.append((i,j)) #dont collect setups together 
				
				#pdb.set_trace() #check for class name equality 
				if ind1 is None or ind2 is None: 
					continue 
					
				if ind1.__class__.__name__ == ind2.__class__.__name__: #experimental - don't have same indicators
					#keep divergences 
					if ('divergence' in tb1.note) != ('divergence' in tb2.note): #don't have two divs waste
						continue
						
					pairs.append((i,j))
					continue
				
				for island in invalid_islands:#dont pair things together on same islands 
					if ind1.__class__ in island and ind2.__class__ in island:
						pairs.append((i,j))
						break
				
		return pairs 
	
	def set_objective_value(self,results_df,objective='output_balance'): #sort by money on each instrument 
		
		#full_results = results_df.copy()
		#pdb.set_trace()
		if objective is not None and 'objective_value' not in results_df.columns:
			if callable(objective):
				results_df['objective_value'] = objective(results_df) #check - may need lambda or something
			elif objective in results_df.columns:
				results_df['objective_value'] = results_df[objective]
		#else:
		#	raise ValueError(f"Unsure what to do with objective '{objective}'")

		return results_df
	
	#consider a pruning class
	def prune_max_island(self,combinations,class_island,max_num):
		#pdb.set_trace()
		class_names = [clz.__name__ for clz in class_island]
		trigger_indexs = [i for (i,tb) in enumerate(self.trigger_blocks) if type(tb) == TriggerBlock and tb.indicator.__class__.__name__ in class_names]
		combination_hits = np.isin(combinations,trigger_indexs)
		comb_indexer = np.sum(combination_hits,axis=1) <= max_num
		return combinations[comb_indexer]
		
		
	def prune_combinations(self,combinations):
	#	print(f"combs before max islands: {len(combinations)}")
		combinations = self.prune_max_island(combinations,oscillators_group,3)
		combinations = self.prune_max_island(combinations,trends_group,3)
		combinations = self.prune_max_island(combinations,momentum_group,3)
	#	print(f"combs after max islands: {len(combinations)}")
		return [comb for comb in combinations if self.pruned(comb)]
	
	def pruned(self,comb): #remove once vectorized (if it is possible!)
		#first, check if any comb is in similar_triggers to prevent using  
		#pdb.set_trace()
		if np.intersect1d(comb,self._ignored_triggers).size:
			return True #prune as this combination contains a removed trigger block 
		
		#any other checks here (eg prevent EMAs being used together or something)
		all_isin = np.isin(self._invalid_trigger_pairs,comb)
		
		if np.any(np.all(all_isin,axis=1)):
			return True 
		
		return False
	
	
	def get_signals(self,trigger_results, trade_signalling_data, combinations):				
		
		instruments = trade_signalling_data.instruments
		timeline = trade_signalling_data.timeline
		filter_mask = np.full((len(instruments),len(timeline)),True)
		
		stop_data = self.stop_tool.get_stops(trade_signalling_data)
		
		all_signals = [] #change from list to df? 
		
		for f in self.filters:
			filter_mask = filter_mask & f.extract_mask(instruments,timeline)
		
		for comb in tqdm(combinations):

			bullish = np.all(trigger_results[:,:,comb,0],axis=2) #zero to 1 tools?
			bearish = np.all(trigger_results[:,:,comb,1],axis=2)
			
			name = self.__class__.__name__+'@'+str(list(comb)) #use a human-readable name for later
			
			if True: #before or after filter?
				bullish = Zero2OneTool.markup(bullish)
				bearish = Zero2OneTool.markup(bearish)
			
			bullish = bullish & filter_mask
			bearish = bearish & filter_mask
			
			signals = SignalGenerator.create_signals(name,bullish,bearish,stop_data,trade_signalling_data)
			all_signals.append(signals)
	
		return all_signals
		
	
	def try_all_combinations(self, trigger_results, trade_signalling_data, backtesting_data):
		
		
		print('get all signals')
		num_containers = len(self.trigger_blocks)
		
		#any way to cast to lists without loop?
		container_combs = np.array([list(comb) for comb in itertools.combinations(range(num_containers),self.N)])
		pruned_comb = self.prune_combinations(container_combs)
		
		print(f"Combinations: {len(container_combs)}, Pruned: {len(pruned_comb)}")
		all_signals = self.get_signals(trigger_results,trade_signalling_data,pruned_comb)
			
		full_results = [] 
		
		backtester = BackTesterCandles(backtesting_data)
		
		backtester_cache = backtester
		if self.cache_backtests: #cache 
			backtester_cache = BackTesterCache(backtester)
		
		#pdb.set_trace() 
		#signals_ns = [len(signals) for signals in all_signals]
		n_days = abs((trade_signalling_data.timeline[-1] - trade_signalling_data.timeline[0]).days)
		n_trading_days = n_days * (5/7)
		n_instruments = len(trade_signalling_data.instruments)
		
		n_signals_ub = max(n_trading_days,1) * n_instruments * self.max_trades_per_day
		
		dbf.stopwatch('backtest all signals')
		for comb,signals in tqdm(list(zip(pruned_comb,all_signals))):
			
			n_signals = len(signals.index)
			
			if 0 < n_signals < n_signals_ub:
				results = backtester_cache.perform(signals)
				statstool = BackTestStatistics(backtesting_data,signals,results)
				result_df = statstool.calculate()  #add to pile for sorting 
				result_df.insert(0,'combination',[list(comb)]*len(result_df))
				full_results.append(result_df)
		
		dbf.stopwatch('backtest all signals')
		
		full_results_df = pd.concat(full_results) 
		
		#with open('results/full_results.pkl','wb') as f: #save result for faster playing with later 
		#	pickle.dump(full_results_df,f)
		return full_results_df
	
	
	
	def _backtest_cache(self,signals):
		results = [] 
		#therunther
	
	
	
	

## file for performing basc search strategy - first search among iterators for best performing combinations


import itertools #going to want all combinations of iterators
import numpy as np 


from backtest import BackTesterCandles, BackTestStatistics
from charting import candle_stick_functions as csf


import pdb

#container class for holding an indicator, and a function specifying buy/sell direction based on the indicator and the candles
class LambdaContainer: #inner class? #rename => TriggerBlock or similar? 
	
	bullish_funct = None 
	bearish_funct = None
	indicator = None 
	note = 'blank'
	
	def __init__(self, indicator, bullish_funct, bearish_funct, note=''):
		self.indicator = indicator
		self.note = note
		self.bullish_funct = bullish_funct
		self.bearish_funct = bearish_funct
	
	def __call__(self,np_candles):
		result = self.indicator(np_candles)
		return self.bullish_funct(result,np_candles), self.bearish_funct(result,np_candles)

#ema = LambdaContainer(EMA(200), lambda res, npc : npc[:,:,csf.close] > res[:,:,0], lambda res, npc : npc[:,:,csf.close] < res[:,:,0], 'clearence close only')

#used to iterate and find best settings/indicators to use for a signal provider. train and test modes 
class IterativeSearch: #(SignalGenerator?) 
	
	lambda_containers = [] 
	stop_operators = []
	N = 3 #number of indicators to combine
	
	trade_signalling_data = None 
	backtesting_data = None
	
	#generated
	result_settings = {} #set this when finding new signals 
	
	def __init__(self, N = 3):
		self.N = N
	
	def pass_data(self,trade_signalling_data, backtesting_data=None):
		self.trade_signalling_data = trade_signalling_data
		self.backtesting_data = backtesting_data if backtesting_data is not None else trade_signalling_data
	
	def main(self):
		full_results = self.all_biases()
		self.main_iterate(full_results)
	
	def all_biases(self):
		num_containers = len(self.lambda_containers)
		np_candles = self.trade_signalling_data.np_candles
		results = np.full((np_candles.shape[0],np_candles.shape[1],num_containers,2),False)   #size?
		for i,lc in enumerate(self.lambda_containers):
			bullish, bearish = lc(np_candles)
			results[:,:,i,0] = bullish
			results[:,:,i,1] = bearish
		return results 
	
	def create_signals(self, name, bullish, bearish, stop_stuff):
		
		(bullish_tp, bullish_sl, bearish_tp, bearish_sl) = stop_stuff
		trade_signalling_data = self.trade_signalling_data #possible crossref err
		
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
	
	def process_full_results(self,results): #sort by money on each instrument 
		pass
	
	def pruned(self,comb):
		return False
	
	def main_iterate(self, all_results):
		stop_op = self.stop_operators[0]
		stop_data = stop_op.get_stops(self.trade_signalling_data)
		
		num_containers = len(self.lambda_containers)
		container_combs = itertools.combinations(range(num_containers),self.N)
		
		backtester = BackTesterCandles(self.backtesting_data)
		
		pdb.set_trace()
		
		full_results = []
		
		for comb in container_combs:
			#pdb.set_trace()
			
			if self.pruned(comb):
				continue 
				
			name = comb #necessary?
			bullish = np.all(all_results[:,:,comb,0],axis=2) #zero to 1 tools?
			bearish = np.all(all_results[:,:,comb,1],axis=2)
			
			signals = self.create_signals(name,bullish,bearish,stop_data) 
			
			results = backtester.perform(signals)
			statstool = BackTestStatistics(self.backtesting_data,signals,results)
			full_result = statstool.calculate()  #add to pile for sorting 
			full_results.append((comb, full_result))
			
		combination_lists = self.process_full_results(full_results)
	
	
	
	
	
	
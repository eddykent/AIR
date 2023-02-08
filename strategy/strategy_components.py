##main strategy components 




#container class for holding an indicator, and a function specifying buy/sell direction based on the indicator and the candles
class TriggerBlock: #inner class? #rename => TriggerBlock or similar? 
	
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

#ema = TriggerBlock(EMA(200), lambda res, npc : npc[:,:,csf.close] > res[:,:,0], lambda res, npc : npc[:,:,csf.close] < res[:,:,0], 'clearence close only')

default_bullish_funct = lambda res, npc : res[:,:,0] > 0
default_bearish_funct = lambda res, npc : res[:,:,0] < 0

class SetupBlock: #use with trigger() functions on setups 
	
	trade_setup = None 
	trade_signalling_data = None
	note = 'blank'
	
	indicator = None #needed for later :/
	
	def __init__(self, trade_setup, trade_signalling_data, note=''):
		self.trade_setup = trade_setup
		self.trade_signalling_data = trade_signalling_data
		self.note = note
	
	def __call__(self, np_candles):
		return self.trade_setup.trigger(self.trade_signalling_data)
	


##piece that needs to be optimised








#online always-run things  
class DataRefresher: #get most recent info into the database (price, volume, stories, ) 
	pass

class SignalGenerator: #use collection of setups to create list of signals 
	#exhaustive search, local search? genetic? (if so, how?) GLS with - balance each iteration to attempt to make other choices 
	#over fitting issues - add error values, use a modified/fuzzy obj function, use weighted choice of result, normalise somehow? 
	pass

class FilterChecker: #check signals against each other and also against filters 
	pass
	
class Executor:
	pass




#offline updaters to set new variables 
class Backtester: #backtest setups and filters for best performers 
	pass

class Searcher: #search additional for best setups/filters 
	pass

class Trainer: #train AI models for better weights 
	pass
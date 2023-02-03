##main strategy components 

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
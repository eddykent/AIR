## setups are trades that have been produced from signals from various sources. A TradeSetup class finds trades on a given date 
#that have a high probabily of winning based on their backtest results.  TradeSetup classes need to be backtestable 




from utils import ListFileReader, Database
from trade_schedule import TradeSignal, TradeDirection


class TradeSetup:	
	
	instruments = []# pairs we want to find trades for 
	currencies = [] # currencies we might use 
	
	trades = []
	
	#def __init__(self):
	#	pass #lfr = ListFileReader()
	
	def setup(self):
		lft = ListFileReader()
		
		if not self.instruments:
			self.instruments = lfr.read('fx_pairs/fx_mains.txt')
		
		if not self.currencies:
			self.currencies = lfr.read('fx_pairs/currencies.txt')
	
	# return any trades that hit a bullish or bearish status from any sources (chart patterns? indicators?) 
	# return the most recent that are on this self.the_date 
	def get_trades(self):
		pass 
	
	# return all trade schedules for all times - a dict of datetime:[Trade]- it is up to a TradeSchedule to evaluate - we focus on signal generation!
	def full_backtest(self):
		pass
	


class SimpleHarmonicSetup(TradeSetup):
	#iterate through the harmonic patterns and report any that are bullish/bearish
	pass



##https://www.youtube.com/watch?v=4dVB_g5YeSE  
##keep it simple - all chart pattern objects should only look at one timeframe. A setup looks at many.
#find trendline/support&resistance from higher timeframe and divergence from this and lower timeframe, and breakout from lower timeframe
class RSIDivergence(TradeSetup):
	   
	def __init__(self):
		pass
	
	#override
	@staticmethod
	def to_candles(sequence,instrument):
		return sorted([
			[
				snapshot[2][instrument]['open_price'],
				snapshot[2][instrument]['high_price'],	
				snapshot[2][instrument]['low_price'],
				snapshot[2][instrument]['close_price'],
				snapshot[2][instrument]['relative_strength_index'],   ##will be needed to detect divergence
				snapshot[0] #datetime for debugging if needed...
			]
		for snapshot in sequence],key=lambda c:c[4]) #sort into chronological order 







#we know his strategy & we can improve it with some extra timeframes!
class ForexSignalsEngulferPinbar(TradeSetup):
	pass
	






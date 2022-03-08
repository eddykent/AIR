## setups are trades that have been produced from signals from various sources. A TradeSetup class finds trades on a given date 
#that have a high probabily of winning based on their backtest results.  TradeSetup classes need to be backtestable 
from enum import Enum
from collections import namedtuple


from utils import ListFileReader, Database


class TradeDirection(Enum):
	SELL = -1
	VOID = 0 
	BUY = 1

class StopType(Enum):
	PERCENTAGE = 0 #use a percentage difference in the price as the take profit and stop loss targets
	ATR = 1 # use a multiple of the average true range 
	STD = 2 # use a multiple of standard deviations 
	KEY = 3 # use a particular feature in the indicator/pattern  

#if "sell if x exceeds y" etc - used for generating signals from indicators or chart patterns etc. stoploss can be a key to use, or a percent etc 
SetupCriteria = namedtuple('SetupCriteria','direction property1 ineq property2 stop_type stop_loss take_profit') 

##A tuple representing a trade that will be taken that has some bounds on it (stop_loss & take_profit)
class TradeSignal:
	the_date = None   #datetime - the time the signal was created 
	strategy = '' #the strategy that this came from 
	instrument = None  #the instrument that is being traded
	direction = TradeDirection.VOID  # a buy or sell (void means to be ignored/deleted)
	entry = None #the entry price to start the trade at. If null, start immediately
	take_profit = 0  #the value to exit the trade at when it wins
	stop_loss = 0 #the value to exit the trade at when it loses
	length = 1440 #1440 minutes in 24 hours
	
	def __init__(self):
		pass  #not sure what to put here yet
		
	@staticmethod
	def from_simple(instrument,direction):
		this_signal = TradeSignal()
		this_signal.instrument = instrument
		this_signal.direction = direction
		return this_signal
	
	@staticmethod
	def from_full(datetime,instrument,strategy,direction,entry,take_profit,stop_loss,length=1440):
		this_signal = TradeSignal()
		this_signal.datetime = datetime 
		this_signal.instrument = instrument
		this_signal.strategy = strategy
		this_signal.direction = direction
		this_signal.entry = entry 
		this_signal.take_profit = take_profit
		this_signal.stop_loss = stop_loss
		this_signal.length = length
		return this_signal

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
	






## setups are trades that have been produced from signals from various sources. A TradeSetup class finds trades on a given date 
#that have a high probabily of winning based on their backtest results.  TradeSetup classes need to be backtestable 

from enum import Enum
from collections import namedtuple
import uuid
import math

from utils import ListFileReader, Database


class TradeDirection(Enum):
	SELL = -1
	VOID = 0 
	BUY = 1

class StopType(Enum):
	PERCENTAGE = 0 #use a percentage difference in the price as the take profit and stop loss targets
	ATR = 1 # use a multiple of the average true range 
	STD = 2 # use a multiple of standard deviations 
	KEY = 3 # use a particular feature in the indicator/pattern that is an array index
	EXPRESSION = 4 #advanced - an expression type that attempts to be parsed by ExpressionHandler(TODO! - maybe too much :) )

class ExpressionType(Enum):
	KEY = 0 #for example, macd or macd_signal 
	PERCENTAGE = 1
	VALUE = 2
	COMPOUND = 3 #used for when more than 1 key is used 
	

class Inequality(Enum):
	CROSS_DOWNWARDS = -3
	LESS_THAN = -2
	WITHIN = -1 #contained inside (usually refers to two values either side, used with expression, eg bollinger bands or something) 
	VOID = 0 #standard -means to be ignored/deleted
	OVERLAP = 1 #oposite to within? 
	MORE_THAN = 2
	CROSS_UPWARDS = 3

#if "sell if x exceeds y" etc - used for generating signals from indicators or chart patterns etc. stoploss can be a key to use, or a percent etc 
SetupCriteria = namedtuple('SetupCriteria','direction expr1 ineq expr2 stop_type stop_loss take_profit') 
#stop criteria separate?


##A tuple representing a trade that will be taken that has some bounds on it (stop_loss & take_profit)
class TradeSignal:
	signal_id = None #signal id to refer specifically to this signal 
	the_date = None   #datetime - the time the signal was created 
	strategy_ref = '' #the strategy that this came from - the class name of the trade_setup or whatever 
	instrument = None  #the instrument that is being traded
	direction = TradeDirection.VOID  # a buy or sell (void means to be ignored/deleted)
	entry = None #the entry price to start the trade at. If null, start immediately
	take_profit = 0  #the value to exit the trade at when it wins - flat price
	stop_loss = 0 #the value to exit the trade at when it loses - flat price
	length = 1440 #1440 minutes in 24 hours
	
	sql_row = "(%(signal_id)s,%(the_date)s,%(instrument)s,%(direction)s,%(entry)s,%(take_profit)s,%(stop_loss)s,%(length)s)"
	
	def __init__(self):
		self.signal_id = str(uuid.uuid4())
		
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
	
	def set_stops_current_distance(self,current_price,take_profit,stop_loss):
		pass
	
	def set_stops_entry_distance(self,take_profit,stop_loss):
		pass
	
	def set_stops_current_percentage(self,current_price,take_profit,stop_loss):
		pass
	
	def set_stops_entry_percentage(self,take_profit,stop_loss):
		pass
	
	
	def get_risk_reward_entry(self):
		assert self.entry not None, "Need an entry price for that!"
		return self.get_risk_reward_current(self.entry)
	
	def get_risk_reward_current(self,current_price):
		risk = math.abs(self.stop_loss - current_price)
		reward = math.abs(self.take_profit - current_price)
		return reward / risk
		
	def to_dict_row(self):
		direction_str = 'BUY' if self.direction = TradeDirection.BUY else 'SELL' if self.direction = TradeDirection.SELL else 'VOID'
		return {
			'signal_id':self.signal_id,
			'the_date':self.the_date,
			'instrument':self.instrument,
			'direction':direction_str,
			'entry':self.entry,
			'take_profit':self.take_profit,
			'stop_loss':self.stop_loss,
			'length':self.length
		}


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
	
	#def detect() - for AI 
	#def get_setups() - for backtest 
	#def get_latest() - for signals right now (short cut to not call for a backtest) 
	#def draw_snapshot() - perhaps add all stuff together that can be put on the chart? - consider what happens with RSI or MACD etc 
	
	

#https://medium.com/codex/trading-stocks-using-bollinger-bands-keltner-channel-and-rsi-in-python-980e87e8109d
class BB_KC_RSI(TradeSetup):
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
	






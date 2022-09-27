from enum import Enum
from collections import namedtuple
import uuid


#looks like you're setting up some kind of grammar!
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
	OVERLAP = 1 
	MORE_THAN = 2
	CROSS_UPWARDS = 3

#if "sell if x more_than y" etc - used for generating signals from indicators or chart patterns etc. stoploss can be a key to use, or a percent etc 
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
	entry_cut = None #cut the signal if the price goes in opposite direction and hits this value 
	entry_expire = 120 # expire the signal if entry price is not hit  (default 2 hours) 
	take_profit_distance = 0  #the value to exit the trade at when it wins 
	stop_loss_distance = 0 #the value to exit the trade at when it loses 
	length = 1440 #1440 minutes in 24 hours
	
	#sql_row = "(%(signal_id)s,%(the_date)s,%(instrument)s,%(direction)s,%(entry)s,%(take_profit_distance)s,%(stop_loss_distance)s,%(length)s)"
	sql_row = "(%(signal_id)s,%(the_date)s,%(instrument)s,%(direction)s,%(entry)s,%(entry_cut)s,%(entry_expire)s,%(take_profit_distance)s,%(stop_loss_distance)s,%(length)s)"
	
	def __init__(self):
		self.signal_id = str(uuid.uuid4())
		
	@staticmethod
	def from_simple(instrument,direction):
		this_signal = TradeSignal()
		this_signal.instrument = instrument
		this_signal.direction = direction
		return this_signal
		
	
	@staticmethod
	def from_full(the_date,instrument,strategy_ref,direction,entry,entry_cut,entry_expire,take_profit_distance,stop_loss_distance,length=1440):
		this_signal = TradeSignal()
		this_signal.the_date = the_date 
		this_signal.instrument = instrument
		this_signal.strategy_ref = strategy_ref
		this_signal.direction = direction
		this_signal.entry = entry,
		this_signal.entry_cut = entry_cut, 
		this_signal.entry_expire = entry_expire,
		this_signal.take_profit_distance = take_profit_distance
		this_signal.stop_loss_distance = stop_loss_distance
		this_signal.length = length
		return this_signal
	
	def set_stops(self,take_profit_distance,stop_loss_distance):
		self.take_profit_distance = take_profit_distance
		self.stop_loss_distance = stop_loss_distance
	
	def get_risk_reward_current(self,current_price):
		return self.take_profit_distance / self.stop_loss_distance
		
	def to_dict_row(self):
		direction_str = 'BUY' if self.direction == TradeDirection.BUY else 'SELL' if self.direction == TradeDirection.SELL else 'VOID'
		return {
			'signal_id':self.signal_id,
			'the_date':self.the_date,
			'instrument':self.instrument,
			'direction':direction_str,
			'entry':self.entry,
			'entry_cut':self.entry_cut,
			'entry_expire':self.entry_expire,
			'take_profit_distance':self.take_profit_distance,
			'stop_loss_distance':self.stop_loss_distance,
			'length':self.length
		}

#class TradeSignalPair:  -- will need an interest rate calculation
#	This class holds the concept of holding a trade - 
#	we can buy and leave open x candles or until another trade hold signal has fired instead of having a TP or SL. 
#	This is risky though and it is probably better to always use the TP and SL levels. 

class TradeSignalDataExtra:
	instruments = None
	timeline = None 
	name = None
	signals = [None, None]
	entries = [None, None]
	entry_cuts = [None, None]
	stop_loss_distances = [None , None]
	take_profit_distances = [None, None]
	







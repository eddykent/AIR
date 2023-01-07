from enum import Enum
from collections import namedtuple
import uuid
import datetime

import numpy as np

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
	strategy_ref = '' #the strategy that this came from usually the class name of the trade_setup 
	instrument = None  #the instrument that is being traded
	currency = None #the currency the instrument is traded in 
	direction = TradeDirection.VOID  # a buy or sell (void means to be ignored/deleted)
	entry = None #the entry price to start the trade at. If null, start immediately
	entry_cut = None #cut the signal if the price goes in opposite direction and hits this value 
	entry_expire = 120 # expire the signal if entry price is not hit  (default 2 hours) 
	take_profit_distance = 0  #the value to exit the trade at when it wins 
	stop_loss_distance = 0 #the value to exit the trade at when it loses 
	length = 1440 #1440 minutes in 24 hours
	
	#timeframe? 
	
	signal_notes = '' #anything that can be used later for reporting (eg filter results) 
	
	#sql_row = "(%(signal_id)s,%(the_date)s,%(instrument)s,%(direction)s,%(entry)s,%(take_profit_distance)s,%(stop_loss_distance)s,%(length)s)"
	sql_row = "(%(signal_id)s,%(strategy_ref)s,%(the_date)s,%(instrument)s,%(direction)s,%(entry)s,%(entry_cut)s,%(entry_expire)s,%(take_profit_distance)s,%(stop_loss_distance)s,%(length)s)"
	
	def __init__(self):
		self.signal_id = str(uuid.uuid4())
		
	@staticmethod
	def from_simple(instrument,direction):
		this_signal = TradeSignal()
		this_signal.instrument = instrument
		this_signal.direction = direction
		return this_signal
		
	
	@staticmethod
	def from_full(the_date,instrument,strategy_ref,direction,entry,entry_cut,entry_expire,take_profit_distance,stop_loss_distance,currency=None,length=1440,notes=''):
		this_signal = TradeSignal()
		this_signal.the_date = the_date 
		this_signal.instrument = instrument
		this_signal.currency = currency
		this_signal.strategy_ref = strategy_ref
		this_signal.direction = direction
		this_signal.entry = entry
		this_signal.entry_cut = entry_cut
		this_signal.entry_expire = entry_expire
		this_signal.take_profit_distance = take_profit_distance
		this_signal.stop_loss_distance = stop_loss_distance
		this_signal.length = length
		this_signal.signal_notes = notes
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
			'strategy_ref':self.strategy_ref,
			'entry':self.entry,
			'entry_cut':self.entry_cut,
			'entry_expire':self.entry_expire,
			'take_profit_distance':self.take_profit_distance,
			'stop_loss_distance':self.stop_loss_distance,
			'length':self.length
		}
	
	def to_dict(self):
		return {
			'signal_id':self.signal_id,
			'the_date':self.the_date,
			'instrument':self.instrument,
			'currency':self.curreny if self.currency is not None else self.instrument[0:3],
			'direction':self.direction,
			'strategy_ref':self.strategy_ref,
			'entry':self.entry,
			'entry_cut':self.entry_cut,
			'entry_expire':self.entry_expire,
			'take_profit_distance':self.take_profit_distance,
			'stop_loss_distance':self.stop_loss_distance,
			'length':self.length,
			'signal_notes':self.signal_notes
		}




TradeEntrySignal = TradeSignal 

# -- interest rate calculation for overnight trades ? 
class TradeExitSignal:
	
	"""
	Class for holding exit signals for any setups. If one has occurred, any open trades that match 
	this exit signal strategy_ref, instrument and direction should be closed 
	
	It is up to the backtester whether to close at the top or bottom or typical price of the candle. 
	"""
	exit_signal_id  = None #a unique id for referring to this specific exit signal 
	the_date = None 
	strategy_ref = None # required for hooking up entry signals to exit signals. Ignored if None
	instrument = None 
	direction = TradeDirection.VOID 
	
	signal_notes = ''  #anything that could be used later for reporting (eg filter results) 
	
	
	sql_row = "(%(exit_signal_id)s,%(strategy_ref)s,%(the_date)s,%(instrument)s,%(direction)s)"
	
	def __init__(self):
		self.exit_signal_id = str(uuid.uuid4())

	def to_dict_row(self):
		direction_str = 'BUY' if self.direction == TradeDirection.BUY else 'SELL' if self.direction == TradeDirection.SELL else 'VOID'
		return {
			'exit_signal_id':self.exit_signal_id,
			'the_date':self.the_date,
			'instrument':self.instrument,
			'direction':direction_str,
			'strategy_ref':self.strategy_ref
		}
	
	@staticmethod
	def create(the_date,instrument,strategy_ref,direction,notes=''):
		exit_signal = TradeExitSignal()
		exit_signal.the_date = the_date
		exit_signal.instrument = instrument
		exit_signal.strategy_ref = strategy_ref
		exit_signal.direction = direction
		exit_signal.signal_notes = notes
		return exit_signal
	
	@staticmethod
	def mock(): #needed so the backtest query does not break when there are no exit signals 
		exit_signal = TradeExitSignal()
		exit_signal.the_date = datetime.datetime(1990,1,1,0,0)
		exit_signal.instrument = None 
		exit_signal.strategy_ref = None 
		exit_signal.direction = TradeDirection.VOID 
		exit_signal.signal_notes = 'fake exit signal to get the backtester query to work'
		return exit_signal
	

#model classes for holding all info when generating a set of signals 
class TradeSignallingPartial:
	signals = [] 
	entries = [] 
	entry_cuts = []
	take_profit_distances = [] 
	stop_loss_distances = []
	
class TradeSignallingData:  #need to force this to break if attemping to set something that doesnt exist
	instruments = None
	timeline = None 
	name = None
	chart_resolution = 15 #default 
	candlesticks = []
	np_candles = None #np array of the candlesticks created when calculate_multiple is called. Useful for speeding stuff up later 
	_instrument_map = {} 
	bullish = TradeSignallingPartial()
	bearish = TradeSignallingPartial() 
	
	#perfect this so it can be used everywhere 
	def closest_time_index(self,the_date):
		end_date = the_date 
		start_date = the_date - datetime.timedelta(minutes=1440*3) #just get all indexs less than or equal to the_date - 3 days
		mask = (self.timeline >= start_date) & (self.timeline <= end_date)
		inds = np.where(mask)[0]
		if len(inds):
			return inds[-1] #then get latest most recent index 
		raise ValueError('Unable to find closest time index')
		return None #not found 
	
	def instrument_index(self,instrument):
		if not self._instrument_map:
			self.set_instruments(self.instruments) 
		
		return self._instrument_map[instrument]
	
	#override setters here? 
	def set_instruments(self,instruments):
		self._instrument_map = {}
		for e,i in enumerate(instruments):	
			self._instrument_map[i] = e
		self.instruments = instruments 
















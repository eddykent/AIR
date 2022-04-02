## setups are trades that have been produced from signals from various sources. A TradeSetup class finds trades on a given date 
#that have a high probabily of winning based on their backtest results.  TradeSetup classes need to be backtestable 

from enum import Enum
from collections import namedtuple
import uuid
from datetime import datetime,timedelta
from typing import Optional, List
import numpy as np

from utils import ListFileReader, Database
from utils import overrides 
import charting.chart_viewer as chv 

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
	take_profit_distance = 0  #the value to exit the trade at when it wins 
	stop_loss_distance = 0 #the value to exit the trade at when it loses 
	length = 1440 #1440 minutes in 24 hours
	
	sql_row = "(%(signal_id)s,%(the_date)s,%(instrument)s,%(direction)s,%(entry)s,%(take_profit_distance)s,%(stop_loss_distance)s,%(length)s)"
	
	def __init__(self):
		self.signal_id = str(uuid.uuid4())
		
	@staticmethod
	def from_simple(instrument,direction):
		this_signal = TradeSignal()
		this_signal.instrument = instrument
		this_signal.direction = direction
		return this_signal
		
	
	@staticmethod
	def from_full(the_date,instrument,strategy_ref,direction,entry,take_profit_distance,stop_loss_distance,length=1440):
		this_signal = TradeSignal()
		this_signal.the_date = the_date 
		this_signal.instrument = instrument
		this_signal.strategy_ref = strategy_ref
		this_signal.direction = direction
		this_signal.entry = entry 
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
			'take_profit_distance':self.take_profit_distance,
			'stop_loss_distance':self.stop_loss_distance,
			'length':self.length
		}


class TradeSetup:	#this not just an indicator - does not have calculate() etc. It is its own thing that finds trade signals 	
	
	timeframe = 15 #15 min chart by default
	instruments = [] #what trading instruments are we interested in?
	
	def __init__(self,instruments,timeframe=15):
		self.timeframe = timeframe
		self.instruments = instruments
	
	
	#by default, get the setups and turn to -1s and 1s?
	def detect(self,start_date : datetime, end_date : datetime) -> np.array:# - for AI - 0s and 1s or similar delivered from  get_setups()
		"""
		Generate a list of numbers (per instrument) between -1 and 1 where -1 is very bearish and 1 is very bullish with high confidence 
		A value close to 0 has low confidence and might be best not to be used. 
		
		Note: 
		This function can be used to generate filters but it is computationally expensive - it has to create setups first then turn them
		back into a numpy array. Therefore, it might be best to implement the filter directly using the indicators. An alternative is to 
		override this function within the base to create a faster version
		
		Parameters
		---------
		start_date : datetime 
			The date in which to start looking for setups 
		end_date : datetime 
			The date in which to end looking for setups 
		
		Returns
		-------
		numpy.array 
			A large array (one per instrument) indicating where the buy (positive numbers) and sell (negative numbers) setups were
		"""
		#even though a tradesetup generates trades on the timeframe, they can still be used as filters! just use this detect() method 
		raise NotImplementedError('This method must be overridden') #use get_setups() ! 
	
	#def get_setups_and_confidence(self,start_date,end_date): # perhaps worth thinking about later
	
	def get_setups(self,start_date : datetime, end_date : datetime) -> List[TradeSignal]:
		"""
		Generate a set of trade signals from this setup generator
		
		Parameters
		---------
		start_date : datetime 
			The date in which to start looking for setups 
		end_date : datetime 
			The date in which to end looking for setups 
		
		Returns:
		-------
		list(TradeSignal) 
			A bunch of trade signals that were found in the date range 
			
		Raises
		------
		NotImplementedError
			This function must be definded in subsequent setup objects 
		"""
		raise NotImplementedError('This method must be overridden')
		
	def get_latest(self,age_limit : int = 240) -> List[TradeSignal]: #- for signals right now (short cut to not call for a backtest) 
		"""
		Generate a set of trade signals from this setup generator, returning only the latest trades per instrument
		
		Returns:
		-------
		list(TradeSignal) 
			A bunch of trade signals that were found from now up to age_limit minutes ago. 
		"""
		end_date = datetime.now() 
		start_date = datetime.now() - timedelta(minutes=age_limit)
		return self.get_setups(start_date,end_date)
	
	def draw_snapshot(self,start_date : datetime, end_date :datetime, trade_signal : TradeSignal = None) -> chv.ChartView #-add all chart views together. Consider what to do with start_date and end_date  
		"""
		Generate a ChartView object that can be plotted and looked at for inspecting the signal generated from this setup.
		All of  the indicators etc used should be plotted on this chart in this method. Start and end dates are needed to 
		gauge the chart size for the trade setup. If the trade signal is not provided, the chart should still be drawn with
		the underlying indicators and methods used.
		
		Parameters
		-----------
		start_date : datetime
			the start date to draw the chart from 
		end_date : datetime
			the end date to draw the chart from
		trade_signal : TradeSignal (optional)  
			the trade signal to draw on the chart (complete with the trading box!)
		
		Returns 	
		-------
		chv.ChartView  
			A chart view object of the drawing of this indicator 		"""
		raise NotImplementedError('This method must be overridden')  #--incorrect? this needs to return a chart view with the trading rectangle 
	





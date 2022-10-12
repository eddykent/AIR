import pdb #? 
import datetime
from collections import namedtuple
from typing import Optional,List

from psycopg2.extensions import AsIs as Inject

from enum import Enum

from utils import CurrencyPair, ListFileReader, overrides
from setups.signal import TradeDirection, TradeSignal, TradeExitSignal

##classes that take a set of trade signals and then test if they won/lost. Also report statistics (win streaks, percent loss, drawdowns??) 

#stagnated = started but didnt stop, unfit = didnt start as out of bounds? eg already hit tp/sl straight away. or the tp/sl targets dont make sense 
BackTestStatistic = namedtuple('BackTestStatistic','total stagnated unfinished invalid  wins losses ups downs winstreak losestreak') #growth, drawdown  drawdown')#allows for multiple tests at once

class TradeResultStatus(Enum):
	#CUT = -5 #the signal is cut if there was an expire_cut price that was hit before the entry price. 
	INVALID = -5  #the trade parameters were wrong in some way (eg tp > sl in a sell order) 
	STAGNATED = -4 #the trade never hit its entry price 
	LOST_SL = -3 #the trade stopped out at the stop loss price 
	LOST_EXIT = -2 #the trade hit an exit criteria and lost
	LOSING = -1 #the trade didnt stop out, but is down 
	VOID = 0 # the trade has not gone ahead (eg hit a cancel price)
	WINNING = 1 #the trade didnt stop out, but is up
	WON_PL = 2 #we moved the stop loss to lock in profit and this value got hit. 
	WON_EXIT = 3 #the trade hit an exit criteria and won
	WON_TP = 4 # the trade stopped out at the take profit price 
	WON_EXTRA = 5 #the trade hit the profit lock activation and continued to the extra profit target 

TradeProfitPath = namedtuple('TradeProfitPath','typical optimistic pessimistic')
TradeResult = namedtuple('TradeResult','signal_id entry_date entry_price entry_candle exit_date exit_price exit_candle result_movement result_percent result_status profit_path')

#class for handling the stats? eg for querying 
# allow for sorting/grouping etc of trade results into separate parts 
class BackTestStatistics: 

	signals = [] 
	results = [] 
	
	def __init__(self,signals,results):
		self.signals = signals
		self.results = results 
	
	def get_statistics_on(self,stategy_refs=[],instruments=[]):  #anything else?
		subset_signals = [s for s in self.signals if (s.instrument in instruments or not instruments) and (s.strategy_ref in strategy_refs or not strategy_refs)]
		subset_signals = sorted(subset_signals,key=lambda s:s.the_date)
		#lose means finish down or lost
		win_streaks = []
		lose_streaks = [] 
		accum_wins = [] 
		accum_loses = [] 
		wins = 0
		loses = 0
		accumwin = 0
		accumloss = 0
		for s in subset_signals:
			wins = (wins+1) if s.result_status in [TradeResultStatus.WON,TradeResultStatus.WINNIG] else 0
			loses = (loses+1) if s.result_status in [TradeResultStatus.LOST,TradeResultStatus.LOSING] else 0
			win_streaks.append(wins)
			lose_streaks.append(loses)
		return {
			'total':len(self.signals),
			'stagnated':len([s for s in self.signals if s.result_status == TradeResultStatus.STAGNATED]),
			'unfinished':len([s for s in self.signals if s.result_status not in [TradeResultStatus.WON,TradeResultStatus.LOST]]),
			'void':len([s for s in self.signals if s.result_status == TradeResultStatus.VOID]),
			'invalid':len([s for s in self.signals if s.result_status == TradeResultStatus.INVALID]),
			'wins':len([s for s in self.signals if s.result_status == TradeResultStatus.WON]),
			'loses':len([s for s in self.signals if s.result_status == TradeResultStatus.LOST]),
			'ups':len([s for s in self.signals if s.result_status == TradeResultStatus.WINNING]),
			'downs':len([s for s in self.signals if s.result_status == TradeResultStatus.LOSING]),
			'win_streak':max(win_streaks),
			'lose_streak':max(lose_streaks)
			#'growth':max(...)
			#'drawdown':max(...)
		}


#TODO : A tool to take a dataset of candles and add a percentage error to all the candles to produce a fuzzy dataset based on real world data.
#The idea is to be able to strengthen backtest results and prevent overfitting. A strategy can be considered quite strong if it also passes 
#a fuzzed dataset 
 
#The strategy produces signals based on the fuzzed data and this data is stored in here so it can be used in the results step too
# - a database backtest might not be ideal here. also testing against fundamentals might shake it up too much
#
class FuzzFactor: 

	fuzz_pc = 5; #float between 0 and 100 prefreably 10% or less (experiments welcomed)
	

#main interface for what a backtester is and how it will work
class BackTester:
	
	'''
	Class for doing backtesting on trading signals to see if they won or not. 
	
	Attributes
	----------	
	mode : str
		Of the form "typical", "optimistic" and "pesimistic" to reflect on the modelling strategy when finding 
		results of a backtest. For example, a pesimistic mode will report prices furthest from the take profit
	'''
	mode = 'typical' #TODO - optimistic,pesimistic (use best/worst scenario)
	fuzz = None  #TODO: add fuzz to the dataset. If not none, the data from the fuzz should be used instead 
	
	#def test_trade(trade_signal : TradeSignal) -> TradeResult:
	#	pass
	
	def perform(trade_signals : List[TradeSignal]) -> List[TradeResult]: 
		'''
		Function to perform the backtesting. The method is defined in the subclass. 
		
		Parameters
		----------
		trade_signals : list(TradeSignal)
			The list of trade signals that need to be backtested 
		
		Returns
		-------
		list(TradeResult)
			The list of results (one per trade signal) of what happened with that trade 
		'''
		raise NotImplementedError("This method must be overridden")
		
#activation = price to reach in order to move the stops 
#adjustment = ratio of the take profit distance to place the stop loss at
#extra_ = ratio of the take profit distance of extra profit to strive for 
ProfitLockData = namedtuple('ProfitLockData','activation adjustment extra')

#perform a backtest by passing the trade signals directly into the database and using a sql query to get the results. 
#Due to using the database, there is no way to be able to expose this to a loss function in tensorflow 
class BackTesterDatabase(BackTester):
	
	sql_query_file = 'queries/new_backtester_execution.sql'
	cursor = None #the database cursor - handled from something else 
	
	trade_result = {
		'INVALID':TradeResultStatus.INVALID,
		'STAGNATED':TradeResultStatus.STAGNATED, 
		'LOST':TradeResultStatus.LOST_SL,
		'EXIT_DOWN':TradeResultStatus.LOST_EXIT,
		'LOSING':TradeResultStatus.LOSING, 
		'VOID':TradeResultStatus.VOID,
		'WINNING':TradeResultStatus.WINNING,
		'PROFIT_LOCK':TradeResultStatus.WON_PL,
		'EXIT_UP':TradeResultStatus.WON_EXIT,
		'WON':TradeResultStatus.WON_TP,
		'WON_EXTRA':TradeResultStatus.WON_EXTRA
	}
	
	
	def __init__(self,cursor):
		self.cursor = cursor
	
	
	@overrides(BackTester)
	def perform(self,trade_signals,exit_signals=[],profit_lock=None):		
		
		if type(profit_lock ) != ProfitLockData:
			profit_lock = ProfitLockData._make(profit_lock)
		
		exit_signals += [TradeExitSignal.mock()]
		
		
		entry_sql_rows = [self.cursor.mogrify(TradeSignal.sql_row,ts.to_dict_row()).decode() for ts in trade_signals]
		exit_sql_rows = [self.cursor.mogrify(TradeExitSignal.sql_row,te.to_dict_row()).decode() for te in exit_signals]
		
		sql_query = None
		with open(self.sql_query_file,'r') as f:
			sql_query = f.read()
		
		query_params = {
			'trade_signals':Inject(','.join(entry_sql_rows)),
			'exit_signals':Inject(','.join(exit_sql_rows)),
			'profit_lock_activation':None if profit_lock is None else profit_lock.activation,
			'profit_lock_adjustment':None if profit_lock is None else profit_lock.adjustment,
			'profit_lock_extra':None if profit_lock is None else profit_lock.extra
		}
		
		
		self.cursor.execute(sql_query,query_params)
		query_result = self.cursor.fetchall()
		
		
		trade_results = []
		for result in query_result:
			result_row, path = result #unpack 			
			result_status = self.trade_result.get(result_row['result_status'].upper(),TradeResultStatus.INVALID)
			result_row['result_status'] = result_status
			if path:
				trade_result_paths = TradeProfitPath(**path)
				result_row['profit_path'] = trade_result_paths
			else:
				result_row['profit_path'] = None
			trade_result = TradeResult(**result_row)
			trade_results.append(trade_result)
		return trade_results
	


#pass streams candles (labelled with their instrument name) to this class and then perfrom backtesting using this data
#this class might be exposable to an AI loss function. 
#class BackTesterCandles:




















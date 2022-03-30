import pdb #? 
import datetime
from collections import namedtuple
from typing import Optional,List

from psycopg2.extensions import AsIs as Inject

from enum import Enum

from utils import CurrencyPair, ListFileReader, overrides
from setups import TradeDirection, TradeSignal

##classes that take a set of trade signals and then test if they won/lost. Also report statistics (win streaks, percent loss, drawdowns??) 

#stagnated = started but didnt stop, unfit = didnt start as out of bounds? eg already hit tp/sl straight away. or the tp/sl targets dont make sense 
BackTestStatistic = namedtuple('BackTestStatistic','total stagnated unfinished invalid  wins losses ups downs winstreak losestreak') #growth, drawdown  drawdown')#allows for multiple tests at once

class TradeResultStatus(Enum):
	INVALID = -4  #the trade parameters were wrong in some way (eg tp > sl in a sell order) 
	STAGNATED = -3 #the trade never hit its entry price 
	LOST = -2 #the trade stopped out at the stop loss price 
	LOSING = -1 #the trade didnt stop out, but is down 
	VOID = 0 #
	WINNING = 1 #the trade didnt stop out, but is up
	WON = 2 # the trade stopped out at the take profit price 

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
	mode = 'typical' #optimistic,pesimistic (use best/worst scenario)
	
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
		

#perform a backtest by passing the trade signals directly into the database and using a sql query to get the results. 
#Due to using the database, there is no way to be able to expose this to a loss function in tensorflow 
class BackTesterDatabase(BackTester):
	
	sql_query_file = 'queries/backtesting_trade_executions.sql'
	cursor = None #the database cursor - handled from something else 
	
	trade_result = {
		'INVALID':TradeResultStatus.INVALID,
		'STAGNATED':TradeResultStatus.STAGNATED, 
		'LOST':TradeResultStatus.LOST,
		'LOSING':TradeResultStatus.LOSING, 
		'VOID':TradeResultStatus.VOID,
		'WINNING':TradeResultStatus.WINNING,
		'WON':TradeResultStatus.WON
	}
	
	
	def __init__(self,cursor):
		self.cursor = cursor
	
	
	@overrides(BackTester)
	def perform(self,trade_signals):
		sql_row = TradeSignal.sql_row
		sql_rows = [self.cursor.mogrify(sql_row,ts.to_dict_row()).decode() for ts in trade_signals]
		sql_query = None
		with open(self.sql_query_file,'r') as f:
			sql_query = f.read()
		self.cursor.execute(sql_query,{'trade_signals':Inject(','.join(sql_rows))})
		query_result = self.cursor.fetchall()
		trade_results = []
		for result in query_result:
			result_row, path = result #unpack 
			trade_result_paths = TradeProfitPath(**path)
			result_status = self.trade_result.get(result_row['result_status'].upper(),TradeResultStatus.VOID)
			result_row['result_status'] = result_status
			result_row['profit_path'] = trade_result_paths
			trade_result = TradeResult(**result_row)
			trade_results.append(trade_result)
		return trade_results
	

		
#pass streams candles (labelled with their instrument name) to this class and then perfrom backtesting using this data
#this class might be exposable to an AI loss function. 
#class BackTesterCandles:




















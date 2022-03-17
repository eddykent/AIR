import pdb #? 
import datetime
from collections import namedtuple
from typing import Optional,List

from psycopg2.extensions import AsIs as Inject

from enum import Enum

from utils import CurrencyPair, ListFileReader
from setups import TradeDirection, TradeSignal


##classes that take a set of trade signals and then test if they won/lost. Also report statistics (win streaks, percent loss, drawdowns??) 

#stagnated = started but didnt stop, unfit = didnt start as out of bounds? eg already hit tp/sl straight away. or the tp/sl targets dont make sense 
#BackTesterStatistic = namedtuple('BackTesterStatistic','total executed stagnated unfit wins losses ups downs winstreak losestreak drawdown')#allows for multiple tests at once

class TradeResultStatus(Enum):
	INVALID = -4  #the trade parameters were wrong in some way (eg tp > sl in a sell order) 
	STAGNATED = -3 #the trade never hit its entry price 
	LOST = -2 #the trade stopped out at the stop loss price 
	LOSING = -1 #the trade didnt stop out, but is down 
	BALANCED = 0 #when we exit at PRECISELY the same cost  as the spread? 
	WINNING = 1 #the trade didnt stop out, but is up
	WON = 2 # the trade stopped out at the take profit price 

TradeResult = namedtuple('TradeResult','entry_date entry_price exit_date exit_price result_percent result_status')

#class for handling the stats? eg for querying 
#class BackTestResults: # allow for sorting/grouping etc of trade results into separate parts 

#main interface for what a backtester is and how it will work
class BackTester:

	mode = 'typical' #optimistic,pesimistic (use best/worst scenario)
	
	#def test_trade(trade_signal : TradeSignal) -> TradeResult:
	#	pass
	
	def perform(trade_signals : List[TradeSignal]) -> List[TradeResult]: 
		pass



#perform a backtest by passing the trade signals directly into the database and using a sql query to get the results. 
#Due to using the database, there is no way to be able to expose this to a loss function in tensorflow 
class BackTesterDatabase
	
	sql_query_file = 'queries/backtesting_trade_executions.sql'
	cursor = None #the database cursor - handled from something else 
	
	def __init__(self,cursor):
		self.cursor = cursor
	
	@overrides(BackTester)
	def perform(self,trade_signals):
		sql_row = TradeSignal.sql_row
		sql_rows = [self.cursor.mogrify(sql_row,ts.to_dict_row()) for ts in trade_signals]
		sql_query = None
		with open(self.sql_query_file,'r') as f:
			sql_query = f.read()
		self.cursor.execute(sql_query,{'trade_signals':Inject(','.join(sql_rows))})
		query_result = self.cursor.fetchall()
		#construct TradeResult tuples from query_result
	

#pass streams candles (labelled with their instrument name) to this class and then perfrom backtesting using this data
#this class might be exposable to an AI loss function. 
#class BackTesterCandles:




















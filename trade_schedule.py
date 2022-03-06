
##perhaps this should  be renamed to trade_backtester.py 


import psycopg2
import pdb #? 
import datetime
from collections import namedtuple

from psycopg2.extensions import AsIs, register_adapter, adapt

from enum import Enum


from utils import CurrencyPair, ListFileReader
from trade_setup import TradeDirection, TradeSignal



#class for holding trade signals that can be filtered by filters. TradeSignal types are generated using setups in trade_setup 
class TradeSchedule:
	
	the_date = datetime.datetime.now()
	take_profit_factor = 10
	stop_loss_factor =  7
	normalisation_window = 100
	trade_length = 24*60 #minutes
	atr_lookback = 100
	start_candle = 2 #the candle we start the trade at (not 0 since we need time to calculate) 
	cursor = None #we should pass the DB cursor in instead of have our own connection 
	trades = []
	all_pairs = []
	__sql_file = 'queries/test_trades.sql'   #TODO - change to handle any tradesignal! 
	
	
	def __init__(self,the_date):
		self.the_date = the_date
		lfr = ListFileReader()
		self.all_pairs = lfr.read('fx_pairs/fx_mains.txt')
	
	#consider class methods
	#https://stackoverflow.com/questions/141545/how-to-overload-init-method-based-on-argument-type
		
	def build_from(self,some_result,the_type):
		#create list of trades according to the results 
		#this function has became a bit of a dumping ground for new methods to produce trade schedules 
		#consider refactoring to make this method more readable and less stuff 
		#pdb.set_trace()
		if the_type.lower() == 'currency_strengths':
			#some_result is a rank list and a currency list - convert to using CurrencyStrengthFilter
			predicted_ranks = some_result['predicted_ranks']
			sorted_ranks = sorted(predicted_ranks)
			ranks = [sorted_ranks.index(x) for x in predicted_ranks]
			currencies = some_result['currencies']
			zipped = sorted(zip(ranks,currencies),key=lambda x: x[0])
			ordered_currencies = [z[1] for z in zipped]
			top = 2
			worst = ordered_currencies[:top]
			best = ordered_currencies[-top:][::-1]
			to_trade = [CurrencyPair(b+'/'+w) for b in best for w in worst]
			self.trades = [TradeSignal.from_simple(curpair.as_string(self.all_pairs),TradeDirection.SELL if curpair.is_reversed(self.all_pairs) else TradeDirection.BUY) for curpair in to_trade]
		if the_type.lower() == 'buy_sell_fx_pairs':
			self.trades = []
			these_fx_pairs = some_result['fx_pairs']
			buy_sell = some_result['predicted']
			buy = 0
			sell = 1
			assert len(these_fx_pairs) ==len(buy_sell) , "The currency list and the buy/sell result must be the same length"
			for candidate in zip(these_fx_pairs,buy_sell):
				cpair  = CurrencyPair(candidate[0])
				todo = candidate[1] #[buy?,sell?]
				if all(todo):
					continue #dont do anything if the model says buy AND sell! 
				if todo[buy]:
					self.trades.append(TradeSignal.from_simple(str(cpair),TradeDirection.BUY))
				if todo[sell]:
					self.trades.append(TradeSignal.from_simple(str(cpair),TradeDirection.SELL))
		if the_type.lower() == 'buy_fx_pairs':
			self.trades = []
			these_fx_pairs = some_result['fx_pairs']
			buy_sell = some_result['predicted']
			assert len(these_fx_pairs) ==len(buy_sell) , "The currency list and the buy result must be the same length"
			for candidate in zip(these_fx_pairs,buy_sell):
				cpair  = CurrencyPair(candidate[0])
				todo = candidate[1] #[buy?,sell?]
				if todo[0]:
					self.trades.append(TradeSignal.from_simple(str(cpair),TradeDirection.BUY))
		if the_type.lower() == 'sell_fx_pairs':
			self.trades = []
			these_fx_pairs = some_result['fx_pairs']
			buy_sell = some_result['predicted']
			assert len(these_fx_pairs) ==len(buy_sell) , "The currency list and the sell result must be the same length"
			for candidate in zip(these_fx_pairs,buy_sell):
				cpair  = CurrencyPair(candidate[0])
				todo = candidate[1] #[buy?,sell?]
				if todo[0]:
					self.trades.append(TradeSignal.from_simple(str(cpair),TradeDirection.SELL))
		if the_type.lower() == 'delta_tuples':
			#delta tuples are of the form [(pair,delta)] where the pair is the fx pair and the delta
			#is the indicator to say whether it is a sure buy or sell. It's a float where positive 
			#is a buy and negative is a sell. A large number is a strong buy.
			self.trades = []
			#filter to ensure we have them
			delta_pairs = [dt for dt in some_result if dt[0] in self.all_pairs]
			#we build the trade from the sign of the delta, and then sort by the magnitude of the delta
			trades = [(TradeSignal.from_simple(dt[0],TradeDirection.BUY if dt[1] > 0 else TradeDirection.SELL),abs(dt[1])) for dt in delta_pairs if abs(dt[1]) > 0]
			self.trades = [t[0] for t in sorted(trades,key=lambda t:t[1],reverse=True)]
	
	
	def run_test(self,curs=None):
		cursor = curs if curs is not None else self.cursor
		if not cursor:
			raise "Missing Database Cursor!"
		the_query = ''
		with open(self.__sql_file,'r') as f:
			the_query = f.read()
		params = {
			'trade_schedule':self,
			'look_back_days':self.atr_lookback,
			'the_date':self.the_date.date(),
			'hour':self.the_date.hour,
			'take_profit_factor':self.take_profit_factor,
			'normalisation_window':self.normalisation_window,
			'stop_loss_factor':self.stop_loss_factor,
			'trade_length':self.trade_length, 
			'start_candle':self.start_candle
		}
		results = []
		if self.trades:
			cursor.execute(the_query,params)
			results = cursor.fetchall()
		return results
		
		
	
def trade_schedule_to_sql_type(tradeschedule):
	trade_sql = [] 
	for t in tradeschedule.trades:
		params = {
			'instrument':adapt(t.instrument).getquoted().decode(),
			'direction':adapt('BUY' if t.direction == TradeDirection.BUY else 'SELL').getquoted().decode(),
			'entry_price':adapt(t.entry).getquoted().decode()
		}
		trade_sql.append('(%(instrument)s,%(direction)s,%(entry_price)s)' % params)
	return AsIs('(VALUES '+','.join(trade_sql)+')')

register_adapter(TradeSchedule,trade_schedule_to_sql_type)


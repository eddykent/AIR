
import psycopg2
import pdb #? 
import datetime
from collections import namedtuple
from utils import CurrencyPair, ListFileReader

from psycopg2.extensions import AsIs, register_adapter, adapt


##A tuple representing a trade that has been taken
#instrument - the instrument that is being traded
#direction - a buy or sell
#entry - the entry price to start the trade at (regularly NULL for this type)
Trade = namedtuple('Trade','instrument direction entry')


##A tuple representing a trade that has been taken that has some bounds on it (stop_loss & take_profit)
#instrument - the instrument that is being traded
#direction - a buy or sell
#entry - the entry price to start the trade at
#take_profit - the value to exit the trade at when it wins
#stop_lossb - the value to exit the trade at when it loses
#length - the time a trade should go on for (in minutes, eg a day is 1440) 
BoundedTrade = namedtuple('BoundedTrade','instrument direction entry take_profit stop_loss length')

#abstract class for laying out a trade filter - attempt to stop "stupid" trades! 
class TradeFilter:
	
	all_pairs = []
	
	def __init__(self,all_pairs):
		if all_pairs:
			self.all_pairs = all_pairs
		else:
			lfr = ListFileReader()
			self.all_pairs = lfr.read('fx_pairs/fx_mains.txt')
		
	def filter(self,trades):
		return [t for t in trades if self.check_pair(t.instrument,t.direction)]
	
	def check_pair(self,pair,direction='BUY'):
		return True  #check to see if doing a buy/sell on this pair is a good idea or not 


##class for determining if a trade is trending in the right direction using EMA200
class MAFilter(TradeFilter):
	
	snapshot = {}
	ma_key = 'ema200' #default to ema200
	
	def __init__(self,snap,all_pairs=None):
		super().__init__(all_pairs)
		self.snapshot = snap
	
	#override
	def check_pair(self,pair,direction):
		if direction == 'BUY':
			return self.snapshot[pair]['low_price'] > self.snapshot[pair][self.ma_key]	
		if direction == 'SELL':
			return self.snapshot[pair]['high_price'] < self.snapshot[pair][self.ma_key]
		return True

class BollingerBandsFilter(TradeFilter):
	
	snapshot = {}
	lower_key = 'bollinger_band_lower'
	upper_key = 'bollinger_band_upper'

	def __init__(self,snap,all_pairs=None):
		super().__init__(all_pairs)
		self.snapshot = snap
	
	def check_pair(self,pair,direction):
		if direction == 'BUY':
			return self.snapshot[pair]['close_price'] < self.snapshot[pair][self.upper_key]	
			#	and self.snapshot[pair]['bollinger_band_percent_b'] < 1.0
		if direction == 'SELL':
			return self.snapshot[pair]['close_price'] > self.snapshot[pair][self.lower_key] 
			#	and self.snapshot[pair]['bollinger_band_percent_b'] > 0
		return False


#reject anything that does the oposite to a macd buy/sell signal
class MACDFilter(TradeFilter):
	
	#can be swapped for any crossover but we will stick with the class name 
	fast_key = 'macd_line'
	slow_key = 'macd_signal'
	__snapshots = []
	__crossovers = {} #holds flags 'UP' 'DOWN' and None ?
	
	def __init__(self,snaps,all_pairs=None):
		super().__init__(all_pairs)
		self.__snapshots = snaps
		
	def find_crossovers(self):
		self.__crossovers = {}
		back = self.__snapshots[0] 
		front = self.__snapshots[-1]
		for pair in self.all_pairs:
			if pair in front and pair in back:
				back_fast = back[pair][self.fast_key]
				back_slow = back[pair][self.slow_key]
				front_fast =front[pair][self.fast_key]
				front_slow = front[pair][self.slow_key]
				if back_fast > back_slow and front_fast < front_slow:
					##fast line crossed slow line downwards
					self.__crossovers[pair] = 'DOWN'
				if back_fast < back_slow and front_fast > front_slow: 
					##faat line crossed slow line upwards
					self.__crossovers[pair] = 'UP'
	
	def check_pair(self,pair,direction):
		if not self.__crossovers:
			self.find_crossovers() #build the crossover cache 
		cross = self.__crossovers.get(pair)
		if cross == 'UP' and direction == 'SELL':
			return False 
		if cross == 'DOWN' and direction == 'BUY':
			return False
		return False

#store the correlation suggestions and reject anything that goes the oposite way to the suggestion
#only use suggestions that have a suitably high number of N and low variance ---how? :) 
class CorrelationFilter(TradeFilter):
	
	variance_limit = 0.5 #if variance is as high as this * movement then reject? 
	movement_percentage_limit = 0.05 #must move by 0.1%? 
	n_limit = 5 #at least 5 suggestors needed to predict the movement 
	
	__correlations = {}
	
	def __init__(self,correlations,all_pairs=None):
		super().__init__(all_pairs)
		self.__correlations = correlations
		
	def check_pair(self,pair,direction):
		corr = self.__correlations.get(pair)
		if corr['delta_n'] >= self.n_limit:
			if corr['delta_variance'] < abs(corr['delta']) * self.variance_limit:
				if abs(corr['delta']) > self.movement_percentage_limit:
					if corr['delta'] < 0 and direction == 'BUY':
						return False
					if corr['delta'] > 0 and direction == 'SELL':
						return False
		return True



#class for determining if a trade is overbought/oversold
class RSIFilter(TradeFilter):
	
	boundary = 0.15
	snapshot = {}
	rsi_key = 'relative_strength_index'
	
	def __init__(self,snap,all_pairs=None):
		super().__init__(all_pairs)
		self.snapshot = snap
	
	def check_pair(self,pair,direction):
		if direction == 'BUY':
			return self.snapshot[pair][self.rsi_key] < 1.0 - self.boundary
		if direction == 'SELL':
			return self.snapshot[pair][self.rsi_key] > self.boundary
		return False
	


#helper class for determining if a currency pair should be traded based on 
#what the currency strength says 
class CurrencyStrengthFilter(TradeFilter):  ##consider making an interface for this such as CurrencyFilter that asserts function check_pair exists
	
	currency_strength = []#snapshot of the currency strength at this moment in time
	all_pairs = [] #list of all available pairs to trade
	tolerance = 2 #rank difference allowed if it is in the wrong direction 
	
	def __init__(self,currency_strength,all_pairs=None):
		super().__init__(all_pairs)
		self.currency_strengths = currency_strength
		
	
	def produce_all_trades(self):
		#return a list of all the trades that this suggests
		strengths = self.__get_strengths()
		trades = []
		for pair in self.all_pairs:
			currpair = CurrencyPair(pair)
			from_strength = strengths[currpair.from_currency]
			to_strength = strengths[currpair.to_currency]
			trades.append(Trade(pair,'BUY' if from_strength > to_strength else 'SELL',None))
		return trades
			
	def produce_top_trades(self,top=10):
		strengths = self.__get_strengths()
		currency_list = [(curr,strengths[curr]) for curr in strengths]
		ordered_currencies = [c[0] for c in sorted(currency_list,key=lambda cl:cl[1])]
		top_take = int(top ** 0.5) #approx 
		worst = ordered_currencies[:top_take]
		best = ordered_currencies[-top_take:][::-1]
		to_trade = [CurrencyPair(b+'/'+w) for b in best for w in worst]
		return [Trade(curpair.as_string(self.all_pairs),'SELL' if curpair.is_reversed(self.all_pairs) else 'BUY',None) for curpair in to_trade] 
		
	#override
	def check_pair(self,pair,direction='BUY'):
		strengths = self.__get_strengths()
		currpair = CurrencyPair(pair)
		if direction == 'BUY':
			return strengths[currpair.from_currency] - strengths[currpair.to_currency] + self.tolerance > 0
		if direction == 'SELL':
			return strengths[currpair.to_currency] - strengths[currpair.from_currency] + self.tolerance > 0
		return False 
	
	def __get_strengths(self,key='rank'):
		#key: rank. Also available: movement, average_movement etc 
		return { curr:val[key] for  curr, val in self.currency_strengths.items()}

#filters that can be created from fundamental analysis 
class SentimentFilter(TradeFilter):
	
	pair_sentiment = {} #for each pair there should be a key "sentiment" which contains BULLISH or BEARISH
	currency_sentiment = {}#for each currency, there should be a key eg self.sentiment_currencies['EUR']['sentiment'] == 'BULLISH'
	
	def __init__(self, pair_sentiment={}, currency_sentiment={}, all_pairs=None):
		super().__init__(all_pairs)
		self.pair_sentiment = pair_sentiment
		self.currency_sentiment = currency_sentiment
	
	def check_pair(self,pair,direction='BUY'):
		pair_sentiment = self.pair_sentiment.get(pair,'').upper() #no actual information regarding bullish or bearish if neutral
		currpair = CurrencyPair(pair)
		if direction == 'BUY':
			if pair_sentiment == 'BEARISH':
				return False
			buying = self.currency_sentiment.get(currpair.from_currency,'').upper()
			selling = self.currency_sentiment.get(currpair.to_currency,'').upper()
		if direction == 'SELL':
			if pair_sentiment == 'BULLISH':
				return False
			buying = self.currency_sentiment.get(currpair.to_currency,'').upper()
			selling = self.currency_sentiment.get(currpair.from_currency,'').upper()
		return not (buying == 'BEARISH' or selling == 'BULLISH')


#class for holding trades that can be filtered by the above filters. Trades are generated using setups 
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
	__sql_file = 'queries/test_trades.sql'
	
	
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
			self.trades = [Trade(curpair.as_string(self.all_pairs),'SELL' if curpair.is_reversed(self.all_pairs) else 'BUY',None) for curpair in to_trade]
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
					self.trades.append(Trade(str(cpair),'BUY',None))
				if todo[sell]:
					self.trades.append(Trade(str(cpair),'SELL',None))
		if the_type.lower() == 'buy_fx_pairs':
			self.trades = []
			these_fx_pairs = some_result['fx_pairs']
			buy_sell = some_result['predicted']
			assert len(these_fx_pairs) ==len(buy_sell) , "The currency list and the buy result must be the same length"
			for candidate in zip(these_fx_pairs,buy_sell):
				cpair  = CurrencyPair(candidate[0])
				todo = candidate[1] #[buy?,sell?]
				if todo[0]:
					self.trades.append(Trade(str(cpair),'BUY',None))
		if the_type.lower() == 'sell_fx_pairs':
			self.trades = []
			these_fx_pairs = some_result['fx_pairs']
			buy_sell = some_result['predicted']
			assert len(these_fx_pairs) ==len(buy_sell) , "The currency list and the sell result must be the same length"
			for candidate in zip(these_fx_pairs,buy_sell):
				cpair  = CurrencyPair(candidate[0])
				todo = candidate[1] #[buy?,sell?]
				if todo[0]:
					self.trades.append(Trade(str(cpair),'SELL',None))
		if the_type.lower() == 'delta_tuples':
			#delta tuples are of the form [(pair,delta)] where the pair is the fx pair and the delta
			#is the indicator to say whether it is a sure buy or sell. It's a float where positive 
			#is a buy and negative is a sell. A large number is a strong buy.
			self.trades = []
			#filter to ensure we have them
			delta_pairs = [dt for dt in some_result if dt[0] in self.all_pairs]
			#we build the trade from the sign of the delta, and then sort by the magnitude of the delta
			trades = [(Trade(dt[0],'BUY' if dt[1] > 0 else 'SELL',None),abs(dt[1])) for dt in delta_pairs if abs(dt[1]) > 0]
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
			'direction':adapt(t.direction).getquoted().decode(),
			'entry_price':adapt(t.entry).getquoted().decode()
		}
		trade_sql.append('(%(instrument)s,%(direction)s,%(entry_price)s)' % params)
	return AsIs('(VALUES '+','.join(trade_sql)+')')

register_adapter(TradeSchedule,trade_schedule_to_sql_type)


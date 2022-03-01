



import datetime

import pdb 

from utils import CurrencyPair, ListFileReader
from trade_schedule import TradeSignal, TradeDirection 


#abstract class for laying out a trade filter - attempt to stop "stupid" trades! - move to trade_filter.py? 
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
	
	def check_pair(self,pair,direction=TradeDirection.VOID):
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
		if direction == TradeDirection.BUY:
			return self.snapshot[pair]['low_price'] > self.snapshot[pair][self.ma_key]	
		if direction == TradeDirection.SELL:
			return self.snapshot[pair]['high_price'] < self.snapshot[pair][self.ma_key]
		if direction == TradeDirection.VOID:
			return False
		return True

class BollingerBandsFilter(TradeFilter):
	
	snapshot = {}
	lower_key = 'bollinger_band_lower'
	upper_key = 'bollinger_band_upper'

	def __init__(self,snap,all_pairs=None):
		super().__init__(all_pairs)
		self.snapshot = snap
	
	def check_pair(self,pair,direction):
		if direction == TradeDirection.BUY:
			return self.snapshot[pair]['close_price'] < self.snapshot[pair][self.upper_key]	
			#	and self.snapshot[pair]['bollinger_band_percent_b'] < 1.0
		if direction == TradeDirection.SELL:
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
		if cross == 'UP' and direction == TradeDirection.SELL:
			return False 
		if cross == 'DOWN' and direction == TradeDirection.BUY:
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
					if corr['delta'] < 0 and direction == TradeDirection.BUY:
						return False
					if corr['delta'] > 0 and direction == TradeDirection.SELL:
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
		if direction == TradeDirection.BUY:
			return self.snapshot[pair][self.rsi_key] < 1.0 - self.boundary
		if direction == TradeDirection.SELL:
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
			trades.append(TradeSignal.from_simple(pair,TradeDirection.BUY if from_strength > to_strength else TradeDirection.SELL))
		return trades
			
	def produce_top_trades(self,top=10):
		strengths = self.__get_strengths()
		currency_list = [(curr,strengths[curr]) for curr in strengths]
		ordered_currencies = [c[0] for c in sorted(currency_list,key=lambda cl:cl[1])]
		top_take = int(top ** 0.5) #approx 
		worst = ordered_currencies[:top_take]
		best = ordered_currencies[-top_take:][::-1]
		to_trade = [CurrencyPair(b+'/'+w) for b in best for w in worst]
		return [TradeSignal.from_simple(curpair.as_string(self.all_pairs),TradeDirection.SELL if curpair.is_reversed(self.all_pairs) else TradeDirection.BUY) for curpair in to_trade] 
		
	#override
	def check_pair(self,pair,direction):
		strengths = self.__get_strengths()
		currpair = CurrencyPair(pair)
		if direction == TradeDirection.BUY:
			return strengths[currpair.from_currency] - strengths[currpair.to_currency] + self.tolerance > 0
		if direction == TradeDirection.SELL:
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
		self.pair_sentiment = pair_sentiment  ##use something here to construct into dict of instrument->BEARISH/BULLISH etc 
		self.currency_sentiment = currency_sentiment
	
	def check_pair(self,pair,direction):
		pair_sentiment = self.pair_sentiment.get(pair,'').upper() #no actual information regarding bullish or bearish if neutral
		currpair = CurrencyPair(pair)
		if direction == TradeDirection.BUY:
			if pair_sentiment == 'BEARISH':
				return False
			buying = self.currency_sentiment.get(currpair.from_currency,'').upper()
			selling = self.currency_sentiment.get(currpair.to_currency,'').upper()
		if direction == TradeDirection.SELL:
			if pair_sentiment == 'BULLISH':
				return False
			buying = self.currency_sentiment.get(currpair.to_currency,'').upper()
			selling = self.currency_sentiment.get(currpair.from_currency,'').upper()
		return not (buying == 'BEARISH' or selling == 'BULLISH')















import datetime
from typing import Optional, List 

import pdb 

from utils import CurrencyPair, ListFileReader, overrides
from setups.trade_setup import TradeSignal, TradeDirection 

from indicators.volume import ClientSentiment
#extend to be across time? 

#each filter takes a result from one instance in time. Perhaps they can be extended to allow for filtering trade signals across different times? 

#use numpy?

#abstract class for laying out a trade filter - attempt to stop "stupid" trades! Works with a single instance in time 
class InstanceTradeFilter:
	
	snapshot = {} #the snapshot in time of some stuff to use in the filtering 
	
	def __init__(self,snap : dict):
		self.snapshot = snap
	
	def filter(self,trades : List[TradeSignal]):
		return [t for t in trades if self.check_instrument(t.instrument,t.direction)]
	
	def check_instrument(self,instrument : str,direction : TradeDirection=TradeDirection.VOID):
		raise NotImplementedError('This method must be overridden')
		return True  #check to see if doing a buy/sell on this pair is a good idea or not 


#from a wealth of information regarding each instrument across time, this filter tests to see if a 
#trade will go against something in one of these timelines. Used mainly for news filters 
class TimelineTradeFilter:
	
	expire = 360 #6 hours -anything after 6 hours can be considered forgotten. Can be changed for different things 
	
	def filter(self,trades):
		return [t for t in trades if self.check_instrument(t.instrument,t.direction,t.the_date)]
	
	
	def check_instrument(self,instrument,direction=TradeDirection.VOID,the_date=datetime.datetime.now()):
		raise NotImplementedError('This method must be overridden')
		return True  #check to see if doing a buy/sell on this pair is a good idea or not 
	
	

##class for determining if a trade is trending in the right direction for example using EMA200
class LineFilter(InstanceTradeFilter):
	
	snapshot = {}
	ma_key = 'ema200' #default to ema200
	
	@overrides(InstanceTradeFilter)
	def check_instrument(self,instrument,direction):
		if direction == TradeDirection.BUY:
			return self.snapshot[instrument]['low_price'] > self.snapshot[instrument][self.ma_key]	
		if direction == TradeDirection.SELL:
			return self.snapshot[instrument]['high_price'] < self.snapshot[instrument][self.ma_key]
		if direction == TradeDirection.VOID:
			return False
		return True

class BandsFilter(InstanceTradeFilter):
	
	snapshot = {}
	lower_key = 'bollinger_band_lower'
	upper_key = 'bollinger_band_upper'

	def check_instrument(self,instrument,direction):
		if direction == TradeDirection.BUY:
			return self.snapshot[instrument]['close_price'] < self.snapshot[instrument][self.upper_key]	
			#	and self.snapshot[pair]['bollinger_band_percent_b'] < 1.0
		if direction == TradeDirection.SELL:
			return self.snapshot[instrument]['close_price'] > self.snapshot[instrument][self.lower_key] 
			#	and self.snapshot[pair]['bollinger_band_percent_b'] > 0
		return False


#store the correlation suggestions and reject anything that goes the oposite way to the suggestion
#only use suggestions that have a suitably high number of N and low variance ---how? :) 
class CorrelationFilter(InstanceTradeFilter):
	
	variance_limit = 0.5 #if variance is as high as this * movement then reject? 
	movement_percentage_limit = 0.05 #must move by 0.1%? 
	n_limit = 5 #at least 5 suggestors needed to predict the movement 
	
	def check_instrument(self,instrument,direction):
		corr = self.snapshot.get(instrument)
		if corr['delta_n'] >= self.n_limit:
			if corr['delta_variance'] < abs(corr['delta']) * self.variance_limit:
				if abs(corr['delta']) > self.movement_percentage_limit:
					if corr['delta'] < 0 and direction == TradeDirection.BUY:
						return False
					if corr['delta'] > 0 and direction == TradeDirection.SELL:
						return False
		return True



#class for determining if a trade is overbought/oversold in any oscillator
class BoundaryFilter(InstanceTradeFilter):
	
	boundary = 0.15 #default rsi is 0.3
	rsi_key = 'relative_strength_index'
	
	def check_instrument(self,instrument,direction):
		if direction == TradeDirection.BUY:
			return self.snapshot[instrument][self.rsi_key] < 1.0 - self.boundary
		if direction == TradeDirection.SELL:
			return self.snapshot[instrument][self.rsi_key] > self.boundary
		return False




##currency specifics 
#helper class for determining if a currency pair should be traded based on 
#what the currency strength says 
class CurrencyStrengthFilter(InstanceTradeFilter):  ##consider making an interface for this such as CurrencyFilter that asserts function check_pair exists
	
	currency_strength = []#snapshot of the currency strength at this moment in time
	tolerance = 2 #rank difference allowed if it is in the wrong direction 
	
	def __init__(self,currency_strength):
		self.currency_strengths = currency_strength
				
	#override
	def check_instrument(self,instrument,direction):
		strengths = self.__get_strengths()
		currpair = CurrencyPair(instrument)
		if direction == TradeDirection.BUY:
			return strengths[currpair.from_currency] - strengths[currpair.to_currency] + self.tolerance > 0
		if direction == TradeDirection.SELL:
			return strengths[currpair.to_currency] - strengths[currpair.from_currency] + self.tolerance > 0
		#single currencies?
		return False 
	
	def __get_strengths(self,key='rank'):
		#key: rank. Also available: movement, average_movement etc 
		return { curr:val[key] for  curr, val in self.currency_strengths.items()}

#filters that can be created from fundamental analysis 
class SentimentFilter(InstanceTradeFilter):
	
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



#reject anything that does the oposite to a macd buy/sell signal
#is this really an instance filter?
class CrossFilter(InstanceTradeFilter):
	
	#can be swapped for any crossover but we will stick with the class name 
	fast_key = 'macd_line'
	slow_key = 'macd_signal'
	__snapshots = []
	__crossovers = {} #holds flags 'UP' 'DOWN' and None ?
	
	def __init__(self,snaps):
		self.__snapshots = snaps
		
	def find_crossovers(self):
		self.__crossovers = {}
		back = self.__snapshots[0] 
		front = self.__snapshots[-1]
		for pair in self.all_pairs:#nope
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
	
	def check_instrument(self,instrument,direction):
		if not self.__crossovers:
			self.find_crossovers() #build the crossover cache 
		cross = self.__crossovers.get(instrument)
		if cross == 'UP' and direction == TradeDirection.SELL:
			return False 
		if cross == 'DOWN' and direction == TradeDirection.BUY:
			return False
		return False



class IndicatorFilter:  ##base this on an indicator so any indicator can be used as a filter? 
	
	expire = 1440 #full day - the timeline should have dates in it at a higher resolution 
	indicator = None
	results = None
	
	def __init__(self,indicator : Indicator, results : np.array): #pass candles instead?
		self.indicator = indicator

	def check_instrument(self,instrument,direction,the_date):
		raise NotImplementedError('This method must be overridden')

	def _closest_time_index(self,the_date):
		timeline = self.indicator.timeline[:,0]
		end_date = the_date 
		start_date = the_date - datetime.timedelta(minutes=self.expire)
		mask = (timeline >= the_date) & (timeline =< end_date)
		inds = np.where(mask)[0]
		if len(inds):
			return inds[-1] #get latest most recent index - might be different for news?
		return None #not found 
		
		
	def _instrument_index(self,instrument):
		instruments = self.indicator.instrument_names 
		if instrument in instruments:
			return instruments.index(instrument)
		return None


class ClientSentimentFilter(IndicatorFilter):
	
	threshold = 0.6
	
	def check_instrument(self,instrument, direction, the_date):
		ti = self._closest_time_index(the_date)
		ii = self._instrument_index(instrument) 
		if ti and ii:
			value = self.results[ti,ii,:]
			long_val = value[0]
			short_val = value[1]
			if direction == TradeDirection.BULLISH:
				if long_val > self.threshold:
					return False
			if direction == TradeDirection.BEARISH:
				if short_val > self.threshold:
					return False
		return True
		

class SpreadTimeFilter(TimelineTradeFilter):
	
	bad_spread_times = {
		'hour':22,
		'min':0,
		'region':30 #minutes 
	}
	
	def check_instrument(self,instrument, direction, the_date):
		the_time = {
			'hour':the_date.hour,
			'min':the_date.min
		}
		
		for bst in self.bad_spread_times:
			if bst['region'] > self.time_diff(the_time,bst):
				#means we are close to this time, so lets avoid trading this.
				return False 
		
		
	
	def time_diff(time1,time2):
		return abs((time1['hour'] - time2['hour'])*60  + time1['min'] - time2['min'])
		
		
#trhis is a bad way of doing it. rework it 
class NewsFilter(IndicatorFilter):
	expire = 360 #6 hours
	ai_invoker = None
	#this will need the AI passed to it and stuff... and perhaps a cache for faster access 
	
	def pass_ai(self,ai):
		self.ai_invoker = ai 
	
	def check_instrument(self,instrument,direction,the_date):
		the_timeline = self.indicator.timelines.get(instrument)
		if the_timeline:
			relevant_timeline = [td for td in the_timeline if td.the_date < the_date and td.the_date ]
		
		return True










	



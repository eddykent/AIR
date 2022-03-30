#helper class for determining if a currency pair should be traded based on 
#what the currency strength says 
class CurrencyStrengthFilter(InstanceTradeFilter):  ##consider making an interface for this such as CurrencyFilter that asserts function check_pair exists
	
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
	

class MACDFilter(InstanceTradeFilter):
	
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
	
	def check_pair(self,instrument,direction):
		if not self.__crossovers:
			self.find_crossovers() #build the crossover cache 
		cross = self.__crossovers.get(instrument)
		if cross == 'UP' and direction == TradeDirection.SELL:
			return False 
		if cross == 'DOWN' and direction == TradeDirection.BUY:
			return False
		return False
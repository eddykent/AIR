#client sentiment - get from indicator that uses volume
#currency strength - could be useful for the 4h timescale etc 

import numpy as np 
from tqdm import tqdm 

import pdb

from utils import overrides
from filters.trade_filter import *
from indicators.volume import ClientSentiment
from indicators.reversal import RSI 

from utils import Database, ListFileReader, Inject

#need to be refactored to call database per trade? 

#client sentiment can be used as an indicator - use lateral indicator filter for this 
class FlatClientSentimentFilter(FlatIndicatorFilter):
	
	client_sentiment = ClientSentiment()
	sentiment_results = None
	
	threshold = 0.3 
	
	@overrides(FlatIndicatorFilter)
	def setup_indicator_results(self):
		self.sentiment_results = self.client_sentiment.calculate_multiple(self.candle_streams)[:,:,0] #0 = long, 1 = short
	
	@overrides(FlatIndicatorFilter)
	def check_instrument(self, instrument, direction, the_time):
		
		ti = self._closest_time_index(the_time)
		ii = self._instrument_index(instrument) 
		
		if ti is not None and ii is not None: 
			if (self.sentiment_results[ii,ti] < (self.threshold)) and direction == TradeDirection.SELL: #if most people are selling too 
				return False #selling when we should be buying 
			if (self.sentiment_results[ii,ti] > (1.0 - self.threshold)) and direction == TradeDirection.BUY: #if most people are buying too 
				return False 
		return True 
	
#need to figure a way to improve this using partial candles & scipy.signal.correlate
class FlatCorrelationFilter(DataBasedFilter):	
	
	n_param = 25   #requires tuning? approx n currency pairs 
	sd_param = 0.05
	p_param = 0.1
	
	_correlation_reports = []
	
	def process_data_piece(self,data_piece):
		
		return [data_piece['predicted_result'],data_piece['result_variance'],data_piece['n_result']]
	
	def check_instrument(self,instrument,direction,the_time):
		
		ti = self._closest_time_index(the_time)
		ii = self._instrument_index(instrument)
		
		correlation_report = self.data_block[ii,ti]
		
		#pdb.set_trace()
		self._correlation_reports.append(correlation_report)
		
		passable = correlation_report[2] > self.n_param#' and correlation_report[1] < self.sd_param 
		
		if passable:	
			if correlation_report[0] >= self.p_param and direction == TradeDirection.SELL:
				return False
			if correlation_report[0] <= -self.p_param and direction == TradeDirection.BUY:
				return False
		return True
	

class FlatCurrencyStrengthFilter(DataBasedFilter):
	
	rank_gap = 0
	
	def process_data_piece(self,data_piece):
		#pdb.set_trace() ##return the strengthco
		#print('check data piece')
		return [data_piece['ranking']]
		
	def check_instrument(self,instrument,direction,the_time):
		
		ti = self._closest_time_index(the_time)
		[fc,tc] = instrument.split('/')
		
		fci = self._instrument_index(fc)
		tci = self._instrument_index(tc)
		
		from_rank = self.data_block[fci,ti,0]
		to_rank = self.data_block[tci,ti,0]
		
		#pdb.set_trace() #bug here somewhere
		
		if from_rank < to_rank + self.rank_gap and direction == TradeDirection.SELL:  
			#to currency is worse than from currency - so we are buying a better and selling a worse (but we are selling so it is reversed) 
			return False
		if to_rank < from_rank + self.rank_gap and direction == TradeDirection.BUY:
			return False 
		
		return True
	
	
class ClientSentimentFilter(PartialIndicatorFilter):
	
	threshold = 0.3 
	
	def filter(self,trade_signals):
		
		client_sentiment_op = ClientSentiment()
		
		filtered_signals = []
		
		np_candles = self._get_candle_streams(trade_signals)
		
		#edit np_candle volumes so they scale "as if" the candle has finished. 
		#pdb.set_trace()
		pclen = 15 #lowest candle length 
		#get the multiplier needed (eg if candle is half finished then mult by 2) 
		npcs = np.array([self._get_n_candles_in_partial(trade_signal,pclen) for trade_signal in trade_signals])
		tnpcs = self.signalling_data.chart_resolution / pclen
		npcs[npcs == 0] = tnpcs
		npc_mult = (tnpcs / npcs)[:,np.newaxis]
		
		np_candles[:,4] *= npc_mult
		np_candles[:,5] *= npc_mult
		
		client_sentiment_results = client_sentiment_op._perform(np_candles)
		end_results = client_sentiment_results[:,-1,0] #gets LONG
		
		
		
		for ts,cs in zip(trade_signals, end_results):
			
			#pdb.set_trace()#check cs
			
			if ts.direction == TradeDirection.BUY and cs < (1.0 - self.threshold):
				#most people are selling -so lets buy!
				filtered_signals.append(ts)
			
			if ts.direction == TradeDirection.SELL and cs > self.threshold:
				#most people are buying! lets allow the sell
				filtered_signals.append(ts)
		
		
		return filtered_signals

#lateral operators 
class CurrencyStrengthOperator: #any other lateral operations? 
	##currency strength functions - consider moving into own tool 
	#for every curency, get whether to add or take the rsi value  
	currencies = []
	instruments = [] 
	
	def __init__(self,instruments, currencies):
		self.currencies = currencies
		self.instruments = instruments
	
	def get_masks(self): 
		currency_pairs = np.array([inst.split('/') for inst in self.instruments])
		result = np.zeros((len(self.currencies),len(self.instruments)))
		for i,currency in enumerate(self.currencies):
			result[i] += (currency_pairs[:,0] == currency).astype(np.int)
			result[i] -= (currency_pairs[:,1] == currency).astype(np.int)
		return result
	
	def get_strengths(self,columns):
		colstrengths = [] 
		masks = self.get_masks()
		for column in columns:  # this is fast enough, but gotta be a better way! 
			strengths = [] 
			for mask in masks: 
				mask = mask[:,np.newaxis]
				rsis = column * mask 
				rsis[rsis < 0] += 1.0
				this_strength= np.sum(rsis,axis=0) 
				strengths.append(this_strength)
			strengths = np.stack(strengths) 
			colstrengths.append(strengths)
		return np.stack(colstrengths)
				
				

class CurrencyStrengthFilter(PartialIndicatorFilter):
	
	rank_diff = 1
	oscillator = None
	smoothing = None
	currency_strength = None
	
	
	def __init__(self,oscillator,currency_strength_operator,smoothing,signalling_data,partial_candles):
		super().__init__(signalling_data,partial_candles)
		
		self.oscillator = oscillator
		self.currency_strength = currency_strength_operator
		self.smoothing = smoothing
		if self.smoothing:
			self.smoothing.instruments = self.currency_strength.currencies
			self.smoothing.candle_channel = 0 

	
	#we want to get the ENTIRE set of candles for every instrument, not just the single lines 
	@overrides(PartialIndicatorFilter)  
	def _get_candles_for_signal(self, signal_index, trade_signal):
		#use self.signalling_data.np_candles and self.timeline 
		ti = self._closest_time_index(
			trade_signal.the_date,
			self.signalling_data.timeline,
			self.signalling_data.chart_resolution
		)
		#ii = self._instrument_index(trade_signal.instrument) 
		pc = None 
		if self.partial_candles:
			pc = self.partial_candles[signal_index]
		candles_back = self.signalling_data.grace_period
		these_candles = self.signalling_data.np_candles[:,ti-candles_back-1:ti-1,:]
		#pdb.set_trace()
		if pc is not None:
			end_candles = np.array(pc)
			end_candle = end_candles[:,np.newaxis,:-1].astype(np.float) #chop date off 
			these_candles = np.concatenate([these_candles[:,1:,:],end_candle],axis=1)
		return these_candles
		
	
	def filter(self,trade_signals):
		
		np_candle_blocks = self._get_candle_streams(trade_signals) #blocks stacked together 
		filtered_signals = []
		np_candles = np.concatenate(np_candle_blocks,axis=0)
		osc_result = self.oscillator._perform(np_candles)[:,:,0] #get just the RSI result
	
		osc_columns = np.array(np.split(osc_result,len(trade_signals)))
		
		currency_strength_blocks = self.currency_strength.get_strengths(osc_columns)
		
		#pdb.set_trace()
		if self.smoothing:
			currency_strengths = np.concatenate(currency_strength_blocks,axis=0)
			smoothing_results = self.smoothing._perform(currency_strengths[:,:,np.newaxis])[:,:,0]
			currency_strength_blocks = np.array(np.split(smoothing_results,len(trade_signals)))
		
		last_currency_strengths = currency_strength_blocks[:,:,-1]
		rankings = np.argsort(last_currency_strengths,axis=1)
		
		currencies = self.currency_strength.currencies
		
		for ts, ranks in zip(trade_signals, rankings):
			buy,sell = ts.instrument.split('/')[:2]
			buy_rank = ranks[currencies.index(buy)]
			sell_rank = ranks[currencies.index(sell)]
			
			#buy rank must be larger than sell rank if we are buying, and smaller if we are selling 
			if ts.direction == TradeDirection.BUY and buy_rank > sell_rank - self.rank_diff:
				filtered_signals.append(ts)
			
			if ts.direction == TradeDirection.SELL and sell_rank > buy_rank - self.rank_diff:
				filtered_signals.append(ts)
		
		return filtered_signals
		

#class CorrelationFilter() #get streams like above, then correlate them using lags and use to get result? 


#class ForexClientStentimentWebFilter(InstanceTradeFilter):	 #web based 
#	pass #this could be a filter that just looks up forex client sentiment website for current client sentiment & overrides the above


#correlations?


##needed for correlations 
#class RSIFilter(LateralIndicatorFilter):
#	
#	_days_back_buffer = 7 #the larger the slower but the more accurate
#	_bounds = 0.2
#
#	
#	#this is painfully slow 
#	def get_candles_for_signal(self,index, trade_signal): 
#	#use this func to get partial candle & rest of candle from initial data read
#		self.candle_data_tool._dbcursor.con.rollback()
#		self.candle_data_tool.end_date = trade_signal.the_date 
#		self.candle_data_tool.start_date = trade_signal.the_date - datetime.timedelta(days=self._days_back_buffer)
#		self.candle_data_tool.read_data_from_instruments([trade_signal.instrument],3)
#		tsd = self.candle_data_tool.get_trade_signalling_data()		
#		return tsd.np_candles
#		
#	@overrides(LateralIndicatorFilter)
#	def filter(self, trade_signals):
#		
#		cursor = Database(cache=False,commit=False)		
#		self.candle_data_tool._dbcursor = cursor #prevent opening/closing connections everytime
#		
#		#load partial candles 
#		
#		rsi_op = RSI()
#		#period?
#		
#		filtered_signals = [] 
#		dbtime = 0
#		intime = 0 
#		
#		partial_candle_end_times  = [the_date for ts in enumerate(trade_signals)]
#		chart_resolution = candle_data_tool
#		
#		
#		for i,ts in tqdm(list(enumerate(trade_signals))):
#			
#			ttt = time.time() 
#			np_candles = self.get_candles_for_signal(i,ts)
#			dbtime += (time.time() - ttt)
#			
#			ttt = time.time()
#			rsi_result = rsi_op._perform(np_candles)[0,-1,0]
#			intime += (time.time() - ttt)
#			
#			if ts.direction == TradeDirection.BUY and rsi_result < (1 - self._bounds):
#				filtered_signals.append(ts)
#			
#			if ts.direction == TradeDirection.SELL and rsi_result > self._bounds:
#				filtered_signals.append(ts)
#		
#		cursor.close() 
#		
#		print('database time: '+str(dbtime))
#		print('indicator time: '+str(intime))
#		
#		return filtered_signals





















#client sentiment - get from indicator that uses volume
#currency strength - could be useful for the 4h timescale etc 

import numpy as np 
from tqdm import tqdm 

import pdb

from utils import overrides
from filters.trade_filter import *
from indicators.volume import ClientSentiment

from utils import Database, ListFileReader, Inject


#client sentiment can be used as an indicator
class ClientSentimentFilter(IndicatorFilter):
	
	client_sentiment = ClientSentiment()
	sentiment_results = None
	
	threshold = 0.3 
	
	@overrides(IndicatorFilter)
	def setup_indicator_results(self):
		self.sentiment_results = self.client_sentiment.calculate_multiple(self.candle_streams)[:,:,0] #0 = long, 1 = short
	
	@overrides(IndicatorFilter)
	def check_instrument(self, instrument, direction, the_time):
		
		ti = self._closest_time_index(the_time)
		ii = self._instrument_index(instrument) 
		
		if ti is not None and ii is not None: 
			if (self.sentiment_results[ii,ti] < (self.threshold)) and direction == TradeDirection.SELL: #if most people are selling too 
				return False #selling when we should be buying 
			if (self.sentiment_results[ii,ti] > (1.0 - self.threshold)) and direction == TradeDirection.BUY: #if most people are buying too 
				return False 
		return True 
	

#pull out and turn into a "database result filter" DataBasedFilter? 
class CorrelationFilter(DataBasedFilter):	
	
	n_param = 25   #requires tuning? approx n currency pairs 
	sd_param = 0.05
	p_param = 0.12
	
	_correlation_reports = []
	
	def process_data_piece(self,data_piece):
		
		return [data_piece['predicted_result'],data_piece['result_variance'],data_piece['n_result']]
	
	def check_instrument(self,instrument,direction,the_time):
		
		ti = self._closest_time_index(the_time)
		ii = self._instrument_index(instrument)
		
		correlation_report = self.data_block[ii,ti]
		#calculate bias
		bias = None 
		
		#pdb.set_trace()
		self._correlation_reports.append(correlation_report)
		
		passable = correlation_report[2] > self.n_param#' and correlation_report[1] < self.sd_param 
		
		if passable:	
			if correlation_report[2] >= self.p_param and direction == TradeDirection.SELL:
				return False
			if correlation_report[2] <= -self.p_param and direction == TradeDirection.BUY:
				return False
		return True
	


class CurrencyStrengthFilter(DataBasedFilter):
	
	rank_gap = 1
	
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
		
		





#class ForexClientStentimentWebFilter(InstanceTradeFilter):	
#	pass #this could be a filter that just looks up forex client sentiment website for current client sentiment & overrides the above


#correlations?

























import datetime
from typing import Optional, List 
import numpy as np #for optimising later 

import pdb 

from utils import CurrencyPair, ListFileReader, overrides, Database
from setups.trade_setup import TradeSignal, TradeDirection
from indicators.indicator import CandleSticks

sql = {}

class TradeFilter:
	pass #unsure what to put here. 


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
	candle_length = None 
	
	def filter(self,trades):
		return [t for t in trades if self.check_instrument(t.instrument,t.direction,t.the_date)]
	
	
	def check_instrument(self,instrument,direction=TradeDirection.VOID,the_date=datetime.datetime.now()):
		raise NotImplementedError('This method must be overridden')
		return True  #check to see if doing a buy/sell on this pair is a good idea or not 


#filters where we can extract out the filter as a mask to '&' to a trigger array 
class ExtractableFilter(TimelineTradeFilter):
	
	def extract_mask(self,instruments,timeline):
		raise NotImplementedError('This method must be overridden')

#slow!
class LateralIndicatorFilter(TimelineTradeFilter):
	
	candle_data_tool = None #use for getting candlestick data per trade
	
	def __init__(self,cdt):	 #CandleDataTool?
		self.candle_data_tool = cdt


#filter based on an indicator but uses one result from the indicator at the filter resolution 
class FlatIndicatorFilter(TimelineTradeFilter):  ##base this on an indicator so any indicator can be used as a filter? 
	
	#expire = 1440 #full day - the timeline should have dates in it at a higher resolution 
	timeline = None 
	instruments = None
	np_candles = None
	candle_streams = None 
	candle_length = None
	
	_instrument_map = {} 
	
	#results = None  #specific to what indicators are used 
	
	def __init__(self,fsd): #TradeSignallingData 

		self.instruments = fsd.instruments
		self.timeline = fsd.timeline 
		self.np_candles = fsd.np_candles 
		self.candle_length = fsd.char_resolution
		self.candle_streams = fsd.candlesticks
		
		for e,i in enumerate(fsd.instruments):	
			self._instrument_map[i] = e
		
		self.setup_indicator_results()
		
	def setup_indicator_results(self):
		raise NotImplementedError('This method must be overridden')
	
	#def check_instrument(self,instrument,direction,the_date):
	#	raise NotImplementedError('This method must be overridden')
	
	def _closest_time_index(self,the_date):
		#unfortunately we dont have the full candle yet in backtesting, so we have to use the previous candle. Otherwise the backtest is wrong.
		the_date = the_date - datetime.timedelta(minutes=self.candle_length) #comment out to use the next candle (backtest will not be correct)

		end_date = the_date 
		start_date = the_date - datetime.timedelta(minutes=self.expire)
		mask = (self.timeline >= start_date) & (self.timeline <= end_date)
		inds = np.where(mask)[0]
		if len(inds):
			return inds[-1] #get latest most recent index - might be different for news?
		return None #not found 
		
		
	def _instrument_index(self,instrument):
		return self._instrument_map.get(instrument)


#powerful tool for getting the "here and now" filter data results for any indicator
#uses partial candles that can be gathered for every signal from the database
#then vectorizes the trades together to be put through the indicator 
#indicator and results handled in filter()
class PartialIndicatorFilter:
	
	signalling_data = None
	partial_candles = []
	_instrument_map = {}
	
	def __init__(self, fsd, pcs = []):	
		self.signalling_data = fsd
		self.partial_candles = pcs
		
		for e,i in enumerate(fsd.instruments):	
			self._instrument_map[i] = e
	
	def _closest_time_index(self,the_date,timeline,candle_length):
		end_date = the_date 
		start_date = the_date - datetime.timedelta(minutes=candle_length)
		mask = (timeline >= start_date) & (timeline <= end_date)
		inds = np.where(mask)[0]
		if len(inds):
			return inds[-1] #get latest most recent index 
		raise ValueError('Time '+str(the_date)+' was not found in timeline')
		return None #not found 
	
	def _instrument_index(self,instrument):
		return self._instrument_map.get(instrument)	
	
	def _get_n_candles_in_partial(self,trade_signal,min_length=15):
		ti = self._closest_time_index(
			trade_signal.the_date,
			self.signalling_data.timeline,
			self.signalling_data.chart_resolution
		)
		tdelt = trade_signal.the_date - self.signalling_data.timeline[ti]
		minutes_diff = (tdelt.days * 3600 * 24) + (tdelt.seconds / 60)
		return minutes_diff // min_length  #remember! min_candle_length = 15 minutes ! 
	
	def _get_candles_for_signal(self, signal_index, trade_signal):
		#use self.signalling_data.np_candles and self.timeline 
		
		ti = self._closest_time_index(
			trade_signal.the_date,
			self.signalling_data.timeline,
			self.signalling_data.chart_resolution
		)
		ii = self._instrument_index(trade_signal.instrument) 
		pc = None 
		if self.partial_candles:
			pc = self.partial_candles[signal_index]
		candles_back = self.signalling_data.grace_period
		these_candles = self.signalling_data.np_candles[ii,ti-candles_back-1:ti-1,:]
		#pdb.set_trace()
		if pc is not None:
			end_candles = np.array(pc)
			end_candle = end_candles[ii,np.newaxis,:-1].astype(np.float) #chop date off 
			these_candles = np.concatenate([these_candles[1:,:],end_candle],axis=0)
		return these_candles
		
	def _get_candle_streams(self,trade_signals):
		np_candle_data = [] 
		
		for (i,ts) in enumerate(trade_signals):
			np_candle_data.append(self._get_candles_for_signal(i,ts))
		
		np_candles = np.stack(np_candle_data) #check 
		return np_candles
	
	def filter(self,trade_signals):
		raise NotImplementedError('This method must be overridden')

#beautiful filter that sorts out the db stuff for us. 
#consider deprecating now... 
class DataBasedFilter(TimelineTradeFilter):
	
	timeline = None
	instruments = None
	_instrument_map = {}
	
	data_block = None #np array?
	
	def __init__(self,data):
		
		self.data_block, self.instruments, self.timeline = self._process_data_block(data)
		
		for e,i in enumerate(self.instruments):	
			self._instrument_map[i] = e


	def _process_data_block(self,data,select_function=None):
		instruments = list(data[0][2].keys())
		timeline = [] 
		instruments = sorted(instruments)
		
		#assert that whole list has all instruments? 
		for timestepdict in data: 
			for inst in instruments:
				if not inst in timestepdict[2]:
					pdb.set_trace()
				assert inst in timestepdict[2], "data is incomplete"
		
		#make correlation block - instrument, timeline, {n_corr, std, up/down change}
		block = [] 
		if select_function and callable(select_function):
			for timestepdict in data:
				block_items = [] 
				timeline.append(timestepdict[0])
				for inst in instruments:
					block_items.append(select_function(timestepdict[2][inst]))
				block.append(block_items)
		else:
			for timestepdict in data:
				block_items = [] 
				timeline.append(timestepdict[0])
				for inst in instruments:
					block_items.append(self.process_data_piece(timestepdict[2][inst]))
				block.append(block_items)
		
		assert len(block), 'no data'
		assert len(block[0]), 'no data' 
		
		dim3 = len(block[0][0])
		dim1 = len(instruments)
		dim2 = len(data)
		
		data_block = np.full((dim1,dim2,dim3),np.nan)  #better way anywhere? 
		for d1 in range(dim1):
			for d2 in range(dim2):
				for d3 in range(dim3):
					try:
						data_block[d1,d2,d3] = block[d2][d1][d3]
					except:
						pdb.set_trace()
		#pdb.set_trace()
		return data_block, instruments, np.array(timeline).reshape((len(timeline),1))


	#weird stuff - perhaps consider refactoring  
	def _closest_time_index(self,the_date):
		return FlatIndicatorFilter._closest_time_index(self,the_date)
	
	def _instrument_index(self,instrument):
		return FlatIndicatorFilter._instrument_index(self,instrument)

	def process_data_piece(self,data_piece):
		raise NotImplementedError('This method must be overridden')

	def check_instrument(self,instrument,direction,the_time):
		raise NotImplementedError('This method must be overridden')




class LambdaSelectFilter(TimelineTradeFilter):	
	
	lambda_function = None
	
	def __init__(self, lambda_function):
		self.lambda_function = lambda_function
		assert callable(lambda_function) , 'LambdaSelectFilter requires a function that maps a trade signal to bool'
	
	#def check_instrument() #dont use
	@overrides(TimelineTradeFilter)
	def filter(self,trades):
		return [t for t in trades if self.lambda_function(t)]





#use this to get a set of partial candles for use with indicator based 
#move to somewhere else? 
class PartialCandleDataTool:
	
	volumes = False 
	instruments = [] 
	chart_resolution = 15
	candle_offset = 0 
	
	_candlesticks = None
	_instruments = None
	
	
	def read_data_from_currencies(self,currencies,trade_times):
		with Database(cache=False,commit=False) as cursor:
			return self.__call_db_read_data_from_currencies(currencies,trade_times,cursor) 
	
	def __call_db_read_data_from_currencies(self,currencies,trade_times,cursor):
		params = {
			'currencies':currencies,
			'trade_times':trade_times,
			'chart_resolution':self.chart_resolution,
			'candle_offset':self.candle_offset
		}
		the_query = 'partial_candles_volumes' if self.volumes else 'partial_candles'
		
		keys = ['open_price','high_price','low_price','close_price']
		keys += ['bid_volume','ask_volume'] if self.volumes else [] 
		keys += ['the_date']
				
		cursor.execute(sql[the_query], params)
		partial_candles = [self.__process_data_row(r[1],keys) for r in cursor.fetchall()]
		return partial_candles
	
	def __process_data_row(self,row,keys):
		if not row or row is None:
			return None #allowed for candles that line up to  the actual time 
		
		return [[ row[inst][k] for k in keys ] for inst in self.instruments]
		
		
		

sql['partial_candles'] = """

WITH partial_candles AS (
	SELECT *
	FROM trading.get_partial_candles_from_currencies(%(currencies)s,%(trade_times)s, %(chart_resolution)s,%(candle_offset)s)
),
result_candles AS (
	SELECT row_index, full_name, to_json(pc) AS candle
	FROM partial_candles pc
),
result_rows AS (
	SELECT row_index, jsonb_object_agg(full_name, candle) AS the_result
	FROM result_candles 
	GROUP BY row_index
),
series AS (
	SELECT generate_series(1,ARRAY_lENGTH(%(trade_times)s,1),1) AS row_index
)
SELECT s.row_index, 
r.the_result 
FROM series s 
LEFT JOIN result_rows r ON s.row_index = r.row_index
ORDER BY s.row_index

"""

sql['partial_candles_volumes'] = """

WITH partial_candles AS (
	SELECT *
	FROM trading.get_partial_candles_volumes_from_currencies(%(currencies)s, %(trade_times)s, %(chart_resolution)s,%(candle_offset)s)
),
result_candles AS (
	SELECT row_index, full_name, to_json(pc) AS candle
	FROM partial_candles pc
),
result_rows AS (
	SELECT row_index, jsonb_object_agg(full_name, candle) AS the_result
	FROM result_candles  
	GROUP BY row_index
),
series AS (
	SELECT generate_series(1,ARRAY_lENGTH(%(trade_times)s,1),1) AS row_index
)
SELECT s.row_index, 
r.the_result 
FROM series s 
LEFT JOIN result_rows r ON s.row_index = r.row_index
ORDER BY s.row_index

"""


	





















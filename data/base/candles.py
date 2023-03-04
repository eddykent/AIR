
import datetime

import numpy as np 

from data.tools.cursor import DataComposer, Database
from setups.signal import TradeSignallingData
from indicators.indicator import CandleSticks, CandleType #should these be somewhere else? 

sql = {}


##for easy/better access to the data 
class CandleDataTool: 
	
	volumes = False 
	instruments = [] 
	chart_resolution = 15
	candle_offset = 0 
	end_date = datetime.datetime.now()
	grace_period = 50 
	start_date =  datetime.datetime.now()#startdate is 
	ask_candles = False
	backtesting = False #if true, get the bid AND the ask candles into np_candles 
	
	
	_candlesticks = None  #data to be read 
	_instruments = None 
	_np_candles = None 
	_timeline = None 
	
	_dbcursor = None 
	
	
	def __init__(self,cursor=None,*args,**kwargs):
		#period doesn't matter here 
		self._dbcursor = cursor 
	
	def __get_days_back(self, grace_period): #n candlesticks to be useful and have RSI setup or whatever 
		mins_in_day = 1440 
		mins_before_start = self.chart_resolution * grace_period 
		delta = self.end_date - self.start_date
		days_back = delta.days + 1
		days_back += int(mins_before_start / mins_in_day) + 1
		days_back += int(delta.days/7) * 2   #buffer period 
		days_back += 2
		return days_back
	
	def read_data_from_currencies(self,currencies,grace_period = 50):  #add soon for from instruments 
		
		if self._dbcursor is not None:  #check is open?
			self.__call_db_read_data_from_currencies(currencies,grace_period,self._dbcursor)
		else:
			with Database(cache=False,commit=False) as cursor:
				self.__call_db_read_data_from_currencies(currencies,grace_period,cursor)
	
	def read_data_from_instruments(self,instruments,grace_period = 50):
	
		if self._dbcursor is not None:  #check is open?
			self.__call_db_read_data_from_instruments(instruments,grace_period,self._dbcursor)
		else:
			with Database(cache=False,commit=False) as cursor:
				self.__call_db_read_data_from_instruments(instruments,grace_period,cursor)
	
	def __call_db_read_data_from_currencies(self,currencies,grace_period,cursor):
		days_back = self.__get_days_back(grace_period)
		composer = DataComposer(cursor,True) #.candles(params).call()...
		if not self.backtesting:
			composer.call('get_candles'+('_volumes_' if self.volumes else '_') + 'from_currencies',{
				'currencies':currencies,
				'this_date':self.end_date,
				'days_back':days_back,
				'chart_resolution':self.chart_resolution,
				'candle_offset':self.candle_offset,
				'ask_candles':self.ask_candles
			})
			candle_result = composer.result(as_json=True)
			candlesticks = DataComposer.as_candles_volumes(candle_result,self.instruments) if self.volumes else DataComposer.as_candles(candle_result,self.instruments)
			self._candlesticks = np.array([candlesticks[instr] for instr in self.instruments if candlesticks.get(instr)]) #always used a block 
			self._instruments = np.array([instr for instr in self.instruments if candlesticks.get(instr)])
			
			candlesticks_pre = CandleSticks()
			if self.volumes:
				candlesticks_pre.candle_type = CandleType.CANDLE_VOLUME
			self._np_candles = candlesticks_pre.calculate_multiple(self._candlesticks)
			self._timeline = candlesticks_pre.timeline[:,0] #this is a 2d array make it 1d
		else:
			composer.call('get_full_from_currencies',{
				'currencies':currencies,
				'this_date':self.end_date,
				'days_back':days_back,
				'chart_resolution':self.chart_resolution,
				'candle_offset':self.candle_offset,
			})
			candle_result = composer.result(as_json=True)
			candlesticks = DataComposer.as_full_candles(candle_result,self.instruments)
			self._candlesticks = np.array([candlesticks[instr] for instr in self.instruments if candlesticks.get(instr)]) #always used a block 
			self._instruments = np.array([instr for instr in self.instruments if candlesticks.get(instr)])
			candlesticks_pre = CandleSticks()
			candlesticks_pre.candle_type = CandleType.FULL_CANDLE
			bidaskcandles = candlesticks_pre.calculate_multiple(self._candlesticks)
			bidcandles = bidaskcandles[:,:,0:4]
			askcandles = bidaskcandles[:,:,4:8]
			self._np_candles = np.stack([bidcandles,askcandles],axis=2)
			self._timeline = candlesticks_pre.timeline[:,0] #this is a 2d array make it 1d
	
	def __call_db_read_data_from_instruments(self,instruments,grace_period,cursor):
		days_back = self.__get_days_back(grace_period)
		composer = DataComposer(cursor,True) #.candles(params).call()...
		if self.backtesting:
			composer.call('get_candles'+('_volumes_' if self.volumes else '_') + 'from_instruments',{
				'instruments':instruments,
				'this_date':self.end_date,
				'days_back':days_back,
				'chart_resolution':self.chart_resolution,
				'candle_offset':self.candle_offset
			})
		
			candle_result = composer.result(as_json=True)
			candlesticks = DataComposer.as_candles_volumes(candle_result,instruments) if self.volumes else DataComposer.as_candles(candle_result,instruments)
			self._candlesticks = np.array([candlesticks[instr] for instr in instruments if candlesticks.get(instr)]) #always used a block 
			self._instruments = np.array([instr for instr in instruments if candlesticks.get(instr)])
			candlesticks_pre = CandleSticks()
			if self.volumes:
				candlesticks_pre.candle_type = CandleType.CANDLE_VOLUME
			self._np_candles = candlesticks_pre.calculate_multiple(self._candlesticks)
			self._timeline = candlesticks_pre.timeline[:,0] #this is a 2d array make it 1d
		else:
			composer.call('get_full_from_instruments',{
				'instruments':instruments,
				'this_date':self.end_date,
				'days_back':days_back,
				'chart_resolution':self.chart_resolution,
				'candle_offset':self.candle_offset
			})
		
			candle_result = composer.result(as_json=True)
			candlesticks = DataComposer.as_full_candles(candle_result,instruments)
			self._candlesticks = np.array([candlesticks[instr] for instr in instruments if candlesticks.get(instr)]) #always used a block 
			self._instruments = np.array([instr for instr in instruments if candlesticks.get(instr)])
			candlesticks_pre = CandleSticks()
			candlesticks_pre.candle_type = CandleType.FULL_CANDLE
			idaskcandles = candlesticks_pre.calculate_multiple(self._candlesticks)
			bidcandles = bidaskcandles[:,:,0:4]
			askcandles = bidaskcandles[:,:,4:8]
			self._np_candles = np.stack([bidcandles,askcandles],axis=2)
			self._timeline = candlesticks_pre.timeline[:,0] #this is a 2d array make it 1d
	
	#use this to get a fresh TradeSignallingData that can be put into any setup
	def get_trade_signalling_data(self):
		
		assert self._candlesticks is not None #these fail if the data has not been read 
		assert self._np_candles is not None
		assert self._timeline is not None
		
		tradesignallingdata = TradeSignallingData()
		tradesignallingdata.start_date = self.start_date
		tradesignallingdata.end_date = self.end_date
		tradesignallingdata.instruments = self._instruments
		tradesignallingdata.candlesticks = self._candlesticks 
		tradesignallingdata.np_candles = self._np_candles
		tradesignallingdata.timeline = self._timeline 
		tradesignallingdata.chart_resolution = self.chart_resolution
		tradesignallingdata.grace_period = self.grace_period
		return tradesignallingdata





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

























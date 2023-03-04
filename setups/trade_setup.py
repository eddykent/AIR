## setups are trades that have been produced from signals from various sources. A TradeSetup class finds trades on a given date 
#that have a high probabily of winning based on their backtest results.  TradeSetup classes need to be backtestable 
#all implementations are in subclasses to this file - it is not possible to import indicator based stuff (circular import?)
from datetime import datetime,timedelta
from typing import Optional, List
import numpy as np
import pandas as pd
import scipy.signal
import scipy.optimize
import string

import pdb


from utils import ListFileReader, PipHandler
from utils import overrides, deprecated
import charting.chart_viewer as chv 
from charting import candle_stick_functions as csf
#from charting.chart_pattern import ChartPattern - unable to import any indicator related stuff here 

from indicators.indicator import CandleSticks, CandleType
from indicators.volatility import ATR

from data.tools.cursor import Database, DataComposer

from setups.signal import *

from setups.setup_tools import ATRStop



#global space function for handling the base cases 
def blank_result(trade_signalling_data,blank_val=None): #blank val can be a 0 or np.nan if needed
	np_candles = trade_signalling_data.np_candles
	result = np.full(np_candles.shape[:2],blank_val) 
	return result, result


#class for holding info about the charts that are created in a setup as well as the chart views 
#consider moving to charting?
class TradeSetupView:
	
	trade_signalling_data = None 
	start_date = None 
	end_date = None 
	instrument = None
	
	charts = {} #candlesticks
	
	def __init__(self, trade_signalling_data, instrument, start_date=None, end_date=None):
		self.trade_signalling_data = trade_signalling_data
		self.instrument = instrument
		self.start_date = start_date 
		self.end_date = end_date 
		self.candlesticks() #initialize candlestick chart
	
	def _np_params(self):
		instrument_ind = self.trade_signalling_data.instrument_index(self.instrument)
		start_ind = self.trade_signalling_data.closest_time_index(self.start_date) if self.start_date is not None else None
		end_ind = self.trade_signalling_data.closest_time_index(self.end_date) if self.end_date is not None else None
		
		return instrument_ind, start_ind, end_ind 
	
	def _y_bounds(self):
		instrument_ind, start_ind, end_ind = self._np_params()
		
		highest = np.max(np_candles[instrument_ind, start_ind:end_ind,csf.high])
		lowest = np.min(np_candles[instrument_ind, start_ind:end_ind,csf.low])
		
		return highest, lowest
	
	def candlesticks(self,np_candles=None): #uses np_candles for any overrides (eg heikin ashi)
		np_candles = self.trade_signalling_data.np_candles if np_candles is None else np_candles
		
		instrument_ind, start_ind, end_ind = self._np_params()
		
		timeline = self.trade_signalling_data.timeline 
		chart_candles = np.concatenate([np_candles[instrument_ind,:,:4],timeline[:,np.newaxis]],axis=1)
		candles_view = chv.ChartView()
		candles_view.draw_candles(chart_candles)
		
		self.charts['candlesticks'] = candles_view
		
	def signals(self,signals):
		chart = self.charts['candlesticks']
		tsd = self.trade_signalling_data
		np_candles = tsd.np_candles 
		these_signals = signals[signals['instrument'] == self.instrument].copy()
		these_signals['timeline_index'] = self.trade_signalling_data.timeline_indexs(these_signals['the_date'])
		
		for signal in these_signals.itertuples(name='PDTradeSignal'):
			
			ii = tsd.instrument_index(signal.instrument)
			ti = signal.timeline_index
			
			entry_line = signal.entry if signal.entry else np_candles[ii,ti,csf.open]
			tp_line = entry_line
			sl_line = entry_line 
			
			if signal.direction == TradeDirection.BUY:
				tp_line += signal.take_profit_distance
				sl_line -= signal.stop_loss_distance
				
			if signal.direction == TradeDirection.SELL: 
				tp_line -= signal.take_profit_distance 
				sl_line += signal.stop_loss_distance
			
			#swap for boxes?
			chart.draw("trades bullish points",chv.Point(ti,tp_line)) #trades
			chart.draw("trades neutral points",chv.Point(ti,entry_line))
			chart.draw("trades bearish points",chv.Point(ti,sl_line))
			
	def filter(self,signals,filtered): 
		chart = self.charts['candlesticks']
		
		signal_dates = signals[signals['instrument'] == self.instrument][['signal_id','the_date']].copy()
		signal_dates['time_index'] = self.trade_signalling_data.timeline_indexs(signal_dates['the_date'])
		filtered_guids = filtered[filtered['instrument'] == self.instrument]['signal_id']
		
		highest, lowest = self._y_bounds()
		
		top = highest - ((highest - lowest)* 0.05)
		bottom = lowest + ((highest - lowest)* 0.05)
		
		for sd in signal_dates:	
			ti = self.trade_signalling_data.closest_time_index(sd.the_date)
			bullbear = ''
			if sd.guid in filtered_guids.values:
				bullbear = 'bearish'
			else:
				bullbear = 'bullish'
			chart.draw(f"caret {bullbear} lines",chv.Line(ti,top,ti,bottom)) #need new draw style?
			
	#change to df
	def backtest(self,signals, results):
		chart = self.charts['candlesticks']
		
		this_df = signals[signals['instrument'] == self.instrument].set_index('signal_id',drop=False).join(results.set_index('signal_id'))
		this_df['timeline_index'] = self.trade_signalling_data.timeline_indexs(this_df['the_date'])
		this_df['start_loc'] = self.trade_signalling_data.timeline_indexs(this_df['entry_date']) - 0.5 
		this_df['end_loc'] = self.trade_signalling_data.timeline_indexs(this_df['exit_date']) + 0.5
		
		for result in this_df.itertuples(): #could vectorise this but might not be much point for drawing :)
			
			#pdb.set_trace()
			#start_ind_old = self.trade_signalling_data.closest_time_index(result.the_date)
			#start_ind = result.timeline_index  
			
			#pdb.set_trace()
			entry_line = result.entry_price
			tp_line = entry_line
			sl_line = entry_line 
			
			bullbear = None
			
			if result.direction == TradeDirection.BUY:
				tp_line += result.take_profit_distance
				sl_line -= result.stop_loss_distance
				
				if result.entry_price < result.exit_price:
					bullbear = 'bullish'
				else:
					bullbear = 'bearish'
				
			if result.direction == TradeDirection.SELL: 
				tp_line -= result.take_profit_distance 
				sl_line += result.stop_loss_distance
				
				if result.entry_price < result.exit_price:
					bullbear = 'bearish'
				else:
					bullbear = 'bullish'
			
			if bullbear is not None:
				x1 = result.start_loc
				x2 = result.end_loc
				y1 = result.entry_price
				y2 = result.exit_price
				#tp_line  #green box 
				#sl_line  #red box 
				#use bullbear for outcome box 
				chart.draw("trades bullish boxes",chv.Box(x1,y1,x2,tp_line)) #tp region 
				chart.draw("trades bearish boxes",chv.Box(x1,y1,x2,sl_line)) #sl region 
				chart.draw(f"trades {bullbear} boxes",chv.Box(x1,y1,x2,y2))
				
	
	def stats(self, backteststats):
		pass # method for passing back test stats to the chart (eg prices, movements, balance)
	
	#these depend on the trade_setup which might be overridden? also they are drawn on other charts than candlesticks 
	def indicators(self,trade_setup):
		instrument_index, start_index, end_index = self._np_params()
		
		np_candles = self.trade_signalling_data.np_candles
		timeline = self.trade_signalling_data.timeline #merge timeline to np_candles?
		#chart_candles = np.concatenate([np_candles[instrument_index,:,:4],timeline[:,np.newaxis]],axis=1)
		
		for ind_key in trade_setup.indicator_bag:
			indicator = trade_setup.indicator_bag[ind_key]
			if indicator.candle_sticks:
				#means draw on main candlestick chart
				#self.charts['candlesticks'] += indficator.draw(np_candles)?
				#pdb.set_trace()
				#chv_result = indicator.draw_snapshot(chart_candles)
				self.charts['candlesticks'] += indicator.draw_snapshot(np_candles,instrument_index)
			
			else:
				chart_key = self.get_chart_key(ind_key) 
				if self.charts.get(chart_key) is None:
					self.charts[chart_key] = chv.ChartView()
				self.charts[chart_key] += indicator.draw_snapshot(np_candles,instrument_index)
	
	#stop tools? 
	
	#def chart_patterns(self,trade_setup):
	#	setup_triggers = trade_setup.trigger(self.trade_signalling_data)
	
	#these are harder to draw - eg how to draw divergence?
	def annotations(self,trade_setup): #only need to draw per signal 
		
		instrument_index, _, _  = self._np_params()
		
		np_candles = self.trade_signalling_data.np_candles
		timeline = self.trade_signalling_data.timeline 
		chart_candles = np.concatenate([np_candles[instrument_index,:,:4],timeline[:,np.newaxis]],axis=1)
		
		#pdb.set_trace()
		bullish,bearish = trade_setup.trigger(self.trade_signalling_data)
		setup_triggers = bullish[instrument_index] | bearish[instrument_index]
		trigger_indexs = np.where(setup_triggers)[0]
		
		for chart_pattern_key in trade_setup.chart_pattern_bag: 
			chart_pattern = trade_setup.chart_pattern_bag[chart_pattern_key]
			#for trigger_index in trigger_indexs: 
			self.charts['candlesticks'] += chart_pattern.draw_snapshot(np_candles,instrument_index,trigger_indexs)
		
		for tool_key in trade_setup.tool_bag: 
			setup_tool = trade_setup.tool_bag[tool_key] #TODO - make some draw_annotations functions 
			setup_tool.draw_annotations(self, trade_setup, instrument_index, trigger_indexs) 
		
	@staticmethod
	def get_chart_key(ind_key): #turn indicator name into chart name it will be drawn on (indicators are grouped together)
		return ind_key.rstrip(string.digits).upper() #eg MACD, RSI, etc ...
	
	

class TradeSetup:	#this not just an indicator - does not have calculate() etc. It is its own thing that finds trade signals 	
	
	grace_period = 10 #number of candles to go back to get an accurate reading at start_date
	stop_calculator = ATRStop() #by default, all trade setups use ATR but for bespoke stops, we can create a new stop tool 
	
	#and set this to an instance 
	setup_name = None
	
	#carry the tools and indicators here for display later
	indicator_bag = {}
	chart_pattern_bag = {} 
	tool_bag = {} #what and how to draw? 
	
	
	def __init__(self, param_settings={}):
		self.indicators()  #call all initializers 
		self.chart_patterns() 
		self.tools() 
		if param_settings:
			self.parameters(param_settings)
	
	#for every setup, put the indicators used in here. They get drawn in full
	def indicators(self):	
		pass 
	
	#chart patterns go in here - so they can be called and drawn at the trigger points 
	def chart_patterns(self):
		pass
		
	#tools that require annotations can be placed in here for drawing at trigger points 
	def tools(self):
		pass
	
	
	#edit default parameters of indicators and re initialize them
	def parameters(self,param_settings={}):
		for (key,settings) in param_settings.items():
			if key in self.indicator_bag:
				clazz = self.indicator_bag[key].__class__
				inst = clazz(**settings)
				self.indicator_bag[key] = inst
			if key in self.chart_pattern_bag:
				clazz = self.chart_pattern_bag[key].__class__
				inst = clazz(**settings)
				self.chart_pattern_bag[key] = inst
			if key in self.tool_bag:
				clazz = self.tool_bag[key].__class__
				inst = clazz(**settings)
				self.tool_bag[key] = inst
				
	
	def trigger(self, trade_signalling_data : TradeSignallingData) -> (np.array, np.array):# - for AI - 0s and 1s or similar delivered from  get_setups()
		"""
		Generate two np array of truths, bullish and bearish. These indicate where on the timeline, for each instrument it is a good time 
		to buy (bullish) or sell (bearish) 
		
		Parameters
		---------
		start_date : datetime 
			The date in which to start looking for setups 
		end_date : datetime 
			The date in which to end looking for setups 
		
		Returns
		-------
		numpy.array 
			A large array (one per instrument) indicating where the buy (positive numbers) and sell (negative numbers) setups were
		"""
		#even though a tradesetup generates trades on the timeframe, they can still be used as filters! just use this detect() method 
		raise NotImplementedError('This method must be overridden') #use get_setups() ! 
	
	def exit(self, trade_signalling_data):
		return blank_result(trade_signalling_data, False)
	
	#value that the price must reach in order to enter the trade 
	def entry(self, trade_signalling_data):
		return blank_result(trade_signalling_data)
		
	#def confidence(self,start_date,end_date): # perhaps worth thinking about later - return confidence value instead for every trigger 
	
	#value that if the price does not reach entry but reaches this first, the trade is cancelled 
	def cancel(self, trade_signalling_data):	
		return blank_result(trade_signalling_data)
	
	def name(self): #get full qualified name for backtesting purposes 
		return self.__class__.__module__ + '.' + self.__class__.__name__ if self.setup_name is None else self.setup_name 
	
	def signals(self, trade_signalling_data : TradeSignallingData) -> List[TradeSignal]:
		"""
		Generate a set of trade signals from this setup generator
		
		Parameters
		---------
		trade_signalling_data : TradeSignallingData 
			A bundle of data that is used + grown to create the signals 
		
		Returns:
		-------
		list(TradeSignal) 
			A bunch of trade signals that were found in the date range 
		"""
		#pdb.set_trace()
		
		#self.indicators() #init indicators for this setup 
		trade_signalling_data.name = self.get_name()
		trade_signalling_data.bullish.signals, trade_signalling_data.bearish.signals = self.trigger(trade_signalling_data)
		trade_signalling_data.bullish.entries, trade_signalling_data.bearish.entries = self.entry(trade_signalling_data)
		trade_signalling_data.bullish.entry_cuts,trade_signalling_data.bearish.entry_cuts = self.cancel(trade_signalling_data)
		(bullish_tp, bullish_sl), (bearish_tp, bearish_sl) = self.stop_calculator.get_stops(trade_signalling_data)
		trade_signalling_data.bullish.take_profit_distances = bullish_tp
		trade_signalling_data.bearish.take_profit_distances = bearish_tp  
		trade_signalling_data.bullish.stop_loss_distances = bullish_sl
		trade_signalling_data.bearish.stop_loss_distances = bearish_sl
		
		#asserts here? 
		
		return self.make_trade_signals(trade_signalling_data)
	
	@staticmethod
	def make_trade_signals(signal_data_extra):	
		strategy_ref = signal_data_extra.name if signal_data_extra.name else 'Please set the name to this setup to something more meaningful!' 
		entry_expire = TradeSignal.entry_expire
		#start_index = signal_data_extra.closest_time_index()
		
		candle_length = signal_data_extra.chart_resolution
		
		trade_signals = pd.DataFrame([])

		#first do buys
		#if signal_data_extra.bullish.signals.any():
		buy_df = pd.DataFrame([])
		(instrument_indexer, timeline_indexer) = np.where(signal_data_extra.bullish.signals)
		buy_df['instrument'] = signal_data_extra.instruments[instrument_indexer]
		buy_df['the_date'] = signal_data_extra.timeline[timeline_indexer] + timedelta(minutes=candle_length)#must add to get END of the candle
		buy_df['strategy_ref'] = str(strategy_ref)
		buy_df['direction'] = TradeDirection.BUY
		buy_df['entry'] = signal_data_extra.bullish.entries[instrument_indexer,timeline_indexer]
		buy_df['entry_cut'] = signal_data_extra.bullish.entry_cuts[instrument_indexer,timeline_indexer]
		buy_df['entry_expire'] = entry_expire
		buy_df['take_profit_distance'] = signal_data_extra.bullish.take_profit_distances[instrument_indexer,timeline_indexer]
		buy_df['stop_loss_distance'] = signal_data_extra.bullish.stop_loss_distances[instrument_indexer,timeline_indexer]
		buy_df['length'] = TradeSignal.length
		trade_signals = trade_signals.append(buy_df)
		#then sells 
		#if signal_data_extra.bearish.signals.any():
		sell_df = pd.DataFrame([])
		(instrument_indexer, timeline_indexer) = np.where(signal_data_extra.bearish.signals)
		sell_df['instrument'] = signal_data_extra.instruments[instrument_indexer]
		sell_df['the_date'] = signal_data_extra.timeline[timeline_indexer] + timedelta(minutes=candle_length)#must add to get END of the candle
		sell_df['strategy_ref'] = str(strategy_ref)
		sell_df['direction'] = TradeDirection.SELL
		sell_df['entry'] = signal_data_extra.bearish.entries[instrument_indexer,timeline_indexer]
		sell_df['entry_cut'] = signal_data_extra.bearish.entry_cuts[instrument_indexer,timeline_indexer]
		sell_df['entry_expire'] = entry_expire
		sell_df['take_profit_distance'] = signal_data_extra.bearish.take_profit_distances[instrument_indexer,timeline_indexer]
		sell_df['stop_loss_distance'] = signal_data_extra.bearish.stop_loss_distances[instrument_indexer,timeline_indexer]
		sell_df['length'] = TradeSignal.length
		trade_signals = trade_signals.append(sell_df)
			
		#get rid of signals that are in grace period
		return_df = trade_signals[trade_signals['the_date'] > signal_data_extra.start_date].copy() 
		#add a unique id
		return_df['signal_id'] = [str(uuid.uuid4()) for _ in range(len(return_df.index))]
		assert np.all(~return_df['signal_id'].duplicated()), 'Duplicate guid found! This should never happen...'
		#return_df.index = return_df['guid'] #good idea?
		#return_df.set_index('signal_id',drop=False)
		return return_df
		
		
		
	
	##helper functions (can be overridden) 
	def get_name(self):
		return self.name()
	
	def get_setups(self,tsd):
		return self.signals(tsd)
	
	#method similar to indicator, but this should show a bunch of signals instead & run a separate drawing tool for the underlying indicators etc used 
	def draw(self,trade_signalling_data : TradeSignallingData, instrument : str, date_from : Optional[datetime.datetime] = None, date_to : Optional[datetime.datetime] = None) -> TradeSetupView: #-add all chart views together. Consider what to do with start_date and end_date  
		"""
		Generate a TradeSetupView object that can be plotted and looked at for inspecting the signals generated from this setup.
		All of  the indicators etc used should be plotted on this chart in this method. Start and end dates are needed to 
		gauge the chart size for the trade setup. 
		
		Parameters
		-----------
		
		
		Returns 	
		-------
		TradeSetupView 
			A collection of chart view objects demonstrating this setup		
		
		"""
		
		trade_setup_view = TradeSetupView(trade_signalling_data, instrument, date_from, date_to) #candlesticks? close prices? base! 
		trade_setup_view.indicators(self) #for indicators and candle stick patterns ?
		trade_setup_view.annotations(self) #for chart patterns and tools
		#self.draw_annotations(trade_setup_view)
		#self.draw_signals(trade_setup_view)		
		return trade_setup_view 
		
		#raise NotImplementedError('This method must be overridden')  #--incorrect? this needs to return a chart view with the trading rectangle 
	














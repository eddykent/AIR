## setups are trades that have been produced from signals from various sources. A TradeSetup class finds trades on a given date 
#that have a high probabily of winning based on their backtest results.  TradeSetup classes need to be backtestable 
#all implementations are in subclasses to this file - it is not possible to import indicator based stuff (circular import?)
from datetime import datetime,timedelta
from typing import Optional, List
import numpy as np
import scipy.signal
import scipy.optimize
import string

import pdb


from utils import ListFileReader, Database, DataComposer, PipHandler
from utils import overrides, deprecated
import charting.chart_viewer as chv 
from charting import candle_stick_functions as csf
#from charting.chart_pattern import ChartPattern - unable to import any indicator related stuff here 

from indicators.indicator import CandleSticks, CandleType
from indicators.volatility import ATR

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
		for signal in signals:
			if signal.instrument == self.instrument:
				
				ii = tsd.instrument_index(signal.instrument)
				ti = tsd.closest_time_index(signal.the_date) 
				
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
		
		signal_tis = {s.signal_id : self.trade_signalling_data.closest_time_index(s.the_date) for s in signals if s.instrument == self.instrument } 
		filtered_s = {f.signal_id for f in filtered}
		
		highest, lowest = self._y_bounds()
		
		top = highest - ((highest - lowest)* 0.05)
		bottom = lowest + ((highest - lowest)* 0.05)
		
		for sti in signal_tis:	
			ti = signal_tis[sti]
			bullbear = ''
			if sti in filtered_s:
				bullbear = 'bearish'
			else:
				bullbear = 'bullish'
			chart.draw(f"caret {bullbear} lines",chv.Line(ti,top,ti,bottom)) #need new draw style?
			
	
	def backtest(self,signals, backtest_result):
		chart = self.charts['candlesticks']
		
		signal_dict = {s.signal_id : s for s in signals} 
		backtest_drawings = []
		
		for br in backtest_result:
			signal = signal_dict.get(br.signal_id)
			
			if signal is None:
				continue 
				
			if signal.instrument != self.instrument:
				continue 
			
			start_ind = self.trade_signalling_data.closest_time_index(signal_dict[br.signal_id].the_date)
			
			entry_line = br.entry_price
			tp_line = entry_line
			sl_line = entry_line 
			
			bullbear = None
			
			if signal.direction == TradeDirection.BUY:
				tp_line += signal.take_profit_distance
				sl_line -= signal.stop_loss_distance
				
				if br.entry_price < br.exit_price:
					bullbear = 'bullish'
				else:
					bullbear = 'bearish'
				
			if signal.direction == TradeDirection.SELL: 
				tp_line -= signal.take_profit_distance 
				sl_line += signal.stop_loss_distance
				
				if br.entry_price < br.exit_price:
					bullbear = 'bearish'
				else:
					bullbear = 'bullish'
			
			if bullbear is not None:
				x1 = self.trade_signalling_data.closest_time_index(br.entry_date) -0.5 
				x2 = self.trade_signalling_data.closest_time_index(br.exit_date) + 0.5
				y1 = br.entry_price
				y2 = br.exit_price
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
				chart_key = ind_key.rstrip(string.digits).upper() #eg MACD, RSI, etc ...
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
			setup_tool.draw_annotations(self, chart_candles, trigger_indexs) 
		
		
	
	

class TradeSetup:	#this not just an indicator - does not have calculate() etc. It is its own thing that finds trade signals 	
	
	grace_period = 10 #number of candles to go back to get an accurate reading at start_date
	stop_calculator = ATRStop() #by default, all trade setups use ATR but for bespoke stops, we can create a new stop tool 
	
	#and set this to an instance 
	setup_name = None
	
	#carry the tools and indicators here for display later
	indicator_bag = {}
	chart_pattern_bag = {} 
	tool_bag = {} #what and how to draw? 
	
	
	def __init__(self):
		self.indicators()  #call all initializers 
		self.chart_patterns() 
		self.tools() 
	
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
				clazz = self.indicator_bag[key] 
				inst = clazz(**settings)
				self.indicator_bag[key] = inst
			if key in self.tool_bag:
				clazz = self.tool_bag[key] 
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
		(bullish_tp, bearish_tp), (bullish_sl, bearish_sl) = self.stop_calculator.get_stops(trade_signalling_data)
		trade_signalling_data.bullish.take_profit_distances = bullish_tp
		trade_signalling_data.bearish.take_profit_distances = bearish_tp  
		trade_signalling_data.bullish.stop_loss_distances = bullish_sl
		trade_signalling_data.bearish.stop_loss_distances = bearish_sl
		
		#asserts here? 
		
		return self.__make_trade_signals(trade_signalling_data)
	
	def __make_trade_signals(self,signal_data_extra):	
		trade_signals = []
		
		#export these? would be much faster for any further computation such as filtering...
		buy_coords = np.stack(np.where(signal_data_extra.bullish.signals),axis=1)
		sell_coords = np.stack(np.where(signal_data_extra.bearish.signals),axis=1)
		
		strategy_ref = signal_data_extra.name if signal_data_extra.name else 'Please set the name to this setup to something more meaningful!' 
		
		entry_expire = TradeSignal.entry_expire
		
		for (instrument_index,timeline_index) in buy_coords:
			timeline_index += 1 #push forward by 1 candle to prevent look ahead bias 
			if timeline_index >= len(signal_data_extra.timeline) or signal_data_extra.timeline[timeline_index] < signal_data_extra.start_date:
				continue
			instrument = signal_data_extra.instruments[instrument_index]
			the_date = signal_data_extra.timeline[timeline_index]
			direction = TradeDirection.BUY
			entry = signal_data_extra.bullish.entries[instrument_index,timeline_index]  
			entry_cut = signal_data_extra.bullish.entry_cuts[instrument_index,timeline_index]  
			take_profit_distance = signal_data_extra.bullish.take_profit_distances[instrument_index,timeline_index]
			stop_loss_distance = signal_data_extra.bullish.stop_loss_distances[instrument_index,timeline_index]
			ts = TradeSignal.from_full(the_date,instrument,strategy_ref,direction,entry,entry_cut,entry_expire,take_profit_distance,stop_loss_distance)
			trade_signals.append(ts)
		
		for (instrument_index,timeline_index) in sell_coords:
			timeline_index += 1 #push forward by 1 candle to prevent look ahead bias 
			if timeline_index >= len(signal_data_extra.timeline) or signal_data_extra.timeline[timeline_index] < signal_data_extra.start_date:
				continue
			instrument = signal_data_extra.instruments[instrument_index]
			the_date = signal_data_extra.timeline[timeline_index]
			direction = TradeDirection.SELL
			entry = signal_data_extra.bearish.entries[instrument_index,timeline_index]  
			entry_cut = signal_data_extra.bearish.entry_cuts[instrument_index,timeline_index]  
			take_profit_distance = signal_data_extra.bearish.take_profit_distances[instrument_index,timeline_index]
			stop_loss_distance = signal_data_extra.bearish.stop_loss_distances[instrument_index,timeline_index]
			ts = TradeSignal.from_full(the_date,instrument,strategy_ref,direction,entry,entry_cut,entry_expire,take_profit_distance,stop_loss_distance)
			trade_signals.append(ts)
		
		return trade_signals
	
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
	














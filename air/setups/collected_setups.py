
import pdb
import numpy as np

#this file contains my own custom setup options that I thought of myself. They are mainly just a collection of patterns and indicators

import logging
log = logging.getLogger(__name__)

from air.utils import overrides
from air.setups.trade_setup import TradeSetup, TradeSignal
from air.charting.chart_pattern import ChartPattern, XtremeWindowSettings 

from air.charting.harmonic_pattern import *  
from air.charting.shape_pattern import * 
from air.charting.trend_pattern import *

import _debugging.functs as dbf


#class IndicatorCollection
#class CandleCollection

class ChartCollection(TradeSetup):
	#this class can be the base that Harmony, Shapes and Trends uses. It can also be used for any collection of charting that uses XWindowBundles
	settings = [] #most favourable last - "find a large pattern" large means further down the list 
	_chart_patterns = [] #rarest first
	grace_period = 100 
	
	remove_conflicts = True
	
	_result_array = []
	_collected_result = [] 
	_result_cdlen = []
	
	@overrides(TradeSetup)
	def trigger(self, trade_signalling_data):
		timeline = trade_signalling_data.timeline
		np_candles = trade_signalling_data.np_candles 
		
		result_array, result_cdlen = self.perform_collection(np_candles)
		collected_result = self.collect_results(result_array)
		
		self._result_array = result_array
		self._result_cdlen = result_cdlen
		
		self._collected_result = collected_result
		
		return collected_result[:,:,0] == 1, collected_result[:,:,0] == -1
		
	def perform_collection(self,np_candles):
		
		result_shape = (np_candles.shape[0],np_candles.shape[1],len(self.settings), len(self._chart_patterns)) #1 for the 0th summary value (-1,0 or 1) 
		result_array = np.full(result_shape,0)
		result_cdlen = np.full(result_shape,0).astype(np.float64) #put into result_array instead? use for getting max harmonic
		
		for si,settings in enumerate(self.settings):    
			base = self._chart_patterns[0]()
			
			base.apply_settings(settings)
			
			dbf.stopwatch('get xtreme_window_bundle')
			xtreme_window_bundle = base.get_xtreme_window_bundle(np_candles)
			dbf.stopwatch('get xtreme_window_bundle')
			
			dbf.stopwatch('perform chart patterns')
			for ci,chart_pattern in enumerate(self._chart_patterns):
				the_ch = chart_pattern()
				the_ch.apply_settings(settings)
				
				try:
					result_ch = the_ch._bundle_perform(xtreme_window_bundle) 
					result_array[:,:,si,ci] = result_ch[:,:,0].astype(int)
					#pdb.set_trace()
					if result_ch.shape[2] > 1: #should also contain breakout size or something for SL later (if needed)
						result_cdlen[:,:,si,ci] = result_ch[:,:,1].astype(np.float64)
				
				except Exception as e:
					result_array[:,:,si,ci] = 0
					pdb.set_trace()
					log.warning(f"failed to perform {the_ch.__class__.__name__} with settings {settings}... \n\tex: {e}")
			dbf.stopwatch('perform chart patterns')
		
		if self.remove_conflicts:
			bull_orders = np.any(result_array ==  1,axis=3) 
			bear_orders = np.any(result_array == -1,axis=3)
			omitted_rows = bull_orders & bear_orders #at each order, if there is one result that says bull and another that says bears it is conflict
			result_array[omitted_rows] = np.zeros(len(self._chart_patterns)) #overwrite to 0s to delete the entries 
		
		return result_array, result_cdlen
	
	
	#process result_array into results of (-1,0,1),settings index,chart pattern index)
	def collect_results(self,result_array):
		
		#for every result get the highest order value (last) that is true and 0 for none (index+1)
		bull_orders = np.any(result_array ==  1,axis=3) 
		bear_orders = np.any(result_array == -1,axis=3)
		mult = np.zeros(result_array.shape[:3]).astype(int) 
		mult[:,:] = np.arange(1,len(self.settings)+1) 
		
		#find out the last occuring index of a pattern that corresponds to the order that was used (higher is better) 
		bull_sis = np.max(bull_orders * mult, axis=2) #assign a number to each true/false value (false*x = 0) and the max will be the latest true
		bear_sis = np.max(bear_orders * mult, axis=2)
		bull_sis = bull_sis - 1  #-1 means 404 pattern not found 
		bear_sis = bear_sis - 1
	
		bull_indexer1 = np.where(bull_sis >= 0)
		bear_indexer1 = np.where(bear_sis >= 0)
		bull_indexer2 = (bull_indexer1[0],bull_indexer1[1],bull_sis[bull_indexer1]) #append the si to the indexs 
		bear_indexer2 = (bear_indexer1[0],bear_indexer1[1],bear_sis[bear_indexer1])
		
		#pdb.set_trace()
		bull_cis = np.argmax(result_array[bull_indexer2],axis=1) #list of [0,1,0,0,1] etc - need to find first occurance not every occurance 
		bear_cis = np.argmin(result_array[bear_indexer2],axis=1) #argmin/argmax does this for us since it will just return the first index of 1/-1
		
		#collected  = bias, order, harmonic "on timeline x, at time y, an order of z harmonic h happened" 
		collected_array = np.full((result_array.shape[0],result_array.shape[1],3),0)
		collected_array[bull_indexer1[0],bull_indexer1[1],0] = 1 
		collected_array[bull_indexer1[0],bull_indexer1[1],1] = bull_sis[bull_indexer1]
		collected_array[bull_indexer1[0],bull_indexer1[1],2] = bull_cis
		
		collected_array[bear_indexer1[0],bear_indexer1[1],0] = -1 
		collected_array[bear_indexer1[0],bear_indexer1[1],1] = bear_sis[bear_indexer1]
		collected_array[bear_indexer1[0],bear_indexer1[1],2] = bear_cis  
		
		return collected_array 

		
		
#bag of harmonic patterns 
#class Harmony(TradeSetup):
#	
#	orders = [1,2,3,4,5,6,7,8,9,10]  #ascending order always (why?) - turn this into settings 
#	harmonics = [Bat,Crab,Butterfly,Gartley,DeepCrab] #rarest first ideally
#	grace_period = HarmonicPattern._required_candles
#	
#	def __init__(self,*args,**kwargs):
#		super().__init__(*args,**kwargs)
#	
#	@overrides(TradeSetup) 
#	def detect(self,trade_signalling_data):  
#		#candleblock, self.instruments = self.get_candlestick_data(start_date,end_date,block=True) #USE trade_signalling_data
#		#timeline = self.get_timeline(candleblock)
#		
#		timeline = trade_signalling_data.timeline
#		np_candles = trade_signalling_data.np_candles 
#		result_shape = (np_candles.shape[0],np_candles.shape[1],len(self.orders), len(self.harmonics)) #1 for the 0th summary value (-1,0 or 1) 
#		result_array = np.full(result_shape,0)
#		result_cdlen = np.full(result_shape,0).astype(np.float64) #put into result_array instead? use for getting max harmonic
#		
#		#this section might be better put in its own function for combining pattern results? 
#		for oi,order in enumerate(self.orders):    
#			base = self.harmonics[0]()
#			base._order = order
#			
#			dbf.stopwatch('get xtreme_window_bundle')
#			xtreme_window_bundle = base.get_xtreme_window_bundle(np_candles)
#			dbf.stopwatch('get xtreme_window_bundle')
#			
#			dbf.stopwatch('perform harmonics')
#			for hi,harmonic in enumerate(self.harmonics):
#				the_h = harmonic()
#				the_h._order = order
#				try:
#					result_h = the_h._bundle_perform(xtreme_window_bundle) #candles not needed in cache?
#					result_array[:,:,oi,hi] = result_h[:,:,0].astype(int)
#					result_cdlen[:,:,oi,hi] = result_h[:,:,1].astype(np.float64)
#				except Exception as e:
#					result_array[:,:,oi,hi] = 0
#					log.warning(f"failed to perform {the_h.__class__.__name__} with order {order}... \n\tex: {e}")
#			dbf.stopwatch('perform harmonics')
#	
#		#pdb.set_trace()
#		#firstly, lets delete bull and bear rows at the order (should never happen with harmonics anyway)		
#		bull_orders = np.any(result_array ==  1,axis=3) 
#		bear_orders = np.any(result_array == -1,axis=3)
#		omitted_rows = bull_orders & bear_orders #at each order, if there is one result that says bull and another that says bears it is conflict
#		result_array[omitted_rows] = np.array([0]*len(self.harmonics)) #overwrite to 0s to delete the entries 
#		
#		#next, for every result get the highest order value (last) that is true and 0 for none (index+1)
#		mult = np.arange(1,len(self.orders)+1) #self.orders? 
#		mult = np.array([mult]*result_array.shape[1])
#		mult = np.array([mult]*result_array.shape[0])
#		
#		#find out the last occuring index of a pattern that corresponds to the order that was used (higher is better) 
#		bull_ois = np.max(bull_orders * mult, axis=2) #assign a number to each true/false value (false*x = 0) and the max will be the latest true
#		bear_ois = np.max(bear_orders * mult, axis=2)
#		bull_ois = bull_ois - 1  #-1 means 404 pattern not found 
#		bear_ois = bear_ois - 1
#	
#		bull_indexer1 = np.where(bull_ois >= 0)
#		bear_indexer1 = np.where(bear_ois >= 0)
#		bull_indexer2 = (bull_indexer1[0],bull_indexer1[1],bull_ois[bull_indexer1]) #append the oi to the indexs 
#		bear_indexer2 = (bear_indexer1[0],bear_indexer1[1],bear_ois[bear_indexer1])
#		
#		#pdb.set_trace()
#		
#		bull_his = np.argmax(result_array[bull_indexer2],axis=1) #list of [0,1,0,0,1] etc - need to find first occurance not every occurance 
#		bear_his = np.argmin(result_array[bear_indexer2],axis=1) #argmin/argmax does this for us since it will just return the first index of 1/-1
#		
#		#collected  = bias, order, harmonic "on timeline x, at time y, an order of z harmonic h happened" 
#		collected_array = np.full((result_array.shape[0],result_array.shape[1],3),0)
#		collected_array[bull_indexer1[0],bull_indexer1[1],0] = 1 
#		collected_array[bull_indexer1[0],bull_indexer1[1],1] = bull_ois[bull_indexer1]
#		collected_array[bull_indexer1[0],bull_indexer1[1],2] = bull_his
#		
#		collected_array[bear_indexer1[0],bear_indexer1[1],0] = -1 
#		collected_array[bear_indexer1[0],bear_indexer1[1],1] = bear_ois[bear_indexer1]
#		collected_array[bear_indexer1[0],bear_indexer1[1],2] = bear_his  
#		
#		#if this was a detect type function, this can be returned
#		
#		
#		pdb.set_trace() 
#		print('check cdlen array & use collected_array to make tpsl distances ')
#		
#		tp_factor = 0.5 #usually, 0.613 is used 
#		sl_factor = 0.333 # usually it is just at D but we will go a bit lower than current price
#		
#		#now make trade signals
#		trade_signals = []
#		for (instrument_index, time_index) in zip(bull_indexer1[0],bull_indexer1[1]):
#			deets = collected_array[instrument_index,time_index] 
#			cdlen = result_cdlen[instrument_index,time_index,deets[1],deets[2]]
#			#if np.isnan(cdlen):
#			#	#print('in bull') #the harmonic index is broken! 
#			#	pdb.set_trace() 
#			#	cdlen = np.nanmax(result_cdlen[instrument_index,time_index,deets[1],:]) #bull
#				
#			tpdistance = cdlen * tp_factor
#			sldistance = cdlen * sl_factor
#			the_date = timeline[time_index]
#			instrument = self.instruments[instrument_index]
#			strategy_ref = self.harmonics[deets[2]].__name__ + f"(order={self.orders[deets[1]]})"
#			direction = TradeDirection.BUY
#			entry = None
#			ts = TradeSignal.from_full(the_date,instrument,strategy_ref,direction,entry,tpdistance,sldistance)
#			trade_signals.append(ts)
#			
#		for (instrument_index, time_index) in zip(bear_indexer1[0],bear_indexer1[1]):
#			deets = collected_array[instrument_index,time_index] 
#			cdlen = result_cdlen[instrument_index,time_index,deets[1],deets[2]]
#			#if np.isnan(cdlen):
#			#	pdb.set_trace()
#			#	cdlen = np.nanmax(result_cdlen[instrument_index,time_index,deets[1],:]) #bear
#			
#			tpdistance = cdlen * tp_factor
#			sldistance = cdlen * sl_factor
#			the_date = timeline[time_index]
#			instrument = self.instruments[instrument_index]
#			strategy_ref = self.harmonics[deets[2]].__name__ + f"(order={self.orders[deets[1]]})"
#			direction = TradeDirection.SELL
#			entry = None
#			ts = TradeSignal.from_full(the_date,instrument,strategy_ref,direction,entry,tpdistance,sldistance)	
#			trade_signals.append(ts)
#			
#		return trade_signals


#all harmonics 
class Harmony(ChartCollection):
	
	_chart_patterns = [Bat,Crab,Butterfly,Gartley,DeepCrab] #rarest first
	settings = [] 
	
	_result_array = []
	_result_cdlen = []
	_collected_result = [] 
	
	def __init__(self,orders=[1,2,3],*args,**kwargs):
		super().__init__(*args,**kwargs)
		self.settings = []
		for o in orders:
			xws = XtremeWindowSettings()
			xws.order = o 
			self.settings.append(xws)
	


class Triangles(ChartCollection):
	_chart_patterns = [RisingTriangle, FallingTriangle, SymmetricalTriangle, RisingWedge, FallingWedge]
	settings = []
	
	def __init__(self,orders=[1,2,3],*args,**kwargs):
		super().__init__(*args,**kwargs)
		self.settings = []
		for o in orders:
			xws = XtremeWindowSettings()
			xws.required_candles = 150
			xws.order = o 
			self.settings.append(xws)

#all trends? 
class Trends(ChartCollection):
	
	_chart_patterns = [Rectangle, ApproximateChannel, RisingTriangle, FallingTriangle, SymmetricalTriangle, RisingWedge, FallingWedge]
	settings = []
	
	def __init__(self,orders=[1,2,3],*args,**kwargs):
		super().__init__(*args,**kwargs)
		self.settings = []
		for o in orders:
			xws = XtremeWindowSettings()
			xws.order = o 
			self.settings.append(xws)

class Shapes(ChartCollection):
	
	_chart_patterns = [TripleExtreme, HeadAndShoulders, DoubleExtreme] #HigherHighs/LowerLows
	settings = []
	
	def __init__(self,orders=[3,5,7,11,13,17],*args,**kwargs):
		super().__init__(*args,**kwargs)
		self.settings = []
		for o in orders:
			xws = XtremeWindowSettings()
			xws.order = o 
			xws.required_candles = 200
			self.settings.append(xws)

#all shapes


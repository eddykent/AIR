
import pdb
import numpy as np

#this file contains my own custom setup options that I thought of myself. They are mainly just a collection of patterns and indicators

from utils import overrides
from setups.trade_setup import TradeSetup, TradeSignal
from charting.harmonic_pattern import *  
from charting.chart_pattern import ChartPattern

import logging
log = logging.getLogger(__name__)

#bag of harmonic patterns 
class Harmony(TradeSetup):
	
	orders = [1,2,3,4,5]  #ascending order always 
	harmonics = [Bat,Crab,Butterfly,Gartley,DeepCrab] #rarest first ideally
	grace_period = HarmonicPattern._required_candles

	def __init__(self,*args,**kwargs):
		super().__init__(*args,**kwargs)
	
	@overrides(TradeSetup) 
	def get_setups(self,start_date,end_date):
		candleblock, self.instruments = self.get_candlestick_data(start_date,end_date,block=True)
		timeline = self.get_timeline(candleblock)
		result_shape = (candleblock.shape[0],candleblock.shape[1],len(self.orders), len(self.harmonics)) #1 for the 0th summary value (-1,0 or 1) 
		result_array = np.full(result_shape,0)
		result_cdlen = np.full(result_shape,0).astype(np.float) #put into result_array instead? use for getting max harmonic
		
		#this section might be better put in its own function for combining pattern results? 
		for oi,order in enumerate(self.orders):    
			base = self.harmonics[0]()
			base._order = order
			init_cache, np_candles = self.get_initial_data(candleblock,base,return_np_candles=True) 
			
			for hi,harmonic in enumerate(self.harmonics):
				the_h = harmonic()
				the_h._order = order
				the_h.set_cache_data(init_cache,set_members=False)
				try:
					result_h = the_h._perform(np_candles) #candles not needed in cache?
					result_array[:,:,oi,hi] = result_h[:,:,0].astype(np.int)
					result_cdlen[:,:,oi,hi] = result_h[:,:,1].astype(np.float)
				except Exception as e:
					result_array[:,:,oi,hi] = 0
					log.warning(f"failed to perform {the_h.__class__.__name__} with order {order}... \n\tex: {e}")
		
		#firstly, lets delete bull and bear rows at the order (should never happen with harmonics anyway)		
		bull_orders = np.any(result_array ==  1,axis=3) 
		bear_orders = np.any(result_array == -1,axis=3)
		omitted_rows = bull_orders & bear_orders #at each order, if there is one result that says bull and another that says bears it is conflict
		result_array[omitted_rows] = np.array([0]*len(self.harmonics)) #overwrite to 0s to delete the entries 
		
		#next, for every result get the highest order value (last) that is true and 0 for none (index+1)
		mult = np.arange(1,len(self.orders)+1) #self.orders? 
		mult = np.array([mult]*result_array.shape[1])
		mult = np.array([mult]*result_array.shape[0])
		
		#find out the last occuring index of a pattern that corresponds to the order that was used (higher is better) 
		bull_ois = np.max(bull_orders * mult, axis=2) #assign a number to each true/false value (false*x = 0) and the max will be the latest true
		bear_ois = np.max(bear_orders * mult, axis=2)
		bull_ois = bull_ois - 1  #-1 means 404 pattern not found 
		bear_ois = bear_ois - 1
	
		bull_indexer1 = np.where(bull_ois >= 0)
		bear_indexer1 = np.where(bear_ois >= 0)
		bull_indexer2 = (bull_indexer1[0],bull_indexer1[1],bull_ois[bull_indexer1]) #append the oi to the indexs 
		bear_indexer2 = (bear_indexer1[0],bear_indexer1[1],bear_ois[bear_indexer1])
		
		pdb.set_trace()
		
		bull_his = np.argmax(result_array[bull_indexer2],axis=1) #list of [0,1,0,0,1] etc - need to find first occurance not every occurance 
		bear_his = np.argmin(result_array[bear_indexer2],axis=1) #argmin/argmax does this for us since it will just return the first index of 1/-1
		
		#collected  = bias, order, harmonic "on timeline x, at time y, an order of z harmonic h happened" 
		collected_array = np.full((result_array.shape[0],result_array.shape[1],3),0)
		collected_array[bull_indexer1[0],bull_indexer1[1],0] = 1 
		collected_array[bull_indexer1[0],bull_indexer1[1],1] = bull_ois[bull_indexer1]
		collected_array[bull_indexer1[0],bull_indexer1[1],2] = bull_his
		
		collected_array[bear_indexer1[0],bear_indexer1[1],0] = -1 
		collected_array[bear_indexer1[0],bear_indexer1[1],1] = bear_ois[bear_indexer1]
		collected_array[bear_indexer1[0],bear_indexer1[1],2] = bear_his  
		
		#if this was a detect type function, this can be returned
		
		
		#pdb.set_trace() 
		print('check cdlen array & use collected_array to make tpsl distances ')
		
		tp_factor = 0.5 #usually, 0.613 is used 
		sl_factor = 0.333 # usually it is just at D but we will go a bit lower than current price
		
		#now make trade signals
		trade_signals = []
		for (instrument_index, time_index) in zip(bull_indexer1[0],bull_indexer1[1]):
			deets = collected_array[instrument_index,time_index] 
			cdlen = result_cdlen[instrument_index,time_index,deets[1],deets[2]]
			#if np.isnan(cdlen):
			#	#print('in bull') #the harmonic index is broken! 
			#	pdb.set_trace() 
			#	cdlen = np.nanmax(result_cdlen[instrument_index,time_index,deets[1],:]) #bull
				
			tpdistance = cdlen * tp_factor
			sldistance = cdlen * sl_factor
			the_date = timeline[time_index]
			instrument = self.instruments[instrument_index]
			strategy_ref = self.harmonics[deets[2]].__name__ + f"(order={self.orders[deets[1]]})"
			direction = TradeDirection.BUY
			entry = None
			ts = TradeSignal.from_full(the_date,instrument,strategy_ref,direction,entry,tpdistance,sldistance)
			trade_signals.append(ts)
			
		for (instrument_index, time_index) in zip(bear_indexer1[0],bear_indexer1[1]):
			deets = collected_array[instrument_index,time_index] 
			cdlen = result_cdlen[instrument_index,time_index,deets[1],deets[2]]
			#if np.isnan(cdlen):
			#	pdb.set_trace()
			#	cdlen = np.nanmax(result_cdlen[instrument_index,time_index,deets[1],:]) #bear
			
			tpdistance = cdlen * tp_factor
			sldistance = cdlen * sl_factor
			the_date = timeline[time_index]
			instrument = self.instruments[instrument_index]
			strategy_ref = self.harmonics[deets[2]].__name__ + f"(order={self.orders[deets[1]]})"
			direction = TradeDirection.SELL
			entry = None
			ts = TradeSignal.from_full(the_date,instrument,strategy_ref,direction,entry,tpdistance,sldistance)	
			trade_signals.append(ts)
			
		return trade_signals




#all shapes?
	
		
	
#all trends? 










from collections import namedtuple
import numpy as np 
#import scipy


import pdb

import charting.chart_viewer as chv 
import charting.candle_stick_functions as csf
from setups.trade_setup import TradeSignal, TradeDirection, SetupCriteria
from indicators.indicator import Indicator
from utils import overrides 

from charting.chart_pattern import ChartPattern



HarmonicRule = namedtuple('HarmonicRule','name tool min max touch_max')
hkeys = {
	'X':0,
	'A':1,
	'B':2,
	'C':3,
	'D':4
}

class HarmonicPattern(ChartPattern):
	
	_required_candles = 100
	_xtreme_degree = 1 #possibly not needed - order seems to work better. 
	_order = 5 #test? might have no points! 
	_breakout_candles = 1 #just look at the last candle only 
	
	#def test_bears(self,xabcds):
	#	pass
	
	#def test_bulls(self,xabcds):
	#	pass
	
	harmonic_rules = [] #fill in subclasses! 
	
	def _test_shape(self,xabcds):  #sign might not matter. should be abstract but use bat for now 
				
		rule_pieces = [np.full((xabcds.shape[0],),True)]
		for rule in self.harmonic_rules:
			params = list(rule.name)
			f,s,t = params[:3]
			rule_result = np.full((xabcds.shape[0],),True)
			if rule.min is not None:
				rule_result = rule_result & (rule.tool(xabcds[:,hkeys[f]],xabcds[:,hkeys[s]],xabcds[:,hkeys[t]]) >= rule.min)
			if rule.max is not None: 
				rule_result = rule_result & (rule.tool(xabcds[:,hkeys[f]],xabcds[:,hkeys[s]],xabcds[:,hkeys[t]]) <= rule.max)
			#what about touch_max?
			
			rule_pieces.append(rule_result)
		rule_outputs = np.stack(rule_pieces,axis=1)
		return np.all(rule_outputs,axis=1) #check
	
	@overrides(ChartPattern)
	def _chart_perform(self, xtreme_windows, breakout_windows, x_start_pos):
		xabcds_xvt = self._get_xabcds(xtreme_windows,breakout_windows,x_start_pos)
		xabcds = xabcds_xvt[:,:,1]
		shape_pass = self._test_shape(xabcds)
		bullish = xabcds[:,0] < xabcds[:,1] #simply, if X is below A, then it must be a bullish pattern
		bearish = xabcds[:,0] > xabcds[:,1]
		bias = np.full((xtreme_windows.shape[0],),0)
		bias[bullish] = 1
		bias[bearish] = -1
		bias[~shape_pass] = 0
		#pdb.set_trace()
		return bias[:,np.newaxis] # add X for the SL value
		
		

	@overrides(Indicator) #we may want to keep the chart pattern draw snapshot func? 
	def draw_snapshot(self,np_candles,snapshot_index,instrument_index):
		#do usual mask to get relevant xtremes 
		mask = self._create_mask(np_candles,instrument_index,snapshot_index)
		xtreme_windows, _ = self._generate_xtreme_windows(np_candles,mask,xtreme_degree=self._xtreme_degree,precandles=self._precandles)
		breakout_windows = self._get_breakout_windows(np_candles,mask)
		x_positions = self._get_x_positions(np_candles,mask)
		
		#determine direction with first x in xabcd, determine if it is indeed the pattern 
		xabcds_xvt = self._get_xabcds(xtreme_windows,breakout_windows,x_positions)
		shape_pass = self._test_shape(xabcds_xvt[:,:,1])
		
		this_view = chv.ChartView()
		for xabcd_xvt in xabcds_xvt[np.where(shape_pass)]:
			style = ''
			if xabcd_xvt[0,1] < xabcd_xvt[1,1]:
				style = 'bullish'
			if xabcd_xvt[0,1] > xabcd_xvt[1,1]:
				style = 'bearish'
			
			#then draw the lines to the min/max points 
			if style:
				path = [chv.Point(p[0],p[1]) for p in xabcd_xvt]
				this_view.draw('patterns '+style+' path',path)
		
		return this_view

		
	def _get_xabcds(self,xtreme_windows,breakout_windows,x_start_pos):
		#ast5test = xtreme_windows[:,:,-5:] #another posibility, but might not work as well as below 
		#pdb.set_trace()
		end_points = np.stack([x_start_pos + self._breakout_candles - 1,breakout_windows[:,-1,csf.close],np.full(x_start_pos.shape,np.nan)],axis=1)
		return np.concatenate([xtreme_windows[:,-4:,:],end_points[:,np.newaxis,:]],axis=1)
	
	#helper methods 
	@staticmethod
	def retracement(value1,value2,the_value):
		result = np.zeros((value1.shape[0],))
		mask = np.where(value1 != value2)
		result[mask] = (the_value[mask] - value2[mask]) / (value1[mask] - value2[mask])
		return result

	@staticmethod
	def extension(value1,value2,the_value):  
		result = np.zeros((value1.shape[0],))
		mask = np.where(value1 != value2)
		result[mask] = (the_value[mask] - value1[mask]) / (value2[mask] - value1[mask])
		return result

	

#class Bat,Gartley,Crab,DeepCrab,Cypher,Butterfly,  (Shark, ABCD)
	
class Butterfly(HarmonicPattern):
	
	harmonic_rules = [
		HarmonicRule('XAB',HarmonicPattern.retracement,0.786,1.0,False),
		HarmonicRule('ABC',HarmonicPattern.retracement,0.382,0.886,True),
		HarmonicRule('XAD',HarmonicPattern.retracement,1.27,None,True),
		HarmonicRule('ABD',HarmonicPattern.extension,1.618,2.24,False)
	]
	
	
class Gartley(HarmonicPattern):
	
	harmonic_rules = [
		HarmonicRule('XAB',HarmonicPattern.retracement,0.618,0.886,False),
		HarmonicRule('ABC',HarmonicPattern.retracement,0.382,0.886,True),
		HarmonicRule('XAD',HarmonicPattern.retracement,0.786,None,True),
		HarmonicRule('ABD',HarmonicPattern.extension,1.13,1.618,False)
	]
	
	
class Bat(HarmonicPattern):
	
	harmonic_rules = [
		HarmonicRule('XAB',HarmonicPattern.retracement,0.382,0.5,True),
		HarmonicRule('ABC',HarmonicPattern.retracement,0.382,0.886,True),
		HarmonicRule('XAD',HarmonicPattern.retracement,0.886,None,True),
		HarmonicRule('ABD',HarmonicPattern.extension,1.618,2.618,False)
	]
	
class Crab(HarmonicPattern):
	
	harmonic_rules = [
		HarmonicRule('XAB',HarmonicPattern.retracement,0.382,0.618,False),
		HarmonicRule('ABC',HarmonicPattern.retracement,0.382,0.886,False),
		HarmonicRule('XAD',HarmonicPattern.retracement,1.618,None,True),
		HarmonicRule('ABD',HarmonicPattern.extension,2.24,3.618,False)
	]

class DeepCrab(HarmonicPattern):
	
	harmonic_rules = [
		HarmonicRule('XAB',HarmonicPattern.retracement,0.886,1.0,False),
		HarmonicRule('ABC',HarmonicPattern.retracement,0.382,0.886,False),
		HarmonicRule('XAD',HarmonicPattern.retracement,1.618,None,True),
		HarmonicRule('ABD',HarmonicPattern.extension,2.24,3.618,False)
	]
	

#needs more work 
class Cypher(HarmonicPattern):
	
	harmonic_rules = [ #perhaps find another definition of cypher somewhere... 
		HarmonicRule('XAB',HarmonicPattern.retracement,0.382,0.618,True),
		HarmonicRule('XAC',HarmonicPattern.extension,1.272,1.414,True),
		HarmonicRule('XCD',HarmonicPattern.retracement,0.786,None,True)#,
		#HarmonicRule('XCBD',HarmonicPattern.retracement,-1,0.786,False) #this rule breaks :(
	]















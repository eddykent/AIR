
import datetime
import numpy as np 


import pdb

#candle patterns - Engulfing, Pinbar, Soilders/Crows, MorningEveningStars, AbandonedIsland, ThreeLineStrikes, Inside/Outside?
from indicators.indicator import Indicator
import charting.candle_stick_functions as csf
import charting.chart_viewer as chv

from utils import overrides

#class CandleStickException(Exception):
	
#candle stick patterns return a list of -1, to 1s -1 is a bear, 1 is a bull and 0 is no pattern detected
class CandleStickPattern(Indicator):
	
	_required_candles = 1 #number of candles needed for this pattern - used in a sliding window 
	pattern_name  = "Candle stick pattern"
	
	def explain(self):
		return """
		A candle stick pattern is an arrangement of open,high,low and close values from a selection of candles. 
		When they are arranged in a particular way they form a pattern. 
		"""
	
	@overrides(Indicator)
	def draw_snapshot(self,candles,index=-1): #draw all patterns we can find as boxes on the chart. 
		
		this_view = chv.ChartView()
		the_type = self.detect(candles)

		for i,t in enumerate(the_type):
			these_candles = candles[i-self._required_candles+1 : i+1]
			if not these_candles:
				continue
			the_max = max([c[csf.high] for c in these_candles])
			the_min = min([c[csf.low] for c in these_candles])
			if t > 0:
				y1 = the_max
				y2 = the_min
				x1 = i - self._required_candles + 0.5
				x2 = i + 0.5
				this_view.draw('candle_boxes bullish boxes',chv.Box(x1,y1,x2,y2))
			if t < 0:
				y1 = the_max
				y2 = the_min
				x1 = i - self._required_candles + 0.5
				x2 = i + 0.5
				this_view.draw('candle_boxes bearish boxes',chv.Box(x1,y1,x2,y2))
				
		return this_view
		
	@overrides(Indicator)
	def _perform(self,np_candles): #override in the classes below
		#turn candlestreams into windows, flattern, perform, unflattern, pad left then return 		
		
		#note: this section is required instead of sliding on np_candles. 
		#need to have a list of candles, not candle of lists! :) 
		np_open = np_candles[:,:,csf.open]
		np_high = np_candles[:,:,csf.high]
		np_low = np_candles[:,:,csf.low]
		np_close = np_candles[:,:,csf.close]
		
		
		open_windows = np.lib.stride_tricks.sliding_window_view(np_open,window_shape=self._required_candles,axis=1)
		high_windows = np.lib.stride_tricks.sliding_window_view(np_high,window_shape=self._required_candles,axis=1)
		low_windows = np.lib.stride_tricks.sliding_window_view(np_low,window_shape=self._required_candles,axis=1)
		close_windows = np.lib.stride_tricks.sliding_window_view(np_close,window_shape=self._required_candles,axis=1)
				
		candle_windows = np.stack([open_windows,high_windows,low_windows,close_windows],axis=3)
		candle_windows_shape = list(candle_windows.shape)
		
		#candlewindows dimensions = (nstreams,streamlen,windowlen,4) (4=>candle open,high,low,close)
		flat_windows_shape = [candle_windows_shape[0] * candle_windows_shape[1]] + candle_windows_shape[2:]
		flat_windows = candle_windows.reshape(flat_windows_shape)
		
		pattern_result = self._candle_perform(flat_windows)  #should be flat list
		pattern_result = pattern_result.reshape((candle_windows_shape[0],candle_windows_shape[1],1))
		
		if self._required_candles > 1:
			padding = np.zeros((candle_windows_shape[0],self._required_candles-1,1))#pad? 
			pattern_result = np.concatenate([padding,pattern_result],axis=1)
		
		return pattern_result
		
	def _candle_perform(self,candle_windows):
		raise NotImplementedError("This method must be overridden")
	
	@overrides(Indicator)
	def detect(self,candle_stream,candle_stream_index=-1,criteria=[]): #for now, ignore criteria 
		return self.calculate(candle_stream,candle_stream_index)
		
class PinBar(CandleStickPattern):
	
	_required_candles = 1
	pin_length = 2.5
	
	@overrides(CandleStickPattern) 
	def _candle_perform(self,candle_windows):
		return_block = np.zeros(candle_windows.shape[0])
		candle = candle_windows[:,0,:] #there is only 1 candle in the window (we treat it "like" it is 1 candle to keep it simple - but really np is magical and it is many candles at once)
		top_heavy = csf.top_heavy(candle,self.pin_length)
		bottom_heavy = csf.bottom_heavy(candle,self.pin_length)
		
		return_block[top_heavy] = 1.0
		return_block[bottom_heavy] = -1.0
		return return_block
			

class Engulfing(CandleStickPattern):
	
	_required_candles = 2
	engulf_difference = 1.5

	def __init__(self):
		pass
	
	@overrides(CandleStickPattern) 
	def _candle_perform(self,candle_windows):	
		return_block = np.zeros(candle_windows.shape[0])
		candle1 = candle_windows[:,0,:]
		candle2 = candle_windows[:,1,:]
		
		bottom1 = csf.body_bottom(candle1)
		bottom2 = csf.body_bottom(candle2)
		top1 = csf.body_top(candle1)
		top2 = csf.body_top(candle2)
	
		engulfer = csf.engulf(candle1,candle2,self.engulf_difference)
		aligned = (top1 <= top2) & (bottom1 >= bottom2)
		bullish1 = csf.bullish(candle1) 
		bearish1 = csf.bearish(candle1)
		bullish2 = csf.bullish(candle2)
		bearish2 = csf.bearish(candle2)
		
		bullish_engulfer = engulfer & aligned & bearish1 & bullish2
		bearish_engulfer = engulfer & aligned & bullish1 & bearish2
		return_block[bullish_engulfer] = 1.0
		return_block[bearish_engulfer] = -1.0
		
		
		#if csf.engulf(candle1,candle2,self.engulf_difference):
		#	candle1,candle2 = candles[-2:]	
		#	if csf.bearish(candle1) and csf.bullish(candle2):
		#		#we must check: 1) we hit some support level 
		#		#2) candle 2 has shot up above candle 1
		#		#3) finally, the first candle is at the bottom of the second candle
		#		if candle1[csf.close] >= candle2[csf.open] and 
		#			candle1[csf.open] < candle2[csf.close] and 
		#			candle2[csf.close] - candle2[csf.open] > (1.0 - self.engulf_difference) * csf.body(candle1):
		#			return 1.0
		#	if csf.bullish(candle1) and csf.bearish(candle2):
		#		#we must check: 1) we hit some resistance level
		#		#candle 2 has shot down
		#		#candle1 is at the top of candle2
		#		if candle1[csf.close] <= candle2[csf.open] and 
		#			candle1[csf.open] > candle2[csf.close] and 
		#			candle1[csf.open] - candle2[csf.close] > (1.0 - self.engulf_difference) * csf.body(candle1):
		#			return -1.0
		
		return return_block
		
		
class SoldiersAndCrows(CandleStickPattern):
	
	_required_candles = 3
	fat_tolerance = 0.5
	
	@overrides(CandleStickPattern)
	def _candle_perform(self,candle_windows):	
		return_block = np.zeros(candle_windows.shape[0])
		
		candle1 = candle_windows[:,0,:]
		candle2 = candle_windows[:,1,:]
		candle3 = candle_windows[:,2,:]
		allfat = csf.fat(candle1,self.fat_tolerance) & csf.fat(candle2,self.fat_tolerance) & csf.fat(candle3,self.fat_tolerance)
		
		stepups = csf.step_up(candle1,candle2) & csf.step_up(candle2,candle3)
		stepdowns = csf.step_down(candle1,candle2) & csf.step_down(candle2,candle3)
		
		return_block[allfat & stepups] = 1.0
		return_block[allfat & stepdowns] = -1.0
		
		return return_block

class MorningEveningStars(CandleStickPattern):
	
	_required_candles = 3
	doji_ratio = 0.15 #body must be 1/doji_ratio times smaller than range
	wick_ballance = 0.6
	fat_tolerance = 0.4
	
	@overrides(CandleStickPattern)
	def _candle_perform(self,candle_windows):	
		return_block = np.zeros(candle_windows.shape[0])
		#check middle candle is a doji star
		candle1 = candle_windows[:,0,:]
		candle2 = candle_windows[:,1,:]
		candle3 = candle_windows[:,2,:]
		
		doji = csf.doji(candle2,self.doji_ratio) & csf.ballanced_wicks(candle2,self.wick_ballance)
		fats = csf.fat(candle1,self.fat_tolerance) & csf.fat(candle3,self.fat_tolerance)
		bullish1 = csf.bullish(candle1)
		bullish3 = csf.bullish(candle3)
		bearish1 = csf.bearish(candle1)
		bearish3 = csf.bearish(candle3)
		
		bull_star = doji & fats & bearish1 & bullish3
		bear_star = doji & fats & bullish1 & bearish3
		
		return_block[bull_star] = 1.0
		return_block[bear_star] = -1.0
		
		#if csf.doji(candles[1],self.doji_ratio) and csf.ballanced_wicks(candles[1],self.wick_ballance):#middle candle must be a doji star
		#	if csf.fat(candles[0],self.fat_tolerance) and csf.fat(candles[2],self.fat_tolerance):
		#		if csf.bearish(candles[0]) and csf.bullish(candles[2]): #might need to check star is fully below the other candles
		#			return 1.0
		#		if csf.bullish(candles[0]) and csf.bearish(candles[2]):
		#			return -1.0
		
		return return_block
		
#class AbandonedCandles(CandleStickPattern): #much better for stocks - not forex
#	pass
	
class ThreeLineStrikes(CandleStickPattern):		
	
	_required_candles = 4
	fat_tolerance = 2.0
	
	@overrides(CandleStickPattern)
	def _candle_perform(self,candle_windows):	
		return_block = np.zeros(candle_windows.shape[0])
		
		candle1 = candle_windows[:,0,:]
		candle2 = candle_windows[:,1,:]
		candle3 = candle_windows[:,2,:]
		candle4 = candle_windows[:,3,:]
		
		stepdowns = csf.step_down(candle1,candle2) & csf.step_down(candle2,candle3)
		swipeup = (candle4[:,csf.open] <= candle3[:,csf.close]) & (candle4[:,csf.close] >= candle1[:,csf.open])
		
		stepups =  csf.step_up(candle1,candle2) & csf.step_up(candle2,candle3)
		swipedown = (candle4[:,csf.open] >= candle3[:,csf.close]) & (candle4[:,csf.close] <= candle1[:,csf.open])
		
		return_block[stepdowns & swipeup] = 1.0
		return_block[stepups & swipedown] = -1.0
		return return_block
		
		
class Harami(CandleStickPattern):	#or whatever it is called! :)
	
	_required_candles = 2
	
	@overrides(CandleStickPattern)
	def _candle_perform(self,candle_windows):	
		return_block = np.zeros(candle_windows.shape[0])
		candle0 = candle_windows[:,0,:]
		candle1 = candle_windows[:,1,:]
		
		shrunk = (csf.range(candle1) <= csf.body(candle0))
		aligned = (candle0[:,csf.low] < candle1[:,csf.low]) & (candle0[:,csf.high] > candle1[:,csf.high])
		harami = shrunk & aligned
		bullish0 = csf.bullish(candle0)
		bearish0 = csf.bearish(candle0)
		bullish1 = csf.bullish(candle1)
		bearish1 = csf.bearish(candle1)
		
		return_block[harami & bullish0 & bearish1] = -1
		return_block[harami & bearish0 & bullish1] = 1
		
		return return_block


#two inside
#two outside






















import datetime

import pdb

#candle patterns - Engulfing, Pinbar, Soilders/Crows, MorningEveningStars, AbandonedIsland, ThreeLineStrikes, Inside/Outside?

import charting.candle_stick_functions as csf
import charting.chart_viewer as cpv
#class CandleStickException(Exception):
	
#candle stick patterns return a list of -1, to 1s -1 is a bear, 1 is a bull and 0 is no pattern detected
class CandleStickPattern(object):
	
	_required_candles = 1 #number of candles needed for this pattern
	pattern_name  = "Candle stick pattern"
	
	def __init__(self):
		pass
		
	#function to override  - should return 1 for buy, -1 for sell and 0 for neutral
	def _determine(self,candles):
		return 0
	
	def _size_check(self,candles):
		if len(candles) >= self._required_candles:
			return self._determine(candles)
		return 0
	
	def detect(self,candle_stream):
		return self._window_function(self._size_check,candle_stream,self._required_candles)
	
	@staticmethod
	def _window_function(func,candles,window_size):
		if not callable(func):
			#what the hell?
			raise Exception('Function is not callable')
		return [func(candles[max(i-window_size,0):i]) for i in range(len(candles))] #starts with lists of wrong size
	
	@staticmethod
	def to_candles(sequence,instrument):
		return sorted([
			[
				snapshot[2][instrument]['open_price'],
				snapshot[2][instrument]['high_price'],	
				snapshot[2][instrument]['low_price'],
				snapshot[2][instrument]['close_price'],
				snapshot[0] #datetime for debugging if needed...
			]
		for snapshot in sequence],key=lambda c:c[4]) #sort into chronological order 
	
	
	#def draw_snapshot(self,index,candles):
	#	the_indexs = list(range(index-self._required_candles,index))
	#	the_candles = candles[index-self._required_candles:index]
	#	suitable_height = (sum([csf.range(candle) for candle in candles]) / len(candles)) * 0.4
	#	suitable_width = 0.4
	#	high = csf.highest_body(the_candles)
	#	low = csf.lowest_body(the_candles)
	#	y = [
	#		low - suitable_height,
	#		high + suitable_height,
	#		high + suitable_height,
	#		low - suitable_height,
	#		low - suitable_height
	#	]
	#	x = [
	#		index - self._required_candles - suitable_width, 
	#		index - self._required_candles - suitable_width, 
	#		index - 1 + suitable_width, 
	#		index - 1 + suitable_width,
	#		index - self._required_candles - suitable_width]
	#	arrow_x = [index - 1, index - 1]
	#	arrow_y = csf.lowest(candles), csf.lowest(candles) - suitable_height
	#	return (x,y,arrow_x,arrow_y,the_candles,the_indexs)
	
	def draw_snapshot(self,candles,index):
		
		this_view = cpv.ChartPatternView()
		this_view.draw_candles(candles)
		return this_view
		
	

class Engulfing(CandleStickPattern):
	
	_required_candles = 2
	engulf_difference = 1.5

	def __init__(self):
		pass
	
	#@overrides(CandleStickPattern) #requires a method called overrides
	def _determine(self,candles):	
		if csf.engulf(candles,self.engulf_difference):
			candle1,candle2 = candles[-2:]	
			if csf.bearish(candle1) and csf.bullish(candle2):
				#we must check: 1) we hit some support level 
				#2) candle 2 has shot up above candle 1
				#3) finally, the first candle is at the bottom of the second candle
				if candle1[csf.close] >= candle2[csf.open] and \
					candle1[csf.open] < candle2[csf.close] and \
					candle2[csf.close] - candle2[csf.open] > (1.0 - self.engulf_difference) * csf.body(candle1):
					return 1.0
			if csf.bullish(candle1) and csf.bearish(candle2):
				#we must check: 1) we hit some resistance level
				#candle 2 has shot down
				#candle1 is at the top of candle2
				if candle1[csf.close] <= candle2[csf.open] and \
					candle1[csf.open] > candle2[csf.close] and \
					candle1[csf.open] - candle2[csf.close] > (1.0 - self.engulf_difference) * csf.body(candle1):
					return -1.0
		return 0
		
		
class PinBar(CandleStickPattern):
	
	_required_candles = 1
	pin_length = 2.5
	
	#@overrides(CandleStickPattern) 
	def _determine(self,candles):
		if csf.top_heavy(candles[0],self.pin_length):
			return 1.0
		if csf.bottom_heavy(candles[0],self.pin_length):
			return -1.0
		return 0
		
		
class SoldiersAndCrows(CandleStickPattern):
	
	_required_candles = 3
	fat_tolerance = 0.5
	
	#@overides(CandleStickPattern)
	def _determine(self,candles):
		if all(csf.fat(candle,self.fat_tolerance) for candle in candles):
			if csf.hop_up(candles[0:2]) and csf.hop_up(candles[1:]):
				return 1.0
			if csf.hop_down(candles[0:2]) and csf.hop_down(candles[1:]):
				return -1.0
		return 0

class MorningEveningStars(CandleStickPattern):
	
	_required_candles = 3
	doji_ratio = 0.15 #body must be 1/doji_ratio times smaller than range
	wick_ballance = 0.6
	fat_tolerance = 0.4
	
	#@overrides(CandleStickPattern)
	def _determine(self,candles):
		#check middle candle is a doji star
		if csf.doji(candles[1],self.doji_ratio) and csf.ballanced_wicks(candles[1],self.wick_ballance):#middle candle must be a doji star
			if csf.fat(candles[0],self.fat_tolerance) and csf.fat(candles[2],self.fat_tolerance):
				if csf.bearish(candles[0]) and csf.bullish(candles[2]): #might need to check star is fully below the other candles
					return 1.0
				if csf.bullish(candles[0]) and csf.bearish(candles[2]):
					return -1.0
		return 0
		
#class AbandonedCandles(CandleStickPattern): #much better for stocks - not forex
#	pass
	
class ThreeLineStrikes(CandleStickPattern):		
	
	_required_candles = 4
	fat_tolerance = 2.0
	
	def _determine(self,candles):
		if all(csf.fat(candle,self.fat_tolerance) for candle in candles):
			if csf.hop_up(candles[0:2]) and csf.hop_up(candles[1:3]):
				strike_height = csf.body_top(candles[2]) - csf.body_bottom(candles[0])
				if csf.body(candles[3]) > strike_height and csf.bearish(candles[3]):
					return -1.0
			if csf.hop_down(candles[0:2]) and csf.hop_down(candles[1:3]):
				strike_height = csf.body_top(candles[0]) - csf.body_bottom(candles[2])
				if csf.body(candles[3]) > strike_height and csf.bullish(candles[3]):
					return 1.0
		return 0
		
		
class Harami(CandleStickPattern):	#or whatever it is called! :)
	
	_required_candles = 2
	
	#@Overrides 
	def _determine(self,candles):
		if csf.range(candles[1]) <= csf.body(candles[0]): #we have a harami
			if csf.bullish(candles[0]) and csf.bearish(candles[1]):
				return -1
			if csf.bearish(candles[0]) and csf.bullish(candles[1]):
				return 1
		return 0
























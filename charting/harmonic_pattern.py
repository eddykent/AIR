from collections import namedtuple
from enum import Enum


import pdb

import charting.candle_stick_functions as csf
from charting.chart_pattern import *
import charting.chart_viewer as chv

#tuple for holding indexs of harmonic patterns 
XABCD = namedtuple('XABCD','direction x a b c d')
HarmonicLeg = namedtuple('HarmonicLeg','name tool min max touch_max')

class HarmonicDirection(Enum):
	BEARISH = -1
	VOID = 0
	BULLISH = 1

#for own confirmations - not actually used anywhere
def fibonacci(n):
    fibonacci_numbers = [1, 1]
    for i in range(2, n+1):
        fibonacci_numbers.append(fibonacci_numbers[i-1] + fibonacci_numbers[i-2])
    return fibonacci_numbers 

#for own confirmations
def fractional_fib(n,accurancy=1000):
	fib_nums = fibonacci(accurancy)
	return fib_nums[accurancy-n] / fib_nums[accurancy]

#for reference
retractments = [
	0.114,
	0.236,
	0.382,
	0.500, #added to all patterns usually! 
	0.618,
	0.707, #unsure about this one
	0.764,
	0.886,
	1.000,
	1.128,
	1.236,
	1.272, #not sure what this is 
	1.382,
	1.500,
	1.618,
	1.764,
	2.618
]

class HarmonicPattern(ChartPattern):
	
	
	harmonic_legs = []
	
	
	@staticmethod
	def retracement(value1,value2,the_value):
		return ((the_value - value2) / (value1 - value2)) if value1 != value2 else 0
	
	@staticmethod
	def extension(value1,value2,the_value):  
		return ((the_value - value1) / (value2 - value1)) if value1 != value2 else 0
	
	
	def get_xabcd(self,candle_stream,candle_stream_index):
		extremes = self._get_extremes(candle_stream_index)
		for e in reversed(extremes): #consider trying to find larger patterns by not exiting early then comparing the D 
			xabcd = self._get_abcd(e,candle_stream,candle_stream_index)
			if xabcd.direction != HarmonicDirection.VOID:
				return xabcd
		return XABCD(HarmonicDirection.VOID,None,None,None,None,None)

	def _determine(self,candle_stream_index,candle_stream):
		#C->D >= A->B and 
		xabcd = self.get_xabcd(candle_stream,candle_stream_index)
		
		if xabcd.direction == HarmonicDirection.BULLISH:
			if xabcd.d == candle_stream_index:
				return 1 * self.pattern_fitness(candle_stream,candle_stream_index,xabcd)
				
		if xabcd.direction == HarmonicDirection.BEARISH:
			if xabcd.d == candle_stream_index:
				return -1 * self.pattern_fitness(candle_stream,candle_stream_index,xabcd)
		
		return 0
	
	#can optimise with dict?
	def _get_legs_for(self,point):
		return [hl for hl in self.harmonic_legs if hl.name[2] == point.upper()]
	
	
	def _height_check(self,value1,value2,direction):
		if direction == HarmonicDirection.BULLISH:
			return value1 > value2
		if direction == HarmonicDirection.BEARISH:
			return value2 > value1
		return False
	
	def _height_check_against(self,value1,value2,direction):
		if direction == HarmonicDirection.BULLISH:
			return value1 < value2
		if direction == HarmonicDirection.BEARISH:
			return value2 < value1
		return False
	
	def _get_abcd(self,start_point,candle_stream, candle_stream_index):
		
		#assume start_point is a minimum
		end_index = min(start_point.index+self.memory_window,candle_stream_index)
		
		points = {
			'X':start_point.index,
			'A':None,
			'B':None,
			'C':None,
			'D':None
		}
		X = start_point.index
		A = None #high candle
		B = None #low candle#store the candles that we find when checking this window
		C = None #new high candle
		D = None #new low candle
		
		b_leg =  self._get_legs_for('B')[0]
		c_leg =  self._get_legs_for('C')[0]
		d_legs = self._get_legs_for('D')
		
		
		wicks = {}
		direction = HarmonicDirection.VOID
		
		if start_point.type == ExtremityType.MINIMUM: #looking for bullish harmonics
			wicks = {
				'X':csf.low,
				'A':csf.high,
				'B':csf.low,
				'C':csf.high,
				'D':csf.low #replace with close?
			}
			direction = HarmonicDirection.BULLISH
		
		if start_point.type == ExtremityType.MAXIMUM:
			wicks = {
				'X':csf.high,
				'A':csf.low,
				'B':csf.high,
				'C':csf.low,
				'D':csf.high
			}
			direction = HarmonicDirection.BEARISH
		
		
		
		for i,candle in enumerate(candle_stream[start_point.index:end_index+1]):
			if i == 0:
				continue
			index = i + start_point.index
			
			#finding A
			if A is None or (self._height_check(candle[wicks['A']],candle_stream[A][wicks['A']],direction) and B is None): 
				A = index  
				B = None
				C = None
			
			#finding B
			elif A is not None and b_leg.tool(candle_stream[X][wicks['X']],candle_stream[A][wicks['A']],candle[wicks['B']]) > b_leg.min and C is None:
								
				if B is None or self._height_check_against(candle[wicks['B']],candle_stream[B][wicks['B']],direction):
					B = index
				
				if b_leg.tool(candle_stream[X][wicks['X']],candle_stream[A][wicks['A']],candle[wicks['B'] if b_leg.touch_max else csf.close]) > b_leg.max: #pattern is off if the market closes after this value
					#A = None #pattern is invalidated
					B = None
					C = None
					break
			
			#finding C
			elif B is not None and c_leg.tool(candle_stream[A][wicks['A']],candle_stream[B][wicks['B']],candle[wicks['C']]) > c_leg.min:  
				if C is None or self._height_check(candle[wicks['C']],candle_stream[C][wicks['C']],direction):
					C = index
				
				if c_leg.tool(candle_stream[A][wicks['A']],candle_stream[B][wicks['B']],candle[wicks['C'] if c_leg.touch_max else csf.close]) > c_leg.max:  
					#A = None #pattern is invalidated
					B = None
					C = None
					#break - #nope, continue from A 
			
			#finding D
			elif C is not None and d_legs[0].tool(candle_stream[X][wicks['X']],candle_stream[A][wicks['A']],candle[wicks['D']]) > d_legs[0].min: 
				#no d_legs[0] max 
														
				if d_legs[1].tool(candle_stream[A][wicks['A']],candle_stream[B][wicks['B']],candle[wicks['D']]) > d_legs[1].max:
					#A = None #pattern is invalidated
					B = None
					C = None
					D = None
					break#pattern is invalidated
				
				elif d_legs[1].tool(candle_stream[A][wicks['A']],candle_stream[B][wicks['B']],candle[wicks['D']]) > d_legs[1].min:
					D = index
					return XABCD(direction,X,A,B,C,D) #return as soon as we identity D 		
		
							
		return XABCD(HarmonicDirection.VOID,X,A,B,C,D)
	
	
	
	def pattern_fitness(self,candle_stream,candle_stream_index,xabcd):	
		return 1.0
	
	
	def draw_snapshot(self,candle_stream,snapshot_index):
		
		base_view = super().draw_snapshot(candle_stream,snapshot_index)
		
		xabcd = self.get_xabcd(candle_stream,snapshot_index)
		
		if xabcd.direction == HarmonicDirection.BULLISH:
			X = chv.Point(xabcd.x, candle_stream[xabcd.x][csf.low])
			A = chv.Point(xabcd.a, candle_stream[xabcd.a][csf.high])
			B = chv.Point(xabcd.b, candle_stream[xabcd.b][csf.low])
			C = chv.Point(xabcd.c, candle_stream[xabcd.c][csf.high])
			D = chv.Point(xabcd.d, candle_stream[xabcd.d][csf.low])
			base_view.draw('patterns bullish path',[X,A,B,C,D])
			
		if xabcd.direction == HarmonicDirection.BEARISH:
			X = chv.Point(xabcd.x, candle_stream[xabcd.x][csf.high])
			A = chv.Point(xabcd.a, candle_stream[xabcd.a][csf.low])
			B = chv.Point(xabcd.b, candle_stream[xabcd.b][csf.high])
			C = chv.Point(xabcd.c, candle_stream[xabcd.c][csf.low])
			D = chv.Point(xabcd.d, candle_stream[xabcd.d][csf.high])
			base_view.draw('patterns bearish path',[X,A,B,C,D])
		
		return base_view
	
class Butterfly(HarmonicPattern):
	
	harmonic_legs = [
		HarmonicLeg('XAB',HarmonicPattern.retracement,0.786,1.0,False),
		HarmonicLeg('ABC',HarmonicPattern.retracement,0.382,0.886,True),
		HarmonicLeg('XAD',HarmonicPattern.retracement,1.27,None,True),
		HarmonicLeg('ABD',HarmonicPattern.extension,1.618,2.24,False)
	]
	
	
class Gartley(HarmonicPattern):
	
	harmonic_legs = [
		HarmonicLeg('XAB',HarmonicPattern.retracement,0.618,0.886,False),
		HarmonicLeg('ABC',HarmonicPattern.retracement,0.382,0.886,True),
		HarmonicLeg('XAD',HarmonicPattern.retracement,0.786,None,True),
		HarmonicLeg('ABD',HarmonicPattern.extension,1.13,1.618,False)
	]
	
	def _get_abcd(self,start_point,candle_stream, candle_stream_index):
		#assume start_point is a minimum
		end_index = min(start_point.index+self.memory_window,candle_stream_index)
		Found = False
		X = start_point.index
		A = None #high candle
		B = None #low candle#store the candles that we find when checking this window
		C = None #new high candle
		D = None #new low candle
		
		if start_point.type == ExtremityType.MINIMUM: #looking for bullish harmonics
			
			for i,candle in enumerate(candle_stream[start_point.index:end_index+1]):
				if i == 0:
					continue
				index = i + start_point.index
				
				#finding A
				if A is None or (candle[csf.high] > candle_stream[A][csf.high] and B is None): 
					A = index  
					B = None
					C = None
				
				#finding B
				elif A is not None and self.retracement(candle_stream[X][csf.low],candle_stream[A][csf.high],candle[csf.low]) > 0.618 and C is None:
					if B is None or candle[csf.low] < candle_stream[B][csf.low]:
						B = index
					
					if self.retracement(candle_stream[X][csf.low],candle_stream[A][csf.high],candle[csf.low]) > 0.886: #pattern is off if the market closes after this value
						#A = None #pattern is invalidated
						B = None
						C = None
						#break
				
				#finding C
				elif B is not None and self.retracement(candle_stream[A][csf.high],candle_stream[B][csf.low],candle[csf.high]) > 0.382:  
					if C is None or candle[csf.high] > candle_stream[C][csf.high]:
						C = index
					if self.retracement(candle_stream[A][csf.high],candle_stream[B][csf.low],candle[csf.high]) > 0.886: #check! if close or high (allowed to touch?) 
						#A = None #pattern is invalidated
						B = None
						C = None
						#break
				
				#finding D
				elif C is not None and self.retracement(candle_stream[X][csf.low],candle_stream[A][csf.high],candle[csf.low]) > 0.786:
															
					if self.extension(candle_stream[A][csf.high],candle_stream[B][csf.low],candle[csf.low]) > 1.618:
						#A = None #pattern is invalidated
						B = None
						C = None
						D = None
						#break#pattern is invalidated
					
					elif self.extension(candle_stream[A][csf.high],candle_stream[B][csf.low],candle[csf.low]) > 1.13:
						D = index
						return XABCD(HarmonicDirection.BULLISH,X,A,B,C,D) #return as soon as we identity D 		
		
		
		if start_point.type == ExtremityType.MAXIMUM: #looking for bearish bat harmonics
			
			for i,candle in enumerate(candle_stream[start_point.index:end_index+1]):
				if i == 0:
					continue
				index = i + start_point.index
				
				#finding A
				if A is None or (candle[csf.low] < candle_stream[A][csf.low] and B is None): 
					A = index  
					B = None
					C = None
				
				#finding B
				elif A is not None and self.retracement(candle_stream[X][csf.high],candle_stream[A][csf.low],candle[csf.high]) > 0.618 and C is None:
					if B is None or candle[csf.high] > candle_stream[B][csf.high]:
						B = index
					
					if self.retracement(candle_stream[X][csf.high],candle_stream[A][csf.low],candle[csf.high]) > 0.886: #pattern is off if the market closes after this value
						#A = None #pattern is invalidated
						B = None
						C = None
						#break
				
				#finding C
				elif B is not None and self.retracement(candle_stream[A][csf.low],candle_stream[B][csf.high],candle[csf.low]) > 0.382:  
					if C is None or candle[csf.low] < candle_stream[C][csf.low]:
						C = index
					if self.retracement(candle_stream[A][csf.low],candle_stream[B][csf.high],candle[csf.low]) > 0.886: #check! if close or low (allowed to touch?) 
						#A = None #pattern is invalidated
						B = None
						C = None
						#break
				
				#finding D
				elif C is not None and self.retracement(candle_stream[X][csf.high],candle_stream[A][csf.low],candle[csf.high]) > 0.786:
															
					if self.extension(candle_stream[A][csf.low],candle_stream[B][csf.high],candle[csf.high]) > 1.618:
						#A = None #pattern is invalidated
						B = None
						C = None
						D = None
						#break#pattern is invalidated
					
					elif self.extension(candle_stream[A][csf.low],candle_stream[B][csf.high],candle[csf.high]) > 1.13:
						D = index
						return XABCD(HarmonicDirection.BEARISH,X,A,B,C,D) #return as soon as we identity D 		
		
					
		return XABCD(HarmonicDirection.VOID,X,A,B,C,D)
	
class Bat(HarmonicPattern):
		
	def _get_abcd(self,start_point,candle_stream, candle_stream_index):
		#assume start_point is a minimum
		end_index = min(start_point.index+self.memory_window,candle_stream_index)
		Found = False
		X = start_point.index
		A = None #high candle
		B = None #low candle#store the candles that we find when checking this window
		C = None #new high candle
		D = None #new low candle
		
		if start_point.type == ExtremityType.MINIMUM: #looking for bullish harmonics
			
			for i,candle in enumerate(candle_stream[start_point.index:end_index+1]):
				if i == 0:
					continue
				index = i + start_point.index
				
				#finding A
				if A is None or (candle[csf.high] > candle_stream[A][csf.high] and B is None): 
					A = index  
					B = None
					C = None
				
				#finding B
				elif A is not None and self.retracement(candle_stream[X][csf.low],candle_stream[A][csf.high],candle[csf.low]) > 0.382 and C is None:
					if B is None or candle[csf.low] < candle_stream[B][csf.low]:
						B = index
					
					if self.retracement(candle_stream[X][csf.low],candle_stream[A][csf.high],candle[csf.close]) > 0.5: #pattern is off if the market closes after this value
						#A = None #pattern is invalidated
						B = None
						C = None
						#break
				
				#finding C
				elif B is not None and self.retracement(candle_stream[A][csf.high],candle_stream[B][csf.low],candle[csf.high]) > 0.382:  
					if C is None or candle[csf.high] > candle_stream[C][csf.high]:
						C = index
					if self.retracement(candle_stream[A][csf.high],candle_stream[B][csf.low],candle[csf.close]) > 0.886: #check! if close or high (allowed to touch?) 
						#A = None #pattern is invalidated
						B = None
						C = None
						#break
				
				#finding D
				elif C is not None and self.retracement(candle_stream[X][csf.low],candle_stream[A][csf.high],candle[csf.low]) > 0.886:
															
					if self.extension(candle_stream[A][csf.high],candle_stream[B][csf.low],candle[csf.low]) > 2.618:
						#A = None #pattern is invalidated
						B = None
						C = None
						D = None
						#break#pattern is invalidated
					
					elif self.extension(candle_stream[A][csf.high],candle_stream[B][csf.low],candle[csf.low]) > 1.618:
						D = index
						return XABCD(HarmonicDirection.BULLISH,X,A,B,C,D) #return as soon as we identity D 		
		
		
		if start_point.type == ExtremityType.MAXIMUM: #looking for bearish bat harmonics
			
			for i,candle in enumerate(candle_stream[start_point.index:end_index+1]):
				if i == 0:
					continue
				index = i + start_point.index
				
				#finding A
				if A is None or (candle[csf.low] < candle_stream[A][csf.low] and B is None): 
					A = index  
					B = None
					C = None
				
				#finding B
				elif A is not None and self.retracement(candle_stream[X][csf.high],candle_stream[A][csf.low],candle[csf.high]) > 0.382 and C is None:
					if B is None or candle[csf.high] > candle_stream[B][csf.high]:
						B = index
					
					if self.retracement(candle_stream[X][csf.high],candle_stream[A][csf.low],candle[csf.close]) > 0.5: #pattern is off if the market closes after this value
						#A = None #pattern is invalidated
						B = None
						C = None
						#break
				
				#finding C
				elif B is not None and self.retracement(candle_stream[A][csf.low],candle_stream[B][csf.high],candle[csf.low]) > 0.382:  
					if C is None or candle[csf.low] < candle_stream[C][csf.low]:
						C = index
					if self.retracement(candle_stream[A][csf.low],candle_stream[B][csf.high],candle[csf.close]) > 0.886: #check! if close or low (allowed to touch?) 
						#A = None #pattern is invalidated
						B = None
						C = None
						#break
				
				#finding D
				elif C is not None and self.retracement(candle_stream[X][csf.high],candle_stream[A][csf.low],candle[csf.high]) > 0.886:
															
					if self.extension(candle_stream[A][csf.low],candle_stream[B][csf.high],candle[csf.high]) > 2.618:
						#A = None #pattern is invalidated
						B = None
						C = None
						D = None
						#break#pattern is invalidated
					
					elif self.extension(candle_stream[A][csf.low],candle_stream[B][csf.high],candle[csf.high]) > 1.618:
						D = index
						return XABCD(HarmonicDirection.BEARISH,X,A,B,C,D) #return as soon as we identity D 		
		
					
		return XABCD(HarmonicDirection.VOID,X,A,B,C,D)


class Crab(HarmonicPattern):
	
	
	def _get_abcd(self,start_point,candle_stream, candle_stream_index):
		#assume start_point is a minimum
		end_index = min(start_point.index+self.memory_window,candle_stream_index)
		Found = False
		X = start_point.index
		A = None #high candle
		B = None #low candle#store the candles that we find when checking this window
		C = None #new high candle
		D = None #new low candle
		
		if start_point.type == ExtremityType.MINIMUM: #looking for bullish harmonics
			
			for i,candle in enumerate(candle_stream[start_point.index:end_index+1]):
				if i == 0:
					continue
				index = i + start_point.index
				
				#finding A
				if A is None or (candle[csf.high] > candle_stream[A][csf.high] and B is None): 
					A = index  
					B = None
					C = None
				
				#finding B
				elif A is not None and self.retracement(candle_stream[X][csf.low],candle_stream[A][csf.high],candle[csf.low]) > 0.382 and C is None:
					if B is None or candle[csf.low] < candle_stream[B][csf.low]:
						B = index
					
					if self.retracement(candle_stream[X][csf.low],candle_stream[A][csf.high],candle[csf.low]) > 0.618: #pattern is off if the market closes after this value
						#A = None #pattern is invalidated
						B = None
						C = None
						#break
				
				#finding C
				elif B is not None and self.retracement(candle_stream[A][csf.high],candle_stream[B][csf.low],candle[csf.high]) > 0.382:  
					if C is None or candle[csf.high] > candle_stream[C][csf.high]:
						C = index
					if self.retracement(candle_stream[A][csf.high],candle_stream[B][csf.low],candle[csf.high]) > 0.886: #check! if close or high (allowed to touch?) 
						#A = None #pattern is invalidated
						B = None
						C = None
						#break
				
				#finding D
				elif C is not None and self.retracement(candle_stream[X][csf.low],candle_stream[A][csf.high],candle[csf.low]) > 1.618:
															
					if self.extension(candle_stream[A][csf.high],candle_stream[B][csf.low],candle[csf.low]) > 3.618:
						#A = None #pattern is invalidated
						B = None
						C = None
						D = None
						#break#pattern is invalidated
					
					elif self.extension(candle_stream[A][csf.high],candle_stream[B][csf.low],candle[csf.low]) > 2.24:
						D = index
						return XABCD(HarmonicDirection.BULLISH,X,A,B,C,D) #return as soon as we identity D 		
		
		
		if start_point.type == ExtremityType.MAXIMUM: #looking for bearish bat harmonics
			
			for i,candle in enumerate(candle_stream[start_point.index:end_index+1]):
				if i == 0:
					continue
				index = i + start_point.index
				
				#finding A
				if A is None or (candle[csf.low] < candle_stream[A][csf.low] and B is None): 
					A = index  
					B = None
					C = None
				
				#finding B
				elif A is not None and self.retracement(candle_stream[X][csf.high],candle_stream[A][csf.low],candle[csf.high]) > 0.382 and C is None:
					if B is None or candle[csf.high] > candle_stream[B][csf.high]:
						B = index
					
					if self.retracement(candle_stream[X][csf.high],candle_stream[A][csf.low],candle[csf.high]) > 0.618: #pattern is off if the market closes after this value
						#A = None #pattern is invalidated
						B = None
						C = None
						#break
				
				#finding C
				elif B is not None and self.retracement(candle_stream[A][csf.low],candle_stream[B][csf.high],candle[csf.low]) > 0.382:  
					if C is None or candle[csf.low] < candle_stream[C][csf.low]:
						C = index
					if self.retracement(candle_stream[A][csf.low],candle_stream[B][csf.high],candle[csf.close]) > 0.886: #check! if close or low (allowed to touch?) 
						#A = None #pattern is invalidated
						B = None
						C = None
						#break
				
				#finding D
				elif C is not None and self.retracement(candle_stream[X][csf.high],candle_stream[A][csf.low],candle[csf.high]) > 1.618:
															
					if self.extension(candle_stream[A][csf.low],candle_stream[B][csf.high],candle[csf.high]) > 3.618:
						#A = None #pattern is invalidated
						B = None
						C = None
						D = None
						#break#pattern is invalidated
					
					elif self.extension(candle_stream[A][csf.low],candle_stream[B][csf.high],candle[csf.high]) > 2.24:
						D = index
						return XABCD(HarmonicDirection.BEARISH,X,A,B,C,D) #return as soon as we identity D 		
		
					
		return XABCD(HarmonicDirection.VOID,X,A,B,C,D)


class DeepCrab(HarmonicPattern):
	
	def _get_abcd(self,start_point,candle_stream, candle_stream_index):
		#assume start_point is a minimum
		end_index = min(start_point.index+self.memory_window,candle_stream_index)
		Found = False
		X = start_point.index
		A = None #high candle
		B = None #low candle#store the candles that we find when checking this window
		C = None #new high candle
		D = None #new low candle
		
		if start_point.type == ExtremityType.MINIMUM: #looking for bullish harmonics
			
			for i,candle in enumerate(candle_stream[start_point.index:end_index+1]):
				if i == 0:
					continue
				index = i + start_point.index
				
				#finding A
				if A is None or (candle[csf.high] > candle_stream[A][csf.high] and B is None): 
					A = index  
					B = None
					C = None
				
				#finding B
				elif A is not None and self.retracement(candle_stream[X][csf.low],candle_stream[A][csf.high],candle[csf.low]) > 0.886 and C is None:
					if B is None or candle[csf.low] < candle_stream[B][csf.low]:
						B = index
					
					if self.retracement(candle_stream[X][csf.low],candle_stream[A][csf.high],candle[csf.low]) > 1.0: #pattern is off if the market closes after this value
						#A = None #pattern is invalidated
						B = None
						C = None
						#break
				
				#finding C
				elif B is not None and self.retracement(candle_stream[A][csf.high],candle_stream[B][csf.low],candle[csf.high]) > 0.382:  
					if C is None or candle[csf.high] > candle_stream[C][csf.high]:
						C = index
					if self.retracement(candle_stream[A][csf.high],candle_stream[B][csf.low],candle[csf.high]) > 0.886: #check! if close or high (allowed to touch?) 
						#A = None #pattern is invalidated
						B = None
						C = None
						#break
				
				#finding D
				elif C is not None and self.retracement(candle_stream[X][csf.low],candle_stream[A][csf.high],candle[csf.low]) > 1.618:
															
					if self.extension(candle_stream[A][csf.high],candle_stream[B][csf.low],candle[csf.low]) > 3.618:
						#A = None #pattern is invalidated
						B = None
						C = None
						D = None
						#break#pattern is invalidated
					
					elif self.extension(candle_stream[A][csf.high],candle_stream[B][csf.low],candle[csf.low]) > 2.24:
						D = index
						return XABCD(HarmonicDirection.BULLISH,X,A,B,C,D) #return as soon as we identity D 		
		
		
		if start_point.type == ExtremityType.MAXIMUM: #looking for bearish bat harmonics
			
			for i,candle in enumerate(candle_stream[start_point.index:end_index+1]):
				if i == 0:
					continue
				index = i + start_point.index
				
				#finding A
				if A is None or (candle[csf.low] < candle_stream[A][csf.low] and B is None): 
					A = index  
					B = None
					C = None
				
				#finding B
				elif A is not None and self.retracement(candle_stream[X][csf.high],candle_stream[A][csf.low],candle[csf.high]) > 0.886 and C is None:
					if B is None or candle[csf.high] > candle_stream[B][csf.high]:
						B = index
					
					if self.retracement(candle_stream[X][csf.high],candle_stream[A][csf.low],candle[csf.high]) > 1.0: #pattern is off if the market closes after this value
						#A = None #pattern is invalidated
						B = None
						C = None
						#break
				
				#finding C
				elif B is not None and self.retracement(candle_stream[A][csf.low],candle_stream[B][csf.high],candle[csf.low]) > 0.382:  
					if C is None or candle[csf.low] < candle_stream[C][csf.low]:
						C = index
					if self.retracement(candle_stream[A][csf.low],candle_stream[B][csf.high],candle[csf.close]) > 0.886: #check! if close or low (allowed to touch?) 
						#A = None #pattern is invalidated
						B = None
						C = None
						#break
				
				#finding D
				elif C is not None and self.retracement(candle_stream[X][csf.high],candle_stream[A][csf.low],candle[csf.high]) > 1.618:
															
					if self.extension(candle_stream[A][csf.low],candle_stream[B][csf.high],candle[csf.high]) > 3.618:
						#A = None #pattern is invalidated
						B = None
						C = None
						D = None
						#break#pattern is invalidated
					
					elif self.extension(candle_stream[A][csf.low],candle_stream[B][csf.high],candle[csf.high]) > 2.24:
						D = index
						return XABCD(HarmonicDirection.BEARISH,X,A,B,C,D) #return as soon as we identity D 		
		
					
		return XABCD(HarmonicDirection.VOID,X,A,B,C,D)
	

class Cypher(HarmonicPattern):
	
	#use state machine 
	def _get_abcd(self,start_point,candle_stream, candle_stream_index):
		#assume start_point is a minimum
		end_index = min(start_point.index+self.memory_window,candle_stream_index)
		Found = False
		X = start_point.index
		A = None #high candle
		B = None #low candle#store the candles that we find when checking this window
		C = None #new high candle
		D = None #new low candle
		
		if start_point.type == ExtremityType.MINIMUM: #looking for bullish harmonics
			for i,candle in enumerate(candle_stream[start_point.index:end_index+1]):
				if i == 0:
					continue
				index = i + start_point.index
				
				#finding A
				if A is None or (candle[csf.high] > candle_stream[A][csf.high] and B is None): 
					A = index  
					B = None
					C = None
				
				#finding B
				elif A is not None and self.retracement(candle_stream[X][csf.low],candle_stream[A][csf.high],candle[csf.low]) > 0.382 and C is None:
					if B is None or candle[csf.low] < candle_stream[B][csf.low]:
						B = index
					if self.retracement(candle_stream[X][csf.low],candle_stream[A][csf.high],candle[csf.close]) > 0.618: #pattern is off if the market closes after this value
						A = None #pattern is invalidated
						B = None
						C = None
						break
				
				#finding C
				elif B is not None and self.extension(candle_stream[X][csf.low],candle_stream[A][csf.high],candle[csf.high]) > 1.272:  #usually 1.128 but 1.272 works better
					if C is None or candle[csf.high] > candle_stream[C][csf.high]:
						C = index
					if self.extension(candle_stream[X][csf.low],candle_stream[A][csf.high],candle[csf.close]) > 1.414: #check! if close or high (allowed to touch?) 
						A = None #pattern is invalidated
						B = None
						C = None
						break
				
				#finding D
				elif C is not None and self.retracement(candle_stream[X][csf.low],candle_stream[C][csf.high],candle[csf.low]) > 0.786:
					D = index
					
					if self.retracement(candle_stream[X][csf.low],candle_stream[C][csf.high],candle_stream[B][csf.low]) > 0.786:
						A = None #pattern is invalidated
						B = None
						C = None
						break
						
					return XABCD(HarmonicDirection.BULLISH,X,A,B,C,D) #return as soon as we identity D 
		
		if start_point.type == ExtremityType.MAXIMUM: #looking for bearish harmonics
			for i,candle in enumerate(candle_stream[start_point.index:end_index+1]):
				if i == 0:
					continue 
					
				index = i + start_point.index
				
				#finding A
				if A is None or (candle[csf.low] < candle_stream[A][csf.low] and B is None): 
					A = index  
					B = None
					C = None
				
				#finding B
				elif A is not None and self.retracement(candle_stream[X][csf.high],candle_stream[A][csf.low],candle[csf.high]) > 0.382 and C is None:
					if B is None or candle[csf.high] > candle_stream[B][csf.high]:
						B = index
					if self.retracement(candle_stream[X][csf.high],candle_stream[A][csf.low],candle[csf.close]) > 0.618: #pattern is off if the market closes after this value
						A = None #pattern is invalidated
						B = None
						C = None
						break
				
				#finding C
				elif B is not None and self.extension(candle_stream[X][csf.high],candle_stream[A][csf.low],candle[csf.low]) > 1.272: #usually 1.128 but 1.272 works better#usually 1.128 but 1.272 works better
					if C is None or candle[csf.low] > candle_stream[C][csf.low]:
						C = index
					if self.extension(candle_stream[X][csf.high],candle_stream[A][csf.low],candle[csf.close]) > 1.414: #check if close or low (allowed to touch?)
						A = None #pattern is invalidated
						B = None
						C = None
						break
				
				#finding D
				elif C is not None and self.retracement(candle_stream[X][csf.high],candle_stream[C][csf.low],candle[csf.high]) > 0.786:
					D = index
					
					if self.retracement(candle_stream[X][csf.high],candle_stream[C][csf.low],candle_stream[B][csf.high]) > 0.786:
						A = None #pattern is invalidated
						B = None
						C = None
						break
						
					return XABCD(HarmonicDirection.BEARISH,X,A,B,C,D) #return as soon as we identity D
					
		return XABCD(HarmonicDirection.VOID,X,A,B,C,D)


##if we need more harmonic patterns then we can implement these. Otherwise lets move onto something else!
class Shark(HarmonicPattern):
	def __init__(self):
		raise NotImplementedError('This pattern has not been implemented')

class ABCD(HarmonicPattern):
	def __init__(self):
		raise NotImplementedError('This pattern has not been implemented')
















from collections import namedtuple
from enum import Enum




import pdb

import charting.candle_stick_functions as csf
from charting.chart_pattern import *
import charting.chart_viewer as chv

#tuple for holding indexs of harmonic patterns 
XABCD = namedtuple('XABCD','direction x a b c d')

class HarmonicDirection(Enum):
	BEARISH = -1
	VOID = 0
	BULLISH = 1

#for own confirmations
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
	
	@staticmethod
	def retracement(value1,value2,the_value):
		return ((the_value - value2) / (value1 - value2)) if value1 != value2 else 0
	
	@staticmethod
	def extension(value1,value2,the_value):  
		return ((the_value - value1) / (value2 - value1)) if value1 != value2 else 0
	
	def get_xabcd(self,candle_stream,candle_stream_index):
		extremes = self._get_extremes(candle_stream_index)
		for e in reversed(extremes):
			xabcd = self._get_abcd(e,candle_stream,candle_stream_index)
			if xabcd.direction != HarmonicDirection.VOID:
				return xabcd
		return XABCD(HarmonicDirection.VOID,None,None,None,None,None)

	def _determine(self,candle_stream_index,candle_stream):
		#C->D >= A->B and 
		xabcd = self.get_xabcd(candle_stream,candle_stream_index)
		
		if xabcd.direction == HarmonicDirection.BULLISH:
			if xabcd.d == candle_stream_index:
				return 1
		if xabcd.direction == HarmonicDirection.BEARISH:
			if xabcd.d == candle_stream_index:
				return -1
		
		return 0
	
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


class Crab(HarmonicPattern):
	pass

class ABCD(HarmonicPattern):
	pass
	
class Butterfly(HarmonicPattern):
	pass
	
class Gartley(HarmonicPattern):
	pass
	

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
						A = None #pattern is invalidated
						B = None
						C = None
						break
				
				#finding C
				elif B is not None and self.retracement(candle_stream[A][csf.high],candle_stream[B][csf.low],candle[csf.high]) > 0.382:  
					if C is None or candle[csf.high] > candle_stream[C][csf.high]:
						C = index
					if self.retracement(candle_stream[A][csf.low],candle_stream[B][csf.high],candle[csf.high]) > 0.886: #check! if close or high (allowed to touch?) 
						A = None #pattern is invalidated
						B = None
						C = None
						break
				
				#finding D
				elif C is not None and self.retracement(candle_stream[X][csf.low],candle_stream[A][csf.high],candle[csf.low]) > 0.886:
															
					if self.extension(candle_stream[A][csf.high],candle_stream[B][csf.low],candle[csf.low]) > 2.618:
						A = None #pattern is invalidated
						B = None
						C = None
						D = None
						break#pattern is invalidated
					
					if self.extension(candle_stream[A][csf.high],candle_stream[B][csf.low],candle[csf.low]) > 1.618:
						D = index
						return XABCD(HarmonicDirection.BULLISH,X,A,B,C,D) #return as soon as we identity D 		
		
		
					
		return XABCD(HarmonicDirection.VOID,X,A,B,C,D)

class DeepCrab(HarmonicPattern):
	pass
	
class Shark(HarmonicPattern):
	pass


















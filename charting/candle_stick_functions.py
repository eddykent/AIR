


open = 0
high = 1
low = 2
close = 3
the_date_col = -1 #date is always at the end of the candle

def bullish(candle):
	return candle[open] < candle[close]

def bearish(candle):
	return candle[open] > candle[close]
	
def body(candle):
	return abs(candle[open] - candle[close])

def body_bottom(candle):
	if bearish(candle):
		return candle[close]
	if bullish(candle):
		return candle[open]
	return candle[open]

def body_top(candle):	
	if bearish(candle):
		return candle[open]
	if bullish(candle):
		return candle[close]
	return candle[open] 

def range(candle):
	return candle[high] - candle[low]

def median(candle):	
	return (candle[high] - candle[low])*0.5 + candle[low]


def doji(candle,doji_body=0.1):   #is the body of the candle small enough to make this a doji?
	candle_body = body(candle)
	shadow = range(candle)
	return candle_body  < shadow * doji_body

def fat(candle,tolerance=0.1):  #is the body larger than the wick lengths? 
	candle_body = body(candle)
	return candle_body  > (upper_wick(candle) + lower_wick(candle)) / (tolerance+1.0)
	

def upper_wick(candle):
	return candle[high] - max(candle[open],candle[close])

def lower_wick(candle):
	return min(candle[open],candle[close]) - candle[low]
	
#def ballanced_wicks(candle,tolerance=0.1):
#	hw = upper_wick(candle)
#	lw = lower_wick(candle)
#	return abs(hw - lw) < (hw + lw) * tolerance

def ballanced_wicks(candle,tolerance=0.1):
	hw = upper_wick(candle)
	lw = lower_wick(candle)
	return abs(hw - lw) < (hw + lw) * tolerance

def top_heavy(candle,wick_len=2):
	return upper_wick(candle) < body(candle) and body(candle) * wick_len < lower_wick(candle)

def bottom_heavy(candle,wick_len=2):
	return lower_wick(candle) < body(candle) and body(candle) * wick_len < upper_wick(candle)


#the following functions are more like candle stick patterns - they operate on a list of candles
def engulf(candles,difference=1.1):
	if len(candles) > 1:
		candle1,candle2 = candles[-2:]
		body1 = body(candle1)
		body2 = body(candle2)
		return body2 > difference*body1 # 10% larger or more
	return False

def reduce(candles,difference=1.1):
	if len(candles) > 1:
		body1 = body(candles[-2])
		body2 = body(candles[-1])
		return body2*difference < body1  # 10% smaller or more
	return False

def grow(candles,difference=1.1):
	if len(candles) > 1:
		candle1 = candles[-2]
		candle2 = candles[-1]
		return engulf(candle1,candle2,difference) and candle1[high] <= candle2[high] and candle1[low] >= candle2[low]
	return False

def shrink(candle1,candle2,difference=1.1):
	if len(candles) > 1:
		candle1 = candles[-2]
		candle2 = candles[-1]
		return reduce(candle1,candle2,difference) and candle1[high] >= candle2[high] and candle1[low] <= candle2[low]
	return False

#step = candle close is higher 
def step_up(candles):
	if len(candles) > 1:
		candle1 = candles[-2]
		candle2 = candles[-1]
		return candle2[close] > candle1[close]
	return False

#candle close is lower
def step_down(candles):
	if len(candles) > 1:
		candle1 = candles[-2]
		candle2 = candles[-1]
		return candle2[close] < candle2[close]
	return False
	
#candle open  is higher than previous candle close and both candles are bullish
def hop_up(candles):
	if len(candles) > 1:
		candle1 = candles[-2]
		candle2 = candles[-1]
		return candle2[open] >= candle1[close] and bullish(candle1) and bullish(candle2)
	return False

def hop_down(candles):
	if len(candles) > 1:
		candle1 = candles[-2]
		candle2 = candles[-1]
		return candle2[open] <= candle1[close] and bearish(candle1) and bearish(candle2)
	return False

#candle open is higher than previous candle high - this probably doesnt happen often!
def leap_up(candles):
	if len(candles) > 1:
		candle1 = candles[-2]
		candle2 = candles[-1]
		return candle2[open] > candle1[high]
	return False

def leap_down(candles):
	if len(candles) > 1:
		candle1 = candles[-2]
		candle2 = candles[-1]
		return candle2[open] < candle1[low]
	return False
	
#candle low is higher than previous candle high - probably never happens!
def jump_up(candles):
	if len(candles) > 1:
		candle1 = candles[-2]
		candle2 = candles[-1]
		return candle2[low] > candle1[high]
	return False
	
def jump_down(candles):
	if len(candles) > 1:
		candle1 = candles[-2]
		candle2 = candles[-1]
		return candle2[high] < candle1[low]
	return False
	
def merge(candles):
	high1 = max([c[high] for c in candles])
	low1 = min([c[low] for c in candles])
	return [candles[0][open],high1,low1,candles[-1][close]] + candles[0][4:] #add date

def lower_lows(candles):
	return all(candle1[low] > candle2[low] for candle1,candle2 in zip(candles[:-1],candles[1:]))

def higher_highs(candles):
	return all(candle1[high] < candle2[high] for candle1,candle2 in zip(candles[:-1],candles[1:]))
	
def lower_highs(candles):
	return all(candle1[high] > candle2[high] for candle1,candle2 in zip(candles[:-1],candles[1:]))

def higher_lows(candles):
	return all(candle1[low] < candle2[low] for candle1,candle2 in zip(candles[:-1],candles[1:]))

def momentum_gain(candles):
	return all(body(candle1) < body(candle2) for candle1,candle2 in zip(candles[:-1],candles[1:]))

def momentum_loss(candles):
	return all(body(candle1) > body(candle2) for candle1,candle2 in zip(candles[:-1],candles[1:]))

#get the candle that achieves the lowest value (lower wick?)
def lowest(candles):
	return min(candle[low] for candle in candles)
	
def highest(candles):
	return max(candle[high] for candle in candles)

def index_highest(candles):
	_high = highest(candles)
	for index in range(len(candles)):
		if candles[index][high] == _high:
			return index
	return -1

def index_lowest(candles):
	_low = lowest(candles)
	for index in range(len(candles)):
		if candles[index][low] == _low:
			return index
	return -1	
	
def lowest_body(candles):
	return min(body_bottom(candle) for candle in candles)
	
def highest_body(candles):
	return max(body_top(candle) for candle in candles)
	
def resting_above(candle,value,gap):
	return body_bottom(candle) > value and body_bottom(candle) < value - gap
	
def hanging_below(candle,value,gap):
	return body_top(candle) < value and body_top(candle) > value - gap

def distance(candle,value):
	if candle[low] <= value and value <= candle[high]:
		return 0 
	if candle[low] > value:
		return candle[low] - value
	if candle[high] < value:
		return value - candle[high]
	return -1

def body_distance(candle,value):
	if body_bottom(candle) <= value and value <= body_top(candle):
		return 0 
	if body_bottom(candle) > value:
		return body_bottom(candle) - value
	if body_top(candle) < value:
		return value - body_top(candle)
	return -1

range_distance = distance



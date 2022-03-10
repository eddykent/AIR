
import numpy as np

open = 0
high = 1
low = 2
close = 3
date_column = -1 #date is always at the end of the candle

def bullish(candle):
	return candle[:,open] < candle[:,close]

def bearish(candle):
	return candle[:,open] >= candle[:,close]
	
def body(candle):
	return np.abs(candle[:,open] - candle[:,close])

def body_bottom(candle):
	return_candle = np.zeros(candle.shape[0])
	bullish_candles = bullish(candle)
	bearish_candles = bearish(candle)
	return_candle[bullish_candles] = candle[bullish_candles,open]
	return_candle[bearish_candles] = candle[bearish_candles,close]
	return return_candle

def body_top(candle):	
	return_candle = np.zeros(candle.shape[0])
	bullish_candles = bullish(candle)
	bearish_candles = bearish(candle)
	return_candle[bullish_candles] = candle[bullish_candles,close]
	return_candle[bearish_candles] = candle[bearish_candles,open]
	return return_candle

def range(candle):
	return candle[:,high] - candle[:,low]

def median(candle):	
	return (candle[:,high] - candle[:,low])*0.5 + candle[:,low]

def typical(candle):
	return (candle[:,high] + candle[:,low] + candle[:,close]) / 3.0

def mean(candle):
	return np.sum(candle,axis=1) / 4.0

def doji(candle,doji_body=0.1):   #is the body of the candle small enough to make this a doji?
	candle_body = body(candle)
	shadow = range(candle)
	return candle_body  < (shadow * doji_body)

def fat(candle,tolerance=0.1):  #is the body larger than the wick lengths? 
	candle_body = body(candle)
	return candle_body  > ((upper_wick(candle) + lower_wick(candle)) / (tolerance+1.0))
	

def upper_wick(candle):
	return candle[:,high] - np.maximum(candle[:,open],candle[:,close])

def lower_wick(candle):
	return np.minimum(candle[:,open],candle[:,close]) - candle[:,low]
	

def ballanced_wicks(candle,tolerance=0.1):
	hw = upper_wick(candle)
	lw = lower_wick(candle)
	return np.abs(hw - lw) < ((hw + lw) * tolerance)

def top_heavy(candle,wick_len=2):
	return (upper_wick(candle) < body(candle)) & ((body(candle) * wick_len) < lower_wick(candle))

def bottom_heavy(candle,wick_len=2):
	return (lower_wick(candle) < body(candle)) & ((body(candle) * wick_len) < upper_wick(candle))

#for the following functions, value should be an np.array of same length as candle
def resting_above(candle,value,gap):
	return (body_bottom(candle) > value) & (body_bottom(candle) < (value - gap))
	
def hanging_below(candle,value,gap):
	return (body_top(candle) < value) & (body_top(candle) > (value - gap))

def distance(candle,value):
	return_candle = np.zeros(candle.shape[0])
	above = candle[:,high] < value
	below = candle[:,low] > value
	return_candle[above] = (value - candle[:,high])[above]
	return_candle[below] = (candle[:,low] - value )[below]
	return return_candle
	
def body_distance(candle,value):
	return_candle = np.zeros(candle.shape[0])
	bottom = body_bottom(candle)
	top = body_top(candle)
	
	below = bottom > value
	above = top < value
	return_candle[below] = (body_bottom(candle) - value)[below]
	return_candle[above] = (value-body_top(candle))[above]
	return return_candle


#the following operate on a pair of candles - these are indexed before they are put in here 
def engulf(candle1,candle2,difference=1.1):
	body1 = body(candle1)
	body2 = body(candle2)
	return body2 > (difference*body1) # 10% larger or more


def reduce(candle1,candle2,difference=1.1):
	body1 = body(candle1)
	body2 = body(candle2)
	return (body2*difference) < body1  # 10% smaller or more

def grow(candle1,candle2,difference=1.1):
	return engulf(candle1,candle2,difference) & (candle1[:,high] <= candle2[:,high]) & (candle1[:,low] >= candle2[:,low])

def shrink(candle1,candle2,difference=1.1):
	return reduce(candle1,candle2,difference) & (candle1[:,high] >= candle2[:,high]) & (candle1[:,low] <= candle2[:,low])

#step = candle close is higher 
def step_up(candle1,candle2):
	return candle2[:,close] > candle1[:,close]

#candle close is lower
def step_down(candle1,candle2):
	return candle2[:,close] < candle1[:,close]

	
#candle open  is higher than previous candle close and both candles are bullish
def hop_up(candle1,candle2):
	return (candle2[:,open] >= candle1[:,close]) & bullish(candle1) & bullish(candle2)

def hop_down(candle1,candle2):
	return candle2[:,open] <= candle1[:,close] and bearish(candle1) and bearish(candle2)


#candle open is higher than previous candle high - this probably doesnt happen often!
def leap_up(candle1,candle2):
	return candle2[:,open] > candle1[:,high]


def leap_down(candle1,candle2):
	return candle2[:,open] < candle1[:,low]

	
#candle low is higher than previous candle high - probably never happens!
def jump_up(candle1,candle2):
	return candle2[:,low] > candle1[:,high]
	
def jump_down(candle1,candle2):
	return candle2[:,high] < candle1[:,low]


#array-like functions 	
def merge(candles):
	high = np.max(candles[:,:,high],axis=1)
	low = np.min(candles[:,:,low],axis=1)
	open = candles[:,0,open]
	close = candles[:,-1,close]
	return  np.concatenate([open,high,low,close],axis=1)#+ candles[0][4:] #add date?

def lower_lows(candles):
	prev_lows = candles[:,:-1,low]
	next_lows = candles[:,1:,low]
	return np.all(prev_lows > next_lows, axis=1)
	#return all(candle1[low] > candle2[low] for candle1,candle2 in zip(candles[:-1],candles[1:]))

def higher_highs(candles):
	prev_highs = candles[:,:-1,high]
	next_highs = candles[:,1:,high]
	return np.all(prev_highs < next_highs, axis=1)
	
def lower_highs(candles):
	prev_highs = candles[:,:-1,high]
	next_highs = candles[:,1:,high]
	return np.all(prev_highs > next_highs, axis=1)

def higher_lows(candles):
	prev_lows = candles[:,:-1,low]
	next_lows = candles[:,1:,low]
	return np.all(prev_lows < next_lows, axis=1)

def momentum_gain(candles):
	prev_opens = candles[:,:-1,open]
	prev_closes = candles[:,:-1,close]
	next_opens = candles[:,1:,open]
	next_closes = candles[:,1:,close]
	prev_bodys = np.abs(prev_opens - prev_closes)
	next_bodys = np.abs(next_opens - next_closes)
	return np.all(prev_bodys < next_bodys,axis=1)

def momentum_loss(candles):
	prev_opens = candles[:,:-1,open]
	prev_closes = candles[:,:-1,close]
	next_opens = candles[:,1:,open]
	next_closes = candles[:,1:,close]
	prev_bodys = np.abs(prev_opens - prev_closes)
	next_bodys = np.abs(next_opens - next_closes)
	return np.all(prev_bodys > next_bodys,axis=1)

#get the candle that achieves the lowest value (lower wick?)
def lowest(candles):
	return np.min(candles[:,:,low],axis=1)
	
def highest(candles):
	return np.max(candles[:,:,high],axis=1)

def index_lowest(candles):
	return np.argmin(candles[:,:,low],axis=1)

def index_highest(candles):
	return np.argmax(candles[:,:,high],axis=1)


def lowest_body(candles):
	opens = candles[:,:,open]
	closes = candles[:,:,close]
	low_body = np.minimum([opens,closes])
	return np.min(low_body,axis=1)

	
def highest_body(candles):
	opens = candles[:,:,open]
	closes = candles[:,:,close]
	high_body = np.maximum([opens,closes])
	return np.max(high_body,axis=1)


range_distance = distance























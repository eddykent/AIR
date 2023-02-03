
#this file just contains a bunch of lists that are used in ther iterative search algorithms 
#to find best setups based on combinations of indicators (and charts, and own novel stuff) 


import numpy as np 

from strategies.setup_search import TriggerBlock, SetupBlock
from charting import candle_stick_functions as csf

from setups.setup_tools import CandleDataTool, PipStop, ATRStop
from utils import ListFileReader, Database

from indicators.reversal import RSI 
from indicators.moving_average import EMA
from indicators.currency import CurrencyWrapper

from charting.match_pattern import MatchPattern
from setups.collected_setups import Harmony, Trends, Shapes


lfr = ListFileReader()
currencies = lfr.read('fx_pairs/currencies.txt')
fx_pairs = lfr.read('fx_pairs/fx_mains.txt')

def default_bullish(res, npc):
	return res[:,:,0] > 0
	
def default_bearish(res,npc):
	return res[:,:,0] < 0

def ma_bullish(res, npc):
	return npc[:,:,csf.low] > res[:,:,0]

def ma_bearish(res, npc):
	return npc[:,:,csf.high] < res[:,:,0]

def ma_bullish_close(res, npc):
	return npc[:,:,csf.close] > res[:,:,0]

def ma_bearish_close(res, npc):
	return npc[:,:,csf.close] < res[:,:,0]

def oscillator_reversal_bullish(low=0.3):	
	def ocb(res,npc):	
		return res[:,:,0] < low
	return ocb

def oscillator_reversal_bearish(high=0.7):	
	def ocb(res,npc):	
		return res[:,:,0] > high
	return ocb

#ideal for testing only - probably want a more exhaustive list for real deal 
def small_set(anything=None):
	return [
		#emas
		TriggerBlock(EMA(200), lambda res, npc : npc[:,:,csf.low] > res[:,:,0], lambda res, npc : npc[:,:,csf.high] < res[:,:,0], 'full clearance'),
		TriggerBlock(EMA(100), lambda res, npc : npc[:,:,csf.close] > res[:,:,0], lambda res, npc : npc[:,:,csf.close] < res[:,:,0], 'clearence close only'),
		TriggerBlock(EMA(50), lambda res, npc : npc[:,:,csf.close] > res[:,:,0], lambda res, npc : npc[:,:,csf.close] < res[:,:,0], 'clearence close only'),
		TriggerBlock(EMA(15), lambda res, npc : npc[:,:,csf.close] > res[:,:,0], lambda res, npc : npc[:,:,csf.close] < res[:,:,0], 'clearence close only'),
		
		#stengths
		TriggerBlock(RSI(20), oscillator_reversal_bullish(0.2), oscillator_reversal_bearish(0.8), '0.2 and 0.8'),
		TriggerBlock(RSI(14),oscillator_reversal_bullish(0.2), oscillator_reversal_bearish(0.8), '0.2 and 0.8'),
		TriggerBlock(RSI(9), oscillator_reversal_bullish(0.2), oscillator_reversal_bearish(0.8), '0.2 and 0.8'),
		TriggerBlock(RSI(5), oscillator_reversal_bullish(0.2), oscillator_reversal_bearish(0.8), '0.2 and 0.8'),
		
		#currency metrics
		TriggerBlock(CurrencyWrapper(RSI(14),fx_pairs,currencies), lambda res, npc : (npc[:,:,0] > 0.65) & (npc[:,:,1] < 0.35), lambda res,npc : (npc[:,:,1] > 0.65) & (npc[:,:,0] < 0.35), '.35 .65 activation'),
		TriggerBlock(CurrencyWrapper(RSI(9),fx_pairs,currencies), lambda res, npc : (npc[:,:,0] > 0.65) & (npc[:,:,1] < 0.35), lambda res,npc : (npc[:,:,1] > 0.65) & (npc[:,:,0] < 0.35), '.35 .65 activation'),
		TriggerBlock(CurrencyWrapper(RSI(14),fx_pairs,currencies), lambda res, npc : (npc[:,:,0] > npc[:,:,1]), lambda res,npc : (npc[:,:,1] > npc[:,:,0]), 'x/y x>y activation'),
		TriggerBlock(CurrencyWrapper(RSI(9),fx_pairs,currencies), lambda res, npc : (npc[:,:,0] > npc[:,:,1]), lambda res,npc : (npc[:,:,1] > npc[:,:,0]), 'x/y x>y activation'),
	 
		#TriggerBlock(MACD(), lambda res, npc : #unsure how this will work yet with crossover activation
		
		
	]

def good_set(trade_signalling_data):
	#match_pattern = MatchPattern()
	#match_pattern.set_haystack(trade_signalling_data.np_candles)
	return [
		#emas
		TriggerBlock(EMA(200), lambda res, npc : npc[:,:,csf.low] > res[:,:,0], lambda res, npc : npc[:,:,csf.high] < res[:,:,0], 'full clearance'),
		TriggerBlock(EMA(100), lambda res, npc : npc[:,:,csf.close] > res[:,:,0], lambda res, npc : npc[:,:,csf.close] < res[:,:,0], 'clearence close only'),
		TriggerBlock(EMA(50), lambda res, npc : npc[:,:,csf.close] > res[:,:,0], lambda res, npc : npc[:,:,csf.close] < res[:,:,0], 'clearence close only'),
		
		#stengths
		TriggerBlock(RSI(20), lambda res, npc : res[:,:,0] < 0.2, lambda res, npc : res[:,:,0] > 0.8, '0.2 and 0.8'),
		TriggerBlock(RSI(14), lambda res, npc : res[:,:,0] < 0.2, lambda res, npc : res[:,:,0] > 0.8, '0.2 and 0.8'),
		TriggerBlock(RSI(5), lambda res, npc : res[:,:,0] < 0.2, lambda res, npc : res[:,:,0] > 0.8, '0.2 and 0.8'),
		
		#currency metrics
		TriggerBlock(CurrencyWrapper(RSI(14),fx_pairs,currencies), lambda res, npc : (npc[:,:,0] > 0.6) & (npc[:,:,1] < 0.4), lambda res,npc : (npc[:,:,1] > 0.6) & (npc[:,:,0] < 0.4), '.4 .6 activation'),
		
		#TriggerBlock(CurrencyWrapper(RSI(14),fx_pairs,currencies), lambda res, npc : (npc[:,:,0] > npc[:,:,1]), lambda res,npc : (npc[:,:,1] > npc[:,:,0]), 'x/y x>y activation'),
		TriggerBlock(CurrencyWrapper(RSI(7),fx_pairs,currencies), lambda res, npc : (npc[:,:,0] > npc[:,:,1]), lambda res,npc : (npc[:,:,1] > npc[:,:,0]), 'x/y x>y activation'),
	 
		#TriggerBlock(MACD(), lambda res, npc : #unsure how this will work yet with crossover activation
		
		
		SetupBlock(Harmony(),trade_signalling_data), 
		#SetupBlock(Trends(),trade_signalling_data),
		#SetupBlock(Shapes(),trade_signalling_data),
		
		#matchpatterns require haystack - np_candles? breaks :/
		#TriggerBlock(match_pattern, lambda res, npc : res[:,:,0] > 0, lambda res, npc : res[:,:,0] < 0, 'find matchings')
		
	]

#WMA, TMMA, ChoppyIndex, Fourier, ClientSentiment, 


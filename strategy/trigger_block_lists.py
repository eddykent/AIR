
#this file just contains a bunch of lists that are used in ther iterative search algorithms 
#to find best setups based on combinations of indicators (and charts, and own novel stuff) 


import numpy as np 

from strategy.strategy_components import TriggerBlock, SetupBlock
from charting import candle_stick_functions as csf

from setups.setup_tools import CandleDataTool, PipStop, ATRStop
from utils import ListFileReader, Database

from indicators.reversal import RSI 
from indicators.trend import ADX, CCI, IchimokuCloud
from indicators.moving_average import EMA, TEMA, WMA, ZLMA
from indicators.momentum import MACD
from indicators.currency import CurrencyWrapper
from indicators.volume import ClientSentiment, MoneyFlowIndex, VWAP#fx does not care about daily
from indicators.volatility import ChoppinessIndex, BollingerBands, KeltnerChannel, DonchianChannel
from indicators.mathematic import FourierGradient

from charting.match_pattern import MatchPattern
from charting.chart_pattern import SupportAndResistance, PivotPoints

from setups.collected_setups import Harmony, Trends, Shapes #Triangles


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


#define some islands of instability - when a strat has two or more of these in it should not be calculated
moving_averages = [EMA,VWAP,WMA,TEMA,ZLMA] #no need to put these together in same strats ?
chart_patterns = [SupportAndResistance,PivotPoints]
rsi = [RSI]

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
		
		
	]

def good_set(trade_signalling_data):
	match_pattern = MatchPattern()
	match_pattern.set_haystack(trade_signalling_data.np_candles)
	return [
		#moving averages
		TriggerBlock(EMA(200), lambda res, npc : npc[:,:,csf.low] > res[:,:,0], lambda res, npc : npc[:,:,csf.high] < res[:,:,0], 'full clearance'),
		TriggerBlock(EMA(100), lambda res, npc : npc[:,:,csf.close] > res[:,:,0], lambda res, npc : npc[:,:,csf.close] < res[:,:,0], 'clearence close only'),
		TriggerBlock(EMA(50), lambda res, npc : npc[:,:,csf.close] > res[:,:,0], lambda res, npc : npc[:,:,csf.close] < res[:,:,0], 'clearence close only'),
		TriggerBlock(VWAP(), ma_bullish, ma_bearish, 'full clearance'),
		TriggerBlock(WMA(), ma_bullish, ma_bearish, 'full clearance'),
		TriggerBlock(TEMA(), ma_bullish, ma_bearish, 'full clearance'),
		TriggerBlock(ZLMA(), ma_bullish, ma_bearish, 'full clearance'),
		
		
		#oscillators & reversals 
		TriggerBlock(RSI(20), oscillator_reversal_bullish(0.2), oscillator_reversal_bearish(0.8), '0.2 and 0.8'),
		TriggerBlock(RSI(14), oscillator_reversal_bullish(0.2), oscillator_reversal_bearish(0.8), '0.2 and 0.8'),
		TriggerBlock(RSI(5), oscillator_reversal_bullish(0.2), oscillator_reversal_bearish(0.8), '0.2 and 0.8'),
		TriggerBlock(CCI(), oscillator_reversal_bullish(0.2), oscillator_reversal_bearish(0.8), '0.2 and 0.8'),
		TriggerBlock(MACD(), lambda res, npc : res[:,:,2] > 0, lambda res, npc : res[:,:,2] < 0,'included everything after cross'),#unsure how this will work yet with crossover activation
		TriggerBlock(MoneyFlowIndex(), oscillator_reversal_bullish(0.2), oscillator_reversal_bearish(0.8), '0.2 and 0.8'),		
		
		#custom metrics
		TriggerBlock(CurrencyWrapper(RSI(14),fx_pairs,currencies), lambda res, npc : (npc[:,:,0] > 0.6) & (npc[:,:,1] < 0.4), lambda res,npc : (npc[:,:,1] > 0.6) & (npc[:,:,0] < 0.4), '.4 .6 activation'),
		
		#TriggerBlock(CurrencyWrapper(RSI(14),fx_pairs,currencies), lambda res, npc : (npc[:,:,0] > npc[:,:,1]), lambda res,npc : (npc[:,:,1] > npc[:,:,0]), 'x/y x>y activation'),
		TriggerBlock(CurrencyWrapper(RSI(7),fx_pairs,currencies), lambda res, npc : (npc[:,:,0] > npc[:,:,1]), lambda res,npc : (npc[:,:,1] > npc[:,:,0]), 'x/y x>y activation'),
		TriggerBlock(ClientSentiment(), lambda res, npc : res[:,:,1] > 0.65, lambda res, npc : res[:,:,0] > 0.65, 'when sentiment is higher than 0.65'),
	 
		#TriggerBlock(MACD(), lambda res, npc : #unsure how this will work yet with crossover activation
		
		#harmonic & chart patterns 
		TriggerBlock(SupportAndResistance(), default_bullish, default_bearish),
		TriggerBlock(PivotPoints(trade_signalling_data.timeline), default_bullish, default_bearish),
		SetupBlock(Harmony(),trade_signalling_data), 
		#SetupBlock(Trends(),trade_signalling_data),
		#SetupBlock(Shapes(),trade_signalling_data),
		
		#matchpatterns require haystack - np_candles? breaks :/
		#TriggerBlock(match_pattern, lambda res, npc : res[:,:,0] > 0, lambda res, npc : res[:,:,0] < 0, 'find matchings'),
		TriggerBlock(ADX(), lambda res, npc : res[:,:,0] > 0.25, lambda res, npc : res[:,:,0] > 0.25, 'check trending only'),
		TriggerBlock(ADX(), lambda res, npc : res[:,:,1] > 0.7, lambda res, npc : res[:,:,2] > 0.7, 'check positives and negatives'),
		TriggerBlock(ChoppinessIndex(), lambda res, npc : res[:,:,0] < res[:,:,1], lambda res, npc : res[:,:,0] < res[:,:,1]),
		
		
		#super trend
		#psar
		#aroon
		
		#TriggerBlock(FourierGradient(), ma_bullish, ma_bearish , 'simple ma style')
				
		
	]

#WMA, TMMA, PivotPoints, TrianglePatterns, CandlestickPatterns, BollingerBands, KeltnerChannel, DonchianChannel


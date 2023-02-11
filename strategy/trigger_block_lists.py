
#this file just contains a bunch of lists that are used in ther iterative search algorithms 
#to find best setups based on combinations of indicators (and charts, and own novel stuff) 


import numpy as np 

from strategy.strategy_components import TriggerBlock, SetupBlock, MultiTriggerBlock
from charting import candle_stick_functions as csf

from setups.setup_tools import CandleDataTool, PipStop, ATRStop, DivTool
from utils import ListFileReader, Database

from indicators.reversal import RSI, Stochastic #WilliamsPercentRange, MassIndex
from indicators.trend import ADX, CCI, IchimokuCloud
from indicators.moving_average import EMA, TEMA, WMA, ZLMA
from indicators.momentum import MACD, Accelerator, RVI
from indicators.currency import CurrencyWrapper
from indicators.volume import ClientSentiment, MoneyFlowIndex, VWAP#fx does not care about daily
from indicators.volatility import ChoppinessIndex, BollingerBands, KeltnerChannel, DonchianChannel
from indicators.mathematic import FourierGradient

from charting.match_pattern import MatchPattern
from charting.chart_pattern import SupportAndResistance, PivotPoints
from charting.candle_stick_pattern import PinBar, Engulfing, SoldiersAndCrows, MorningEveningStars, ThreeLineStrikes, Harami

from setups.collected_setups import Harmony, Trends, Shapes, Triangles

csps =  [PinBar, Engulfing, SoldiersAndCrows, MorningEveningStars, ThreeLineStrikes, Harami]

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

def multi_any_not_bullish(res, npc):	
	return np.any(res > 0,axis=2) & ~ np.any(res < 0,axis=2)

def multi_any_not_bearish(res, npc):	
	return np.any(res < 0,axis=2) & ~ np.any(res > 0,axis=2)

def multi_any_bullish(res,npc):
	return np.any(res > 0,axis=2)

def multi_any_bearish(res,npc):
	return np.any(res < 0,axis=2)

div_orders = [3,5,7,11]
div_windows = [20,50,80,100]

def divergences_bullish(res,npc):
	result_arr = np.full(list(res.shape[0:2])+[len(div_orders)],False)
	for i,(win,ord) in enumerate(zip(div_windows,div_orders)):
		div = DivTool(win,ord)
		bullish, bearish = div.markup([res[:,:,0],npc[:,:,csf.close]])#csf.low?
		result_arr[:,:,i] = bullish
	return np.any(result_arr,axis=2)

def divergences_bearish(res,npc):
	result_arr = np.full(list(res.shape[0:2])+[len(div_orders)],False)
	for i,(win,ord) in enumerate(zip(div_windows,div_orders)):
		div = DivTool(win,ord)
		bullish, bearish = div.markup([res[:,:,0],npc[:,:,csf.close]])
		result_arr[:,:,i] = bearish
	return np.any(result_arr,axis=2)

def hidden_divergences_bullish(res,npc):
	result_arr = np.full(list(res.shape[0:2])+[len(div_orders)],False)
	for i,(win,ord) in enumerate(zip(div_windows,div_orders)):
		div = DivTool(win,ord,hidden=True)
		bullish, bearish = div.markup([res[:,:,0],npc[:,:,csf.close]])
		result_arr[:,:,i] = bullish
	return np.any(result_arr,axis=2)
	
def hidden_divergences_bearish(res,npc):
	result_arr = np.full(list(res.shape[0:2])+[len(div_orders)],False)
	for i,(win,ord) in enumerate(zip(div_windows,div_orders)):
		div = DivTool(win,ord,hidden=True)
		bullish, bearish = div.markup([res[:,:,0],npc[:,:,csf.close]])
		result_arr[:,:,i] = bearish
	return np.any(result_arr,axis=2)


def stoch_bullish(res,npc): #slow
	return (res[:,:,1] > res[:,:,2]) & (res[:,:,1] < res[:,:,4])
	
def stoch_bearish(res,npc):
	return (res[:,:,1] < res[:,:,2]) & (res[:,:,1] > res[:,:,3])

#define some islands of instability - when a strat has two or more of these in it should not be calculated
moving_averages = [EMA,VWAP,WMA,TEMA,ZLMA] #no need to put these together in same strats ?
chart_patterns = [SupportAndResistance,PivotPoints] #triangles? 
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
	#match_pattern = MatchPattern()
	#match_pattern.set_haystack(trade_signalling_data.np_candles)
	return [
		#moving averages
		TriggerBlock(EMA(200), lambda res, npc : npc[:,:,csf.low] > res[:,:,0], lambda res, npc : npc[:,:,csf.high] < res[:,:,0], 'full clearance'),
		TriggerBlock(EMA(100), lambda res, npc : npc[:,:,csf.close] > res[:,:,0], lambda res, npc : npc[:,:,csf.close] < res[:,:,0], 'clearence close only'),
		TriggerBlock(EMA(50), lambda res, npc : npc[:,:,csf.close] > res[:,:,0], lambda res, npc : npc[:,:,csf.close] < res[:,:,0], 'clearence close only'),
		TriggerBlock(VWAP(), ma_bullish, ma_bearish, 'full clearance'),
		TriggerBlock(WMA(), ma_bullish, ma_bearish, 'full clearance'),
		TriggerBlock(TEMA(), ma_bullish, ma_bearish, 'full clearance'),
		TriggerBlock(ZLMA(), ma_bullish, ma_bearish, 'full clearance'),
		
		
		#harmonic & chart patterns 
		TriggerBlock(SupportAndResistance(), default_bullish, default_bearish),
		TriggerBlock(PivotPoints(trade_signalling_data.timeline), default_bullish, default_bearish),
		SetupBlock(Harmony(),trade_signalling_data), 
		#SetupBlock(Triangles(),trade_signalling_data),
		#SetupBlock(Shapes(),trade_signalling_data),
		MultiTriggerBlock([csp() for csp in csps], multi_any_bullish, multi_any_bearish, 'candle stick patterns'),
		
		#some common divergences - could also use Stochastic or Awesome
		TriggerBlock(RSI(14),divergences_bullish, divergences_bearish,'divergence'), 
		#TriggerBlock(RSI(14),hidden_divergences_bullish, hidden_divergences_bearish,'hidden divergence'), 
		#TriggerBlock(MACD(),divergences_bullish, divergences_bearish,'divergence'), 
		#TriggerBlock(MACD(),hidden_divergences_bullish, hidden_divergences_bearish,'hidden divergence'), 
		
		#oscillators & reversals 
		TriggerBlock(RSI(20), oscillator_reversal_bullish(0.2), oscillator_reversal_bearish(0.8), '0.2 and 0.8'),
		TriggerBlock(RSI(14), oscillator_reversal_bullish(0.2), oscillator_reversal_bearish(0.8), '0.2 and 0.8'),
		TriggerBlock(RSI(5), oscillator_reversal_bullish(0.2), oscillator_reversal_bearish(0.8), '0.2 and 0.8'),
		TriggerBlock(CCI(), oscillator_reversal_bullish(0.2), oscillator_reversal_bearish(0.8), '0.2 and 0.8'),
		TriggerBlock(MACD(), lambda res, npc : (res[:,:,2] > 0) & (res[:,:,0] < 0), lambda res, npc : (res[:,:,2] < 0) & (res[:,:,0] > 0),'included everything after cross, but macd below 0 for buy'),
		TriggerBlock(MoneyFlowIndex(), oscillator_reversal_bullish(0.2), oscillator_reversal_bearish(0.8), '0.2 and 0.8'),		
		TriggerBlock(Accelerator(), lambda res, npc : res[:,:,0] > 0, lambda res, npc : res[:,:,0] < 0,'zero line based'), 
		TriggerBlock(RVI(), lambda res,npc : res[:,:,0] > res[:,:,1], lambda res,npc : res[:,:,0] < res[:,:,1], 'signal cross'),
		TriggerBlock(Stochastic(), stoch_bullish, stoch_bearish, 'checks overbought/sold and crossover (slow)'), 
		
		#custom metrics
		TriggerBlock(CurrencyWrapper(RSI(14),fx_pairs,currencies), lambda res, npc : (npc[:,:,0] > 0.6) & (npc[:,:,1] < 0.4), lambda res,npc : (npc[:,:,1] > 0.6) & (npc[:,:,0] < 0.4), '.4 .6 activation'),
		
		#TriggerBlock(CurrencyWrapper(RSI(14),fx_pairs,currencies), lambda res, npc : (npc[:,:,0] > npc[:,:,1]), lambda res,npc : (npc[:,:,1] > npc[:,:,0]), 'x/y x>y activation'),
		TriggerBlock(CurrencyWrapper(RSI(7),fx_pairs,currencies), lambda res, npc : (npc[:,:,0] > npc[:,:,1]), lambda res,npc : (npc[:,:,1] > npc[:,:,0]), 'x/y x>y activation'),
		TriggerBlock(ClientSentiment(), lambda res, npc : res[:,:,1] > 0.65, lambda res, npc : res[:,:,0] > 0.65, 'when sentiment is higher than 0.65'),
	 
		
		
		#matchpatterns require haystack - np_candles? breaks :/
		#TriggerBlock(match_pattern, lambda res, npc : res[:,:,0] > 0, lambda res, npc : res[:,:,0] < 0, 'find matchings'),
		TriggerBlock(ADX(), lambda res, npc : res[:,:,0] > 0.25, lambda res, npc : res[:,:,0] > 0.25, 'check trending only'),
		TriggerBlock(ADX(), lambda res, npc : res[:,:,1] > 0.7, lambda res, npc : res[:,:,2] > 0.7, 'check positives and negatives'),
		TriggerBlock(ChoppinessIndex(), lambda res, npc : res[:,:,0] < res[:,:,1], lambda res, npc : res[:,:,0] < res[:,:,1]),
		
		
		#super trend
		#psar
		#aroon
		
		#TriggerBlock(FourierGradient(), ma_bullish, ma_bearish , 'simple ma style')
		TriggerBlock(BollingerBands(), lambda res, npc : npc[:,:,csf.close] < res[:,:,2], lambda res, npc : npc[:,:,csf.close] > res[:,:,1] ,'standard close above/below upper/lower bands'),
		TriggerBlock(KeltnerChannel(), lambda res, npc : npc[:,:,csf.high] > res[:,:,1], lambda res, npc : npc[:,:,csf.low] > res[:,:,2]),
		
		#anything else? 
		
	]

#WMA, TMMA, PivotPoints, Fibbonacci? TrianglePatterns, CandlestickPatterns, BollingerBands, KeltnerChannel, DonchianChannel, Divergences
#Shapes, Ichimoku, Trends
#awesome, accelerator


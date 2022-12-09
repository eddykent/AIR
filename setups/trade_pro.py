

#this file contains setups from youtube from some guys analysis. His name is TradePro so that is what this file is called 
#it is up to your future self if you want to continue adding more of his setups, but this is enough for now I think
#from youtube: 
#(MACD_MFT)		HIGHEST PROFITING Trading Strategy On YouTube PROVEN 100 Trades - MTF Indicator + MACD
#(RSIS_EMA_X)	Highly Profitable Trading Strategy Proven 100 Trades - RSI + Stochastic + 200 EMA
#(RSIS_EMA_1) 	Extremely Profitable 1 Minute Chart Trading Strategy Proven 100 Trades - EMA + RSI + Stochastic
#(HISTOGRAM)	Highly Profitable Indicator Absolute Strength Histogram Proven 100 Trades
#(CMF_MACD_ATR)	Chaikin Money Flow + MACD + ATR Best Simple Forex Trading Strategy Tested 100 Times
#(ENGULFING)	HIGH PROFIT 1 Minute Chart Scalping Stratgey Proven 100 Trades - RSI+200 EMA+ Engulfing
#(SIMPLE_MONEY)	Simple Money Flow Index MF! DayTrading Strategy Tested 100 Times (5 minute chart) - Full Results


import pdb

import charting.candle_stick_functions as csf
from charting.candle_stick_pattern import Engulfing

from setups.trade_setup import TradeSetup
from setups.setup_tools import DivTool, CrossTool, Zero2OneTool

from indicators.momentum import MACD 
from indicators.reversal import RSI, Stochastic
from indicators.moving_average import EMA
from indicators.volume import ChaikinMoneyFlow, MoneyFlowIndex

from utils import overrides


class MACD_MFT(TradeSetup):

	@overrides(TradeSetup)
	def detect(self,trade_signalling_data):
		#HTF filters? 
		#hourly 50 EMA = 200ema
		#15m 50 EMA
		
		#macd & signal > 0 for bearish (<0 for bullish)
		#macd never <0 when divergence downwards (or upwards) (TODO)
		#enter when macd cross
		#risk: above 5 high + 2 pip 
		#reward = risk * 2
		
		ema200 = EMA() #=hourly 50 ema 
		ema200.period = 200
		ema50 = EMA()
		ema50.period = 50
		
		macd = MACD()
		
		np_candles = trade_signalling_data.np_candles
		ema200_result = ema200(np_candles)[:,:,0]
		ema50_result = ema50(np_candles)[:,:,0]
		
		macd_result	= macd(np_candles)
		macd_line =  macd_result[:,:,0]
		macd_dev = macd_result[:,:,2]
		
		np_closes = np_candles[:,:,csf.close]
		
		div_tool1 = DivTool(macd_result, np_closes)
		div_tool1.order = 3 
		div_tool1.div_window = 20
		div_tool1.zero_cross = False
		
		div_tool2 = DivTool(macd_result, np_closes)
		
		bull_div1, bear_div1 = div_tool1.markup()
		bull_div2, bear_div2 = div_tool2.markup()
		
		bull_div = bull_div1 | bull_div2
		bear_div = bear_div1 | bear_div2 
		
		ema_bull = (ema50_result > ema200_result) #& (np_closes > ema50_result)  #comment out second bit? 
		ema_bear = (ema50_result < ema200_result) #& (np_closes < ema50_result)
		
		cross_bull, cross_bear = CrossTool.markup(macd_dev)
		
		bullish = cross_bull * ema_bull & bull_div
		bearish = cross_bear * ema_bear * bear_div  
		
		return Zero2OneTool.markup(bullish), Zero2OneTool.markup(bearish)
		

class RSIS_EMA_X(TradeSetup):
	
	@overrides(TradeSetup)
	def detect(self,trade_signalling_data):
		
		np_candles = trade_signalling_data.np_candles
		#EMA 200 long above/ short below
		ema200 = EMA()
		ema200.period = 200 
		
		ema200_result = ema200(np_candles)[:,:,0]
		np_closes = np_candles[:,:,csf.close]
		ema_bull = np_closes > ema200_result
		ema_bear = np_closes < ema200_result
		
		#RSI divergence  
		rsi = RSI() 
		rsi_result = rsi(np_candles)[:,:,0]
		
		div_tool1 = DivTool(rsi_result, np_closes)
		div_tool1.order = 3
		div_tool1.div_window = 20 
		
		div_tool2 = DivTool(rsi_result, np_closes)
		bull_div1, bear_div1 = div_tool1.markup() 
		bull_div2, bear_div2 = div_tool2.markup()
		
		bull_div = bull_div1 | bull_div2
		bear_div = bear_div1 | bear_div2 
				
		#stoch cross (n candles after div)
		stochastic = Stochastic()
		stochastic_result = stochastic(np_candles)
		
		stochastic_dev = stochastic_result[:,:,1] - stochastic_result[:,:,2]
		bull_cross, bear_cross = CrossTool.markup(stochastic_dev)
		
		bullish = ema_bull & bull_div & bull_cross
		bearish = ema_bear & bear_div & bear_cross
		
		return bullish, bearish  
		
#lost of signals 
class RSIS_EMA_1(TradeSetup): #check
	
	@overrides(TradeSetup)
	def detect(self,trade_signalling_data):
		#price below 50 and 200 ema
		ema50 = EMA() 
		ema200 = EMA() 
		ema50.period = 50
		ema200.period = 200 
		
		np_candles = trade_signalling_data.np_candles
		
		np_closes = np_candles[:,:,csf.close]
		ema50_result = ema50(np_candles)[:,:,0]
		ema200_result = ema200(np_candles)[:,:,0]
		
		bull_ema = (np_closes > ema50_result) & (ema50_result > ema200_result)
		bear_ema = (np_closes < ema50_result) & (ema50_result < ema200_result)
		
		#rsi divergence hidden!  
		rsi = RSI()
		rsi_result = rsi(np_candles)[:,:,0]
		
		div_tool1 = DivTool(rsi_result, np_closes)
		div_tool1.hidden = True 
		div_tool1.order = 3
		div_tool1.div_window = 20 
		
		div_tool2 = DivTool(rsi_result, np_closes)
		div_tool2.hidden = True 
		
		bull_div1, bear_div1 = div_tool1.markup() 
		bull_div2, bear_div2 = div_tool2.markup()
		bull_div = bull_div1 | bull_div2 
		bear_div = bear_div1 | bear_div2 
		
		bullish = bull_ema & bull_div 
		bearish = bear_ema & bear_div
		
		return bullish, bearish
		

class HISTOGRAM(TradeSetup):
	
	@overrides(TradeSetup)
	def detect(self,trade_signalling_data):
		#absolute histogram indicator - gman trading
		#hist blue = buy, red = sell (2 lines) 
		#200 ema above/below
		#atr 14 of 1.5 SL, RR 2 -maybe
		raise NotImplementedError('Implement me!')

class CMF_MACD_ATR(TradeSetup):
	
	@overrides(TradeSetup)
	def detect(self,trade_signalling_data):
		
		np_candles = trade_signalling_data.np_candles
		#macd #macd cross signal/macd & need to be > 0 for long & < 0 for short
		
		macd = MACD()
		macd_result = macd(np_candles)
		
		macd_bull = macd_result[:,:,0] > 0
		macd_bear = macd_result[:,:,0] < 0
		
		cmf = ChaikinMoneyFlow()
		cmf_result = cmf(np_candles)
		
		cmf_bull = cmf_result > 0
		cmf_bear = cmf_result < 0		
		
		cross_bull, cross_bear = CrossTool.markup(macd_result[:,:,2])
		#cmf > 0 long, cmf < 0 short
		#atr sl 2, r:r 2
		bullish = macd_bull & cmf_bull & cross_bull 
		bearish = macd_bear & cmf_bear & cross_bear
		
		return bullish, bearish

class ENGULFING(TradeSetup):
	
	@overrides(TradeSetup)
	def detect(self,trade_signalling_data):
		#rsi mid line > .5 buy  < .5 sell 
		np_candles = trade_signalling_data.np_candles
		np_closes = np_candles[:,:,csf.close]
		
		rsi = RSI() 
		rsi_result = rsi(np_candles)[:,:,0]
		
		rsi_bull = rsi_result > 0.5
		rsi_bear = rsi_result < 0.5		
		
		#ema 200 above/below
		ema200 = EMA()
		ema200.period = 200
		ema_result = ema200(np_candles)[:,:,0]
		
		ema_bull = ema_result < np_closes 
		ema_bear = ema_result > np_closes 
		
		#bullish/bearish candle patterns (engulfing)
		eng = Engulfing() #replace with CandlePatternEnsemble 

		eng_result = eng(np_candles)[:,:,0]
		eng_bullish = eng_result > 0
		eng_bearish = eng_result < 0 
		
		bullish = rsi_bull & ema_bull & eng_bullish 
		bearish = rsi_bear & ema_bear & eng_bearish 
		
		return bullish, bearish 		
		
	


class SIMPLE_MONEY(TradeSetup):
	
	@overrides(TradeSetup)
	def detect(self,trade_signalling_data):
		np_candles = trade_signalling_data.np_candles
		np_closes = np_candles[:,:,csf.close]
		
		#200 ema above/below
		ema200 = EMA() 
		ema200.period = 200
		ema_result = ema200(np_candles)[:,:,0]
		
		ema_bull = np_closes > ema_result 
		ema_bear = np_closes < ema_result 
		
		#money flow index > .8 => sell 
		mfi = MoneyFlowIndex()
		mfi_result = mfi(np_candles)[:,:,0]
		
		mfi_bear = mfi_result > 0.8 
		mfi_bull = mfi_result < 0.2
		
		bullish = ema_bull & mfi_bull
		bearish = ema_bear & mfi_bear
		
		#sl few pips after rolling high/low or ema level whichever bigger
		#tp = 2 * sl
		
		return Zero2OneTool.markup(bullish), Zero2OneTool.markup(bearish)
		















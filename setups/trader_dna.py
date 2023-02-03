

#this file contains a bunch of Trader DNA youtube channel setups that can be used in our trading bot 
##list here: 
#(TripleRSIADX) - Triple RSI-ADX Trading Strategy - The BEST "SCALPING and SWING Trading Strategy" for Beginners https://www.youtube.com/watch?v=k1dejtLqKP0
#(DoubleCCICross) - The "DOUBLE CCI" SCALPING & SWING Trading Strategy - The Best Zero Line Cross Trading Strategy https://www.youtube.com/watch?v=UH9lp6_t86Y
#(RSI_MACD_STOCH) - The "RSI-MACD-STOCHASTIC" PRICE ACTION SECRET That No One Will Tell You...(BEGINNER TO EXPERT) https://www.youtube.com/watch?v=R1cKTKV6-gc
#(MACD123) - 1-2-3 EMA-MACD "SCALPING" Strategy - One of The Best Absolute Methods for Trading https://www.youtube.com/watch?v=SOS_YnPZSQo
#(ZeroLagEMA) - Zero Lag EMA - The BEST “Simple Trading Strategy” For Beginners That No one Ever Told You https://www.youtube.com/watch?v=kz0wT8zM8lE
#(MACD_DOUBLE_DIV) - "MACD Double Divergence" The Ultimate MACD Patterns Trading Course https://www.youtube.com/watch?v=_1_PeIFfy4U
import numpy as np
import pdb

from utils import overrides

import charting.candle_stick_functions as csf
from charting.candle_stick_pattern  import Engulfing, PinBar
from charting.chart_pattern import ChartPattern, SupportAndResistance #get an xtreme window 

from setups.trade_setup import TradeSetup
from setups.setup_tools import DivTool, CrossTool, Zero2OneTool, CandleLagTool, ValueLagTool, ExtremesTool, SmudgeTool


from indicators.trend import ADX, CCI
from indicators.momentum import MACD 
from indicators.moving_average import EMA, ZLMA
from indicators.reversal import RSI, Stochastic


class TripleRSIADX(TradeSetup):
	#7, 14, 21 RSI - 7 above 14 and 21, and all above mid line means buy (divtool?) 
	#50 period ema - price "touches" means prev candle fully above, and this candle or next or next line goes through hl and this candle closes above? or through
	#adx 14 value of 20 or more & moving up 
	#aggressive - close to prev support/resistance value (>1 atr?) (with SR)
	#conservative - candle stick pattern (WithCSP)
	#SL rolling low + few pip buffer
	aggressive = True 
	conservative = False 
	
	@overrides(TradeSetup)
	def indicators(self):
		self.indicator_bag = {
			'rsi07':RSI(7),
			'rsi14':RSI(14),
			'rsi21':RSI(21),
			'ema50':EMA(50),
			'adx14':ADX(14)
		}
	
	@overrides(TradeSetup)
	def chart_patterns(self):
		self.chart_pattern_bag = {
			'support_resistance1':SupportAndResistance()
		}
	
	@overrides(TradeSetup)
	def trigger(self,trade_signalling_data):
		rsi07 = self.indicator_bag['rsi07'] 
		rsi14 = self.indicator_bag['rsi14'] 
		rsi21 = self.indicator_bag['rsi21'] 
		ema50 = self.indicator_bag['ema50']  
		adx14 = self.indicator_bag['adx14'] 
		
		np_candles = trade_signalling_data.np_candles 
		rsi07_result = rsi07(np_candles)[:,:,0]
		rsi14_result = rsi14(np_candles)[:,:,0]
		rsi21_result = rsi21(np_candles)[:,:,0]
		adx14_result = adx14(np_candles)[:,:,0]
		ema50_result = ema50(np_candles)[:,:,0]
		
		rsi_bullish = (rsi07_result >= rsi14_result) & (rsi14_result >= rsi21_result) & (rsi21_result > 0.5)
		rsi_bearish = (rsi07_result <= rsi14_result) & (rsi14_result <= rsi21_result) & (rsi21_result < 0.5)
		
		ema_touch = (np_candles[:,:,csf.low] <= ema50_result) & (ema50_result <= np_candles[:,:,csf.high]) 
		ema_bullish = ema_touch & (np_candles[:,:,csf.close] > ema50_result) #& (np_candles[:,:,csf.close] > np_candles[:,:,csf.open])
		ema_bearish = ema_touch & (np_candles[:,:,csf.close] < ema50_result) #& (np_candles[:,:,csf.close] < np_candles[:,:,csf.open])
		
		adx_ok = adx14_result > 25
		
		bullish = adx_ok & ema_bullish & rsi_bullish 
		bearish = adx_ok & ema_bearish & rsi_bearish
		
		if self.aggressive:
			#test S&R
			support_resistance = self.chart_pattern_bag['support_resistance1']
			sr_bias = support_resistance(np_candles)[:,:,0]  #bias is at 1
			bullish = bullish & (sr_bias > 0)
			bearish = bearish & (sr_bias < 0)
			
		if self.conservative:
			#test candles 
			pass
		
		#pdb.set_trace()
		return Zero2OneTool.markup(bullish), Zero2OneTool.markup(bearish) #best to do this with all? 
		
		

#MANY signals
class DoubleCCICross(TradeSetup):
	#CCI 50, 25 - cci25 is positive and cci50 crosses from neg to positive 
	#ema 34 price closes above 
	#trigger when this candle high is higher than prev, and this candle is bullish 
	#SL rolling low + few pip buffer or fixed pips
	#anything else? 
	
	@overrides(TradeSetup)
	def indicators(self):
		self.indicator_bag = {
			'cci25':CCI(25),
			'cci50':CCI(50),
			'ema34':EMA(34)
		}
		
	@overrides(TradeSetup)
	def trigger(self,trade_signalling_data):
		cci25 = self.indicator_bag['cci25']
		cci50 = self.indicator_bag['cci50']
		ema34 = self.indicator_bag['ema34']
		
		np_candles = trade_signalling_data.np_candles 
		cci25_result = cci25(np_candles)[:,:,0]
		cci50_result = cci50(np_candles)[:,:,0]
		ema34_result = ema34(np_candles)[:,:,0]
		
		cci_bullish = Zero2OneTool.markup(cci25_result > 0) & (cci50_result > 0)
		cci_bearish = Zero2OneTool.markup(cci25_result < 0) & (cci50_result < 0)
		
		ema_bullish = ema34_result < np_candles[:,:,csf.close]
		ema_bearish = ema34_result > np_candles[:,:,csf.close]
		
		cdt = CandleLagTool() #lag=1
		prev_candles = cdt.markup(np_candles)
		
		candle_bullish = (prev_candles[:,:,csf.high] < np_candles[:,:,csf.high]) & (np_candles[:,:,csf.open] < np_candles[:,:,csf.close])
		candle_bearish = (prev_candles[:,:,csf.low] > np_candles[:,:,csf.low]) & (np_candles[:,:,csf.open] > np_candles[:,:,csf.close])
		
		bullish = cci_bullish & ema_bullish & candle_bullish 
		bearish = cci_bearish & ema_bearish & candle_bearish
		
		#pdb.set_trace()
		return Zero2OneTool.markup(bullish), Zero2OneTool.markup(bearish) #best to do this with all? 
		
	

#this one was confusing since there are 3 events that have to happen "in a time of" eachother 
#i decided to use each as a trigger, then look to see if the other two happened recently 
#LOADS of signals
class RSI_MACD_STOCH(TradeSetup): 
	#stoch both oversold then (use lags)
	#rsi > .5 then (use lags)
	#macd crosses up above signal then 
	#ensure stoch now not overbought
	
	def indicators(self):
		self.indicator_bag = {
			'stoch':Stochastic(),
			'rsi':RSI(),
			'macd':MACD()
		}
	
	@overrides(TradeSetup)
	def trigger(self,trade_signalling_data):
		stoch = self.indicator_bag['stoch']
		rsi = self.indicator_bag['rsi']
		macd = self.indicator_bag['macd']
		
		#2 triggers - either macd cross, or rsi goes above 0.5 - stoch always lags anyway 
		np_candles = trade_signalling_data.np_candles
		stoch_result = stoch(np_candles)
		rsi_result = rsi(np_candles)[:,:,0]
		macd_result = macd(np_candles)
		
		#trigger 1 - rsi > 0.5 
		rsi_bullish_trigger = Zero2OneTool.markup(rsi_result > 0.5)
		rsi_bearish_trigger = Zero2OneTool.markup(rsi_result < 0.5)
		macd_bullish = macd_result[:,:,0] > macd_result[:,:,1] #macd line > signal line 
		macd_bearish = macd_result[:,:,0] < macd_result[:,:,1]
		trigger1_bullish = rsi_bullish_trigger & macd_bullish
		trigger1_bearish = rsi_bearish_trigger & macd_bearish
		
		#triger2 - macd crosses signal 
		macd_bullish_trigger, macd_bearish_trigger = CrossTool.markup(macd_result[:,:,0] - macd_result[:,:,1])
		rsi_bullish = rsi_result > 0.5
		rsi_bearish = rsi_result < 0.5
		trigger2_bullish = macd_bullish_trigger & rsi_bullish
		trigger2_bearish = macd_bearish_trigger & rsi_bearish
		
		bull_trigger = trigger1_bullish | trigger2_bullish 
		bear_trigger = trigger1_bearish | trigger2_bearish 
		
		#now for stochastic stuff 
		stoch_overbought = (stoch_result[:,:,0] > 0.8) & (stoch_result[:,:,1] > 0.8)
		stoch_oversold = (stoch_result[:,:,0] < 0.2) & (stoch_result[:,:,1] < 0.2)
		
		st = SmudgeTool()
		st.smudge_length = stoch.period #arbitrary... 
		stoch_overbought_recently = st.markup(stoch_overbought)
		stoch_oversold_recently = st.markup(stoch_oversold) 
		
		bullish = stoch_oversold_recently & ~stoch_overbought & bull_trigger
		bearish = stoch_overbought_recently & ~stoch_oversold & bear_trigger 
		
		return Zero2OneTool.markup(bullish), Zero2OneTool.markup(bearish)
		


class MACD123(TradeSetup):
	#8, 13, 21 EMAs and MACD 
	#8ema > 13ema > 21 ema? (cross in close proximity? <5candles) 
	#macd > signal line & both macd and signal going upwards 
	#hist starts growing after shrinking (momentum increasing) 
	
	first_crosses_only = False 
	
	@overrides(TradeSetup)
	def indicators(self):
		self.indicator_bag = {
			'ema08': EMA(8),
			'ema13': EMA(13),
			'ema21': EMA(21), 
			'macd': MACD()
		}
	
	@overrides(TradeSetup)
	def trigger(self,trade_signalling_data):
		ema08 = self.indicator_bag['ema08']
		ema13 = self.indicator_bag['ema13']
		ema21 = self.indicator_bag['ema21']
		macd = self.indicator_bag['macd']
		
		np_candles = trade_signalling_data.np_candles
		ema08_result = ema08(np_candles)[:,:,0]
		ema13_result = ema13(np_candles)[:,:,0]
		ema21_result = ema21(np_candles)[:,:,0]
		macd_result = macd(np_candles)
			
		#simple way
		ema_bullish = (ema08_result > ema13_result) & (ema13_result > ema21_result)
		ema_bearish = (ema08_result < ema13_result) & (ema13_result < ema21_result)
		
		if self.first_crosses_only:
			#consider using delay crossovers here instead - update ema_bullish and ema_bearish accordingly
			pass
		
		macd_bullish = macd_result[:,:,0] > macd_result[:,:,1]
		macd_bearish = macd_result[:,:,0] < macd_result[:,:,1]
		
		macd_hist = np.abs(macd_result[:,:,0] - macd_result[:,:,1]) 
		macd_hist_change = np.concatenate([np.zeros((macd_hist.shape[0],1)), macd_hist[:,1:] - macd_hist[:,:-1]],axis=1)
		
		lagger = ValueLagTool()
		prev_macd_hist_change = lagger.markup(macd_hist_change)
		
		macd_trigger = (prev_macd_hist_change < 0) & (macd_hist_change > 0) #macd hist was shrinking but now it is growing again 
		
		bullish = ema_bullish & macd_bullish & macd_trigger 
		bearish = ema_bearish & macd_bearish & macd_trigger
		
		return bullish, bearish
		
		


class ZeroLagEMA(TradeSetup):
	#NLMA 240
	#NLMA 21
	#240 slope up 
	#21 higher highs and higher lows 
	#use standard chart pattern or perhaps shape patterns 
	#21 closed above 21nlma
	
	@overrides(TradeSetup)
	def indicators(self):
		self.indicator_bag = {
			'nlma021': ZLMA(21), 
			'nlma240': ZLMA(240)
		}
	
	@overrides(TradeSetup)
	def tools(self):
		self.tool_bag = {
			'et1':ExtremesTool(20,3), 
			'et2':ExtremesTool(40,5)
		}
	
	
	@overrides(TradeSetup)
	def trigger(self, trade_signalling_data):
		
		nlma021 = self.indicator_bag['nlma021']
		nlma240 = self.indicator_bag['nlma240']
		
		np_candles = trade_signalling_data.np_candles
		nlma021_result = nlma021(np_candles)[:,:,0]
		nlma240_result = nlma240(np_candles)[:,:,0]
		
		nlma240_grad = np.concatenate([np.full((nlma240_result.shape[0],1),np.nan), nlma240_result[:,1:] - nlma240_result[:,:-1]],axis=1)
		
		nlma_bullish = (np_candles[:,:,csf.close] > nlma021_result) & (nlma240_grad > 0)
		nlma_bearish = (np_candles[:,:,csf.close] < nlma021_result) & (nlma240_grad < 0)
		
		#check nlma21 for higher highs and higher lows or lower highs and lower lows 
		et1 = self.tool_bag['et1']
		et2 = self.tool_bag['et2']
		high2s = et1.markup(nlma021_result,'max')
		high5s = et2.markup(nlma021_result,'max')
		low2s = et1.markup(nlma021_result,'min')
		low5s = et2.markup(nlma021_result,'min')
		
		#bounds checks?
		hhhls2 = (high2s[:,:,-2,1] < high2s[:,:,-1,1]) & (low2s[:,:,-2,1] < low2s[:,:,-1,1])
		hhhls5 = (high5s[:,:,-2,1] < high5s[:,:,-1,1]) & (low5s[:,:,-2,1] < low5s[:,:,-1,1])
		
		lhlls2 = (high2s[:,:,-2,1] > high2s[:,:,-1,1]) & (low2s[:,:,-2,1] > low2s[:,:,-1,1])
		lhlls5 = (high5s[:,:,-2,1] > high5s[:,:,-1,1]) & (low5s[:,:,-2,1] > low5s[:,:,-1,1])
		
		
		hhhl = hhhls2 | hhhls5
		lhll = lhlls2 | lhlls5
		
		bullish = nlma_bullish & hhhl
		bearish = nlma_bearish & lhll
		
		return bullish, bearish 
		
		
		
		
		

class MACD_DOUBLE_DIV(TradeSetup):
	#use macd and divergence
	#use macd div on close, macd line
	#use macd div on close, histogram 
	#trigger on macd cross? configurable
	
	@overrides(TradeSetup)
	def indicators(self):
		self.indicator_bag = {
			'macd':MACD()
		}
	
	@overrides(TradeSetup)
	def tools(self):
		self.tool_bag = {
			'div4':DivTool(30,4,other_chart='macd'),
			'div7':DivTool(40,7,other_chart='macd')
		}
	
	@overrides(TradeSetup)
	def trigger(self, trade_signalling_data):
		
		macd = self.indicator_bag['macd']
		np_candles = trade_signalling_data.np_candles
		macd_result = macd(np_candles)
		
		np_closes = np_candles[:,:,csf.close]
		macd_line = macd_result[:,:,0]
		macd_hist = macd_result[:,:,2]
		
		div4 = self.tool_bag['div4']
		div7 = self.tool_bag['div7']
		
		bullish_macd4, bearish_macd4 = div4.markup(np.stack([np_closes, macd_line]))
		bullish_macd7, bearish_macd7 = div7.markup(np.stack([np_closes, macd_line]))
		
		bullish_hist4, bearish_hist4 = div4.markup(np.stack([np_closes, macd_hist]))
		bullish_hist7, bearish_hist7 = div7.markup(np.stack([np_closes, macd_hist]))
		
		bullish_macd = bullish_macd4 | bullish_macd7
		bearish_macd = bearish_macd4 | bearish_macd7
		
		bullish_hist = bullish_hist4 | bullish_hist7
		bearish_hist = bearish_hist4 | bearish_hist7
		
		sm = SmudgeTool() #smudge_length = 5
		recent_bullish_macd = sm.markup(bullish_macd)
		recent_bearish_macd = sm.markup(bearish_macd)
		
		recent_bullish_hist = sm.markup(bullish_hist)
		recent_bearish_hist = sm.markup(bearish_hist)
		
		cx = CrossTool()
		macd_cross_bullish, macd_cross_bearish = cx.markup(macd_hist)
		
		bullish = recent_bullish_macd & recent_bullish_hist & macd_cross_bullish
		bearish = recent_bearish_macd & recent_bearish_hist & macd_cross_bearish
		
		return bullish, bearish 







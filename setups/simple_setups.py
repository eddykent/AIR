import pdb

from setups.trade_setup import *

from indicators.moving_average import EMA 
from indicators.indicator import CandleSticks, RunningHigh, RunningLow
from indicators.momentum import MACD
from indicators.reversal import RSI 
from indicators.volatility import BollingerBands
from indicators.trend import ADX


from charting.chart_pattern import SupportAndResistance



class ForexSignalsAnchorBarStop(StopTool):
	
	rrratio = 1.5
	tolerance = 0.05
	
	def __init__(self,risk_reward_ratio=1.5,tolerance_percentage=0.05):
		self.rrratio = risk_reward_ratio
		self.tolerance = tolerance_percentage
	
	@overrides(StopTool)
	def get_stops(self,trade_signalling_data):
		
		candlesticks = trade_signalling_data.candlesticks
		
		candles_pre = CandleSticks() 
		candles = candles_pre.calculate_multiple(candlesticks) 
		
		entry_bullish = trade_signalling_data.bullish.entries
		entry_bearish = trade_signalling_data.bearish.entries

		stop_loss_bullish = np.abs(entry_bullish - candles[:,:,csf.low]) #the current candle is the trigger bar 
		stop_loss_bearish = np.abs(entry_bearish - candles[:,:,csf.high])
		
		#check this bit 
		stop_loss_bullish = stop_loss_bullish * (1.0 + self.tolerance) # add 5% tollerance #+3 pips thing
		stop_loss_bearish = stop_loss_bearish * (1.0 + self.tolerance)
		
		take_profit_bullish = stop_loss_bullish * self.rrratio #1.5 Risk:Reward
		take_profit_bearish = stop_loss_bearish * self.rrratio
		
		return (take_profit_bullish, take_profit_bearish),  (stop_loss_bullish,stop_loss_bearish)



#file for holding very simple setups 

#use with a MA anchor chart filter (eg price above 8 above 21 for buy)  - possibly use a larger moving average for same chart - perfect for testing filters 
#fanned out - 8, 13, 21. 
#price touches 8 => trigger bar. 
#count back 5 and get highest (body?) => entry
#risk = min trigger bar 
#profit = risk * 1
#the backtest for the inverse of this setup without any filters gives good results! 
#if close above 21ma, trade is off - need a trade purge/filter
class ForexSignalsAnchorBar(TradeSetup):
	
	grace_period = 50
	
	stop_tool = ForexSignalsAnchorBarStop()
	
	@overrides(TradeSetup)
	def detect(self,trade_signalling_data):
		
		candles_pre = CandleSticks()
		ema8 = EMA()
		ema13 = EMA() 
		ema21 = EMA() 
		
		ema8.period = 8 
		ema13.period = 13
		ema21.period = 21 
		
		candlesticks = trade_signalling_data.candlesticks
		
		candles = candles_pre.calculate_multiple(candlesticks)
		prev_candles = np.concatenate([np.full((candles.shape[0],1,candles.shape[2]),np.nan),candles[:,:-1,:]],axis=1)
		ema8_result = ema8.calculate_multiple(candlesticks)[:,:,0]
		ema13_result = ema13.calculate_multiple(candlesticks)[:,:,0]
		ema21_result = ema21.calculate_multiple(candlesticks)[:,:,0]
		
		fanout_bullish = (ema8_result > ema13_result) & (ema13_result > ema21_result)
		fanout_bearish = (ema8_result < ema13_result) & (ema13_result < ema21_result)
		
		trigger_bullish = (prev_candles[:,:,csf.low] > ema8_result) & (candles[:,:,csf.low] <= ema8_result) & (candles[:,:,csf.low] > ema13_result)
		trigger_bearish = (prev_candles[:,:,csf.high] < ema8_result) & (candles[:,:,csf.high] >= ema8_result) & (candles[:,:,csf.high] < ema13_result)
		
		bullish_signals = fanout_bullish & trigger_bullish 
		bearish_signals = fanout_bearish * trigger_bearish 
		 
		#return bearish_signal,bullish_signal #swap round makes better signals?
		return bullish_signals, bearish_signals
	
	@overrides(TradeSetup)
	def get_entries(self,trade_signalling_data):
		high5s = RunningHigh()  
		high5s.period = 5
		
		low5s = RunningLow()
		low5s.period = 5
		
		candlesticks = trade_signalling_data.candlesticks 
		
		entry_bullish = high5s.calculate_multiple(candlesticks)[:,:,0]  #+3pips 
		entry_bearish = low5s.calculate_multiple(candlesticks)[:,:,0]   #-3pips 
		
		return entry_bullish, entry_bearish 
		
		
	@overrides(TradeSetup)
	def get_entry_cuts(self,trade_signalling_data):
		
		candlesticks = trade_signalling_data.candlesticks 
		ema21 = EMA() 
		ema21.period = 21 
		ema21_result = ema21.calculate_multiple(candlesticks)[:,:,0]
		
		high5s = RunningHigh()  
		high5s.period = 5
		
		low5s = RunningLow()
		low5s.period = 5
		
		cut_bearish = high5s.calculate_multiple(candlesticks)[:,:,0]  #+3pips 
		cut_bullish = low5s.calculate_multiple(candlesticks)[:,:,0]   #-3pips 
		
		return np.maximum(cut_bullish,ema21_result), np.minimum(cut_bearish,ema21_result)
		
		
		#high5s = RunningHigh()  #used as triggers 
		#high5s.period = 5
		#
		#low5s = RunningLow()
		#low5s.period = 5
		#
		#entry_bullish = high5s.calculate_multiple(candlesticks)[:,:,0]
		#entry_bearish = low5s.calculate_multiple(candlesticks)[:,:,0]
		#
		#stop_loss_bullish = np.abs(entry_bullish - candles[:,:,csf.low]) #the current candle is the trigger bar 
		#stop_loss_bearish = np.abs(entry_bearish - candles[:,:,csf.high])
		#
		#stop_loss_bullish = stop_loss_bullish * 1.05 # add 5% tollerance 
		#stop_loss_bearish = stop_loss_bearish * 1.05
		#
		#take_profit_bullish = stop_loss_bullish * 1.5 #1.5 Risk:Reward
		#take_profit_bearish = stop_loss_bearish * 1.5 
		#
		
		#buy_coords = np.stack(np.where(buy_signals),axis=1)
		#sell_coords = np.stack(np.where(sell_signals),axis=1)
		#
		#for (instrument_index,timeline_index) in buy_coords:
		#	if timeline[timeline_index] < start_date:
		#		continue
		#	the_date = timeline[timeline_index]
		#	instrument = available_instruments[instrument_index]
		#	strategy_ref = self.__class__.__name__
		#	direction = TradeDirection.BUY
		#	entry = entry_bullish[instrument_index,timeline_index] #consider entry_prices[instrument_index,timeline_index]
		#	take_profit_distance = take_profit_bullish[instrument_index,timeline_index]
		#	stop_loss_distance = stop_loss_bullish[instrument_index,timeline_index]
		#	
		#	ts = TradeSignal.from_full(the_date,instrument,strategy_ref,direction,entry,take_profit_distance,stop_loss_distance)
		#	trade_signals.append(ts)
		#
		#for (instrument_index,timeline_index) in sell_coords:
		#	if timeline[timeline_index] < start_date:
		#		continue
		#	the_date = timeline[timeline_index]
		#	instrument = available_instruments[instrument_index]
		#	strategy_ref = self.__class__.__name__
		#	direction = TradeDirection.SELL
		#	entry = entry_bearish[instrument_index,timeline_index]
		#	take_profit_distance = take_profit_bearish[instrument_index,timeline_index]
		#	stop_loss_distance = stop_loss_bearish[instrument_index,timeline_index]
		#	
		#	ts = TradeSignal.from_full(the_date,instrument,strategy_ref,direction,entry,take_profit_distance,stop_loss_distance)
		#	trade_signals.append(ts)
		#
		#return trade_signals

#miror of the above setup, but the signals are reflected - it seems to perform well! (mean reversion, fuck forex signals!) 
class MeanReversionFFXS(TradeSetup):
	
	grace_period = 50
	
	@overrides(TradeSetup)
	def detect(self,trade_signalling_data):
		bullish, bearish = ForexSignalsAnchorBar.detect(self,trade_signalling_data)
		return bearish, bullish 
	
	@overrides(TradeSetup)
	def get_entries(self,trade_signalling_data):
		bullish, bearish =  ForexSignalsAnchorBar.get_entries(self,trade_signalling_data) 
		return bearish, bullish 

#test for pinbars and engulfers above/below the moving average line (pullback strat?)
class ForexSignalsCandles(TradeSetup):
	pass



class WyseTradeBollingerBands(TradeSetup):  #more wysetrade based?
	pass



class MACD_EMA_SR(TradeSetup):
	
	grace_period = 50
	
	@overrides(TradeSetup)
	def detect(self,trade_signalling_data):
		
		ema200 = EMA() 
		macd_ind = MACD()#default settings 
		
		candlesticks = trade_signalling_data.candlesticks 
		candles_pre = CandleSticks()
		
		ema200.period = 200
		
		snr = SupportAndResistance()#default settings? raise to 200?
		
		candle_closes = candles_pre.calculate_multiple(candlesticks)[:,:,csf.close]
		ema200_result = ema200.calculate_multiple(candlesticks)[:,:,0]
		
		macd_directions = macd_ind.calculate_multiple(candlesticks)[:,:,3] #get directions 
		prev_macd_directions = np.concatenate([np.full((macd_directions.shape[0],1),np.nan),macd_directions[:,:-1]],axis=1)
		#determine macd crossover signals
		bullish_macd = (prev_macd_directions < 0) & (macd_directions > 0)
		bearish_macd = (prev_macd_directions > 0) & (macd_directions < 0)
		
		bullish_ema = candle_closes > ema200_result
		bearish_ema = candle_closes < ema200_result
		
		snr_result = snr.calculate_multiple(candlesticks)[:,:,0] 
		
		bullish_signal = bullish_macd & bullish_ema & (snr_result > 0)
		bearish_signal = bearish_macd & bearish_ema & (snr_result < 0)
		
		return bullish_signal, bearish_signal
		
	


class FastRSI(TradeSetup):
	
	grace_period = 50
	
	@overrides(TradeSetup)
	def detect(self,trade_signalling_data):
		
		ema200 = EMA() 
		ema5 = EMA() 
		
		rsi = RSI() 
		
		candlesticks = trade_signalling_data.candlesticks
		candles_pre = CandleSticks()
		
		ema200.period = 200
		ema5.period = 20
		rsi.period = 3
		
		
		candle_closes = candles_pre.calculate_multiple(candlesticks)[:,:,csf.close]
		ema200_result = ema200.calculate_multiple(candlesticks)[:,:,0]
		ema5_result = ema5.calculate_multiple(candlesticks)[:,:,0]
		rsi_result = rsi.calculate_multiple(candlesticks)[:,:,0]
		
		bullish_ema1 = candle_closes > ema200_result
		bearish_ema1 = candle_closes < ema200_result
		
		bullish_ema2 = candle_closes < ema5_result
		bearish_ema2 = candle_closes > ema5_result
		
		bullish_rsi = rsi_result < 0.05
		bearish_rsi = rsi_result > 0.05
		
		bullish_signal = (bullish_rsi & bullish_ema1) & bullish_ema2
		bearish_signal = (bearish_rsi & bearish_ema1) & bearish_ema2
		
		
		return Zero2OneTool.markup(bearish_signal), Zero2OneTool.markup(bullish_signal)
		#return Zero2OneTool.markup(bullish_signal), Zero2OneTool.markup(bearish_signal)
		
		
		

#https://medium.com/@daviddtech/83-win-rate-5-minute-ultimate-scalping-trading-strategy-89c4e89fb364
class MediumScalpDaviddAnthony(TradeSetup):
	
	grace_period = 50
	
	@overrides(TradeSetup)
	def detect(self,trade_signalling_data):
		
		ema9 = EMA() 
		ema55 = EMA() 
		ema200 = EMA()
		
		rsi14 = RSI() 
		macd1 = MACD() 
		
		#improvements 
		adx26 = ADX() 
		
		ema9.period = 9
		ema55.period = 55
		ema200.period = 200 
		
		bbmacd = BollingerBands() #use bb on macd[2] (deviation) to get low and high bars  
		bbmacd.candle_channel = 0
		
		candlesticks = trade_signalling_data.candlesticks 
		
		ema200_result = ema200.calculate_multiple(candlesticks)[:,:,0]
		ema55_result = ema55.calculate_multiple(candlesticks)[:,:,0]
		ema9_result = ema9.calculate_multiple(candlesticks)[:,:,0]
		
		rsi14_result = rsi14.calculate_multiple(candlesticks)[:,:,0]
		macd_deviation = macd1.calculate_multiple(candlesticks)[:,:,2:3]
				
		bb_result = bbmacd._perform(macd_deviation)
		bb_macd_highs = bb_result[:,:,1]
		bb_macd_lows = bb_result[:,:,2]
		
		adx26_result = adx26.calculate_multiple(candlesticks)[:,:,0]
		
		#pdb.set_trace()
		
		#for long, ema9 > ema55 > ema200, rsi > 52 and macd_dev < bb_macd_low
		bullish_signal = (ema9_result > ema55_result) & (ema200_result > ema55_result) & \
		(rsi14_result > 0.52) & (macd_deviation[:,:,0] < bb_macd_lows)  & (adx26_result > 26)
		bearish_signal = (ema9_result < ema55_result) & (ema200_result < ema55_result) & \
		(rsi14_result < 0.48) & (macd_deviation[:,:,0] > bb_macd_highs) & (adx26_result > 26)
		
		return Zero2OneTool.markup(bullish_signal), Zero2OneTool.markup(bearish_signal) 
	
	
	#@overrides(TradeSetup)
	#def 
	
	
	#tp/sl can be 30 and 20 pips respectively 
	

















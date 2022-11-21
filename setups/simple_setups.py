import pdb
import numpy as np

from setups.trade_setup import TradeSetup
from setups.setup_tools import StopTool, SmudgeTool, DelayTool

from indicators.moving_average import EMA 
from indicators.indicator import CandleSticks, RunningHigh, RunningLow
from indicators.momentum import MACD
from indicators.reversal import RSI 
from indicators.volatility import BollingerBands
from indicators.trend import ADX, IchimokuCloud

from charting.candle_stick_pattern import PinBar, Engulfing
import charting.candle_stick_functions as csf
from utils import overrides

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
	
	def detect(self,trade_signalling_data):
		candlesticks = trade_signalling_data.candlesticks 
		ema200 = EMA() 
		ema200.period = 200 
		ema200_result = ema200.calculate_multiple(candlesticks)[:,:,0]
		
		close_values = candlesticks[:,:,csf.close]
		
		pinbars = PinBar()
		engulfers = Engulfing()
		
		pinbar_results = pinbars.calculate_multiple(candlesticks)
		engulf_results = engulfers.calculate_multiple(candlesticks)
		
		candle_results = (pinbar_results + engulf_results)[:,:,0]
		
		#pin to the 200ema using ATR? 
		
		bullish = (candle_results > 0) & (close_values > ema200_result) 
		bearish = (candle_results < 0) & (close_values < ema200_result)
		
		return bullish, bearish
		



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
	



#youtube.com/watch?v=cnHZIxHFtXo&list=RDCMUC9aJvG8qRKxN4MgrYIX4IrQ&start_radio=1&rv=cnHZIxHFtXo&t=0
#class IchimokuCloudSetup(TradeSetup);
class IchimokuCloudBreakoutSetup(TradeSetup): #superichi?
	
	
	# wait for candle close above/below cloud (candle has to be touching cloud?)  
	# wait for base / conversion crossover conversion > base = bull 
	# additional: wait for cloud to be bullish/bearish
	# additional: wait for both base & conversion to be correct side of cloud 
	# additional: wait for candles to dip below then above base & conversion - this was the retraction 
	# buy at next candle 
	
	#ideas:
	# check cloud larger than ATR 
	#stops - recent low?
	
	grace_period = 50
	breakout_candles = 5 # candles ago that need to be below the two lines 
	
	conversion_period = 9 
	base_period = 26 #cloud lag
	span_period = 52 #cloud lag lag (for lag check) 
	
	use_cloud_colour = True #turn off for HTFs
	#other switches?
	
	@overrides(TradeSetup)
	def detect(self,trade_signalling_data):
		
		ichi = IchimokuCloud() 
		
		ichi.conversion_period = self.conversion_period
		ichi.base_period = self.base_period 
		ichi.span_period = self.span_period
		
		candlesticks = trade_signalling_data.candlesticks
		ichi_results = ichi.calculate_multiple(candlesticks)
		#indexs: 
		#0 = tenken-sen - conversion 
		#1 = kijun-seh - base
		#2 = senku span - span a     span a > span b = green 
		#3 = chikou span - span b    span b > span a = red
		#4 = close price (use as lagging span - check lag now on cloud 52 periods ago) 
		cloud_a = np.concatenate([np.full((ichi_results.shape[0],self.base_period),np.nan), ichi_results[:,:-self.base_period,2]],axis=1) 
		cloud_b = np.concatenate([np.full((ichi_results.shape[0],self.base_period),np.nan), ichi_results[:,:-self.base_period,3]],axis=1) 
		
		lag_cloud_a = np.concatenate([np.full((ichi_results.shape[0],self.span_period),np.nan), ichi_results[:,:-self.span_period,2]],axis=1) 
		lag_cloud_b = np.concatenate([np.full((ichi_results.shape[0],self.span_period),np.nan), ichi_results[:,:-self.span_period,3]],axis=1) 
		
		#pdb.set_trace()
		
		cloud_max = np.maximum(cloud_a,cloud_b)
		cloud_min = np.minimum(cloud_a,cloud_b)	
		
		closes = ichi_results[:,:,csf.close]
		base = ichi_results[:,:,1]
		conversion = ichi_results[:,:,0]
		
		price_cloud_bullish = closes > cloud_max
		price_cloud_bearish = closes < cloud_min
		
		baseconv_bullish = base < conversion
		baseconv_bearish = base > conversion
		
		cloud_colour = np.full(closes.shape,0)
		if self.use_cloud_colour:
			cloud_colour[cloud_a > cloud_b] = +1 #green 
			cloud_colour[cloud_a < cloud_b] = -1 #red
			
		cloud_bullish = cloud_colour >= 0 
		cloud_bearish = cloud_colour <= 0
		
		bothlines_status = np.full(ichi_results.shape[:2],0)#gray 
		#if self.use_both_lines:
		bothlines_status[(base > cloud_max) & (conversion > cloud_max)] = +1 
		bothlines_status[(base < cloud_min) & (conversion < cloud_min)] = -1 
		bothlines_bullish = bothlines_status >= 0
		bothlines_bearish = bothlines_status <= 0
		
		lag_cond = np.full(closes.shape,0)
		lag_cloud_max = np.maximum(lag_cloud_a,lag_cloud_b)
		lag_cloud_min = np.minimum(lag_cloud_a,lag_cloud_b)
		lag_cond[closes > lag_cloud_max] = +1
		lag_cond[closes > lag_cloud_min] = -1	
		lag_bullish = lag_cond >= 0
		lag_bearish = lag_cond <= 0 
		
		
		#breakout status 
		#breakout_status = np.full(closes.shape,0)
		#breakout_bullish = breakout_status >= 0 #incorrect?
		#breakout_bearish = breakout_status <= 0
		
		#use smudge forward tool 
		pullback_bullish = closes < np.minimum(base,conversion)
		pullback_bearish = closes > np.maximum(base,conversion)
		
		#smudge backwards by breakout candles 
		st = SmudgeTool()
		st.smudge_length = self.breakout_candles 
		pullback_bullish = st.markup(pullback_bullish)
		pullback_bearish = st.markup(pullback_bearish)
		
		price_bullish = closes > np.maximum(base,conversion)
		price_bearish = closes < np.minimum(base,conversion)
		
		bullish = price_cloud_bullish & price_bullish & baseconv_bullish & cloud_bullish & bothlines_bullish & lag_bullish & pullback_bullish
		bearish = price_cloud_bearish & price_bearish & baseconv_bearish & cloud_bearish & bothlines_bearish & lag_bearish & pullback_bearish
		
		return bullish, bearish
		

#balanced w/l with pop stops 30, 20 
#https://www.youtube.com/watch?v=Gq1f5nfHunc
class BollingerBandsRSISetup(TradeSetup):
	
	grace_period = 50
	#365 > 180 ema = sell trend, + rsi overbought, + above bb, + next candle bearish (consider candle stick pattern eg 2 outside) 
	
	def detect(self,trade_signalling_data):
		
		bbands_op = BollingerBands()
		rsi_op = RSI()
		#rsi_op.overbought = 0.75 #remain as 0.8 to maximise profits
		#rsi_op.oversold = 0.25
		
		ema_slow_op = EMA() 
		ema_fast_op = EMA()
		ema_slow_op.period = 365
		ema_fast_op.period = 180
		
		ema_slow_res = ema_slow_op.calculate_multiple(trade_signalling_data.candlesticks)
		ema_fast_res = ema_fast_op.calculate_multiple(trade_signalling_data.candlesticks)
		
		bbands_res = bbands_op.calculate_multiple(trade_signalling_data.candlesticks)
		rsi_res = rsi_op.calculate_multiple(trade_signalling_data.candlesticks)
		
		np_candles = trade_signalling_data.np_candles
		closes = np_candles[:,:,csf.close]
		prev_closes = np.concatenate([np.full((closes.shape[0],1),np.nan),closes[:,:-1]],axis=1) 
		
		#pdb.set_trace()
		ema_cond_bullish = ema_slow_res[:,:,0] < ema_fast_res[:,:,0]
		ema_cond_bearish = ema_slow_res[:,:,0] > ema_fast_res[:,:,0]
		
		bbands_cond_bullish = closes < bbands_res[:,:,2]
		bbands_cond_bearish = closes > bbands_res[:,:,1]
		
		rsi_cond_bullish = rsi_res[:,:,0] < rsi_res[:,:,2] #0.2
		rsi_cond_bearish = rsi_res[:,:,0] > rsi_res[:,:,1] #0.8
		
		delay = DelayTool()
		delay.delay_length = 1 
		bbands_cond_bullish = delay.markup(bbands_cond_bullish)
		bbands_cond_bearish = delay.markup(bbands_cond_bearish)
		
		candle_cond_bullish = np_candles[:,:,csf.open] < np_candles[:,:,csf.close]  #replace with candle scanner? /candlestick tool 
		candle_cond_bearish = np_candles[:,:,csf.open] > np_candles[:,:,csf.close] 
		
		bullish = ema_cond_bullish & bbands_cond_bullish & rsi_cond_bullish & candle_cond_bullish
		bearish = ema_cond_bearish & bbands_cond_bearish & rsi_cond_bearish & candle_cond_bearish
		
		return bullish, bearish
		

		










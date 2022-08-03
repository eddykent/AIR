import pdb

from setups.trade_setup import *

from indicators.moving_average import EMA 
from indicators.indicator import CandleSticks, RunningHigh, RunningLow

#file for holding very simple setups 


#use with a MA anchor chart filter (eg price above 8 above 21 for buy)  - possibly use a larger moving average for same chart - perfect for testing filters 
#fanned out - 8, 13, 21. 
#price touches 8 => trigger bar. 
#count back 5 and get highest (body?) => entry
#risk = min trigger bar 
#profit = risk * 1
class ForexSignalsAnchorBar(TradeSetup):
	
	grace_period = 50
	
	@overrides(TradeSetup)
	def detect(self,candlesticks, extra= None):
		
		candles_pre = CandleSticks()
		ema8 = EMA()
		ema13 = EMA() 
		ema21 = EMA() 
		
		ema8.period = 8 
		ema13.period = 13
		ema21.period = 21 
		
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
	def get_entries(self,candlesticks,extra=None):
		high5s = RunningHigh()  
		high5s.period = 5
		
		low5s = RunningLow()
		low5s.period = 5
		
		entry_bullish = high5s.calculate_multiple(candlesticks)[:,:,0]
		entry_bearish = low5s.calculate_multiple(candlesticks)[:,:,0]
		
		return entry_bullish, entry_bearish 
		
		
	
	@overrides(TradeSetup)
	def get_tpsls_specific(self,candlesticks,extra=None):
		candles_pre = CandleSticks() 
		candles = candles_pre.calculate_multiple(candlesticks) 
		
		entry_bullish, entry_bearish = extra.entries

		stop_loss_bullish = np.abs(entry_bullish - candles[:,:,csf.low]) #the current candle is the trigger bar 
		stop_loss_bearish = np.abs(entry_bearish - candles[:,:,csf.high])
		
		stop_loss_bullish = stop_loss_bullish * 1.05 # add 5% tollerance 
		stop_loss_bearish = stop_loss_bearish * 1.05
		
		take_profit_bullish = stop_loss_bullish * 1.5 #1.5 Risk:Reward
		take_profit_bearish = stop_loss_bearish * 1.5 
		
		return (take_profit_bullish, take_profit_bearish),  (stop_loss_bullish,stop_loss_bearish)
		
		
		
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

#test for pinbars and engulfers above/below the moving average line
class ForexSignalsCandles(TradeSetup):
	pass








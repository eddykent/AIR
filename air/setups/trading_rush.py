#TODO :)
#https://tradingrush.net/trscore/

#this file contains setups that were from a youtube channel called Trading Rush. It contains the top of the list 
#setups since there isn't much point doing setups that they say don't work 
#1) MACD - https://www.youtube.com/watch?v=nmffSjdZbWQ
#2) DONCHIAN - https://www.youtube.com/watch?v=icYe2SS3-4M
#3) KNOW_SURE_THING - https://www.youtube.com/watch?v=cNFk9jvJDZo
#4) MACD_STOCH - https://www.youtube.com/watch?v=ifekTKhtCKU
#5) SCHAFF_TREND_CYCLE - https://www.youtube.com/watch?v=hZGU7TbcmkQ
#6) GOLDEN_CROSS - https://www.youtube.com/watch?v=H4ACxRjlhp4
#7) ICHIMOKU - hold (dailymotion?) 
#8) BOLLINGER_BANDS - hold - bonus since it has high winrate 
import numpy as np
import pdb

from air.utils import overrides

import air.charting.candle_stick_functions as csf

from air.indicators.momentum import MACD
from air.indicators.moving_average import EMA, WMA
from air.indicators.reversal import Stochastic
from air.indicators.trend import IchimokuCloud


from air.setups.trade_setup import TradeSetup
from air.setups.setup_tools import CrossTool, SmudgeTool,ValueLagTool



#+easy!
class MACD_TR(TradeSetup): #since there is an indicator called MACD got to have the _TR to prevent recrusive definition
	#macd & signal below 0 
	#macd cross signal up 
	#complete candle above ema200
	#sl at just below pullback of trend (rolling min)
	
	@overrides(TradeSetup)
	def indicators(self):
		self.indicator_bag = {
			'macd':MACD(),
			'ema200':EMA(200) 
		}
	
	
	@overrides(TradeSetup)
	def trigger(self,trade_signalling_data):
		np_candles = trade_signalling_data.np_candles
		macd = self.indicator_bag['macd']
		macd_result = macd(np_candles)
		macd_line = macd_result[:,:,0]
		signal_line = macd_result[:,:,1]
		macd_hist = macd_result[:,:,2]
		
		ema200 = self.indicator_bag['ema200']
		ema_result = ema200(np_candles)
		
		macd_place_bullish = (macd_line < 0) & (signal_line < 0) 
		macd_place_bearish = (macd_line > 0) & (signal_line > 0) 
		
		ema_bullish = np_candles[:,:,csf.low] > ema_result[:,:,0]
		ema_bearish = np_candles[:,:,csf.high] < ema_result[:,:,0]
		
		cx = CrossTool()
		macd_cross_bullish, macd_cross_bearish = cx.markup(macd_hist)
		
		bullish = macd_cross_bullish & ema_bullish & macd_place_bullish
		bearish = macd_cross_bearish & ema_bearish & macd_place_bearish
		
		return bullish,bearish
		
	


#-tricky 
class DONCHIAN(TradeSetup):
	#buy when upper band has changed direction passed  x candles? 
	#price above ema200
	#also check lower band made lower low? - check in window if there was a decreasing area
	#stop loss below lower band
	pass

class KNOW_SURE_THING(TradeSetup):
	#implement knowsureting indicator
	#kst crosses bove signal 
	#kst below 0
	#ema200
	#sl below recent low
	pass
	

class MACD_STOCH(TradeSetup):
	#macd cross signal up
	#stoch k line below 20 recently (within 8 candles?)
	#ema200?
	#use stock k to exit if it its overbought - was shown to be not good so can ignore 
	
	@overrides(TradeSetup)
	def indicators(self):
		self.indicator_bag = {
			'macd':MACD(),
			'ema200':EMA(200),
			'stochastic':Stochastic()
		}
	
	
	@overrides(TradeSetup)
	def trigger(self,trade_signalling_data):
		np_candles = trade_signalling_data.np_candles
		macd = self.indicator_bag['macd']
		macd_result = macd(np_candles)
		macd_hist = macd_result[:,:,2]
		
		cx = CrossTool()
		macd_cross_bullish, macd_cross_bearish = cx.markup(macd_hist)
		
		ema200 = self.indicator_bag['ema200']
		ema_result = ema200(np_candles)
		
		ema_bullish = np_candles[:,:,csf.low] > ema_result[:,:,0]
		ema_bearish = np_candles[:,:,csf.high] < ema_result[:,:,0]
		
		stoch = self.indicator_bag['stochastic']
		stoch_result = stoch(np_candles)
		
		stoch_bullish_now = stoch_result[:,:,0] < 0.2
		stoch_bearish_now = stoch_result[:,:,0] > 0.8
		
		smudge = SmudgeTool(8) #more? less? - large smudge = false signals, small = less signals
		stoch_bullish = smudge.markup(stoch_bullish_now)
		stoch_bearish = smudge.markup(stoch_bearish_now)
		
		bullish = macd_cross_bullish & ema_bullish & stoch_bullish
		bearish = macd_cross_bearish & ema_bearish & stoch_bearish
		
		return bullish, bearish


class SCHAFF_TREND_CYCLE(TradeSetup): #-might need filtering
	#implement schaff trend cycle indicator
	#signal line crosses 25 up (75 down for sell) 
	#ema200
	#SL below pullback (Recent low) 
	# improve? using flat areas
	pass

class GOLDEN_CROSS(TradeSetup): #-not brill though but uses wma for the cross
	#wma50
	#wma200
	#wma50 cross up above wma200 buy 
	
	@overrides(TradeSetup)
	def indicators(self):
		self.indicator_bag = {
			'wma50':WMA(50),
			'wma200':WMA(200)
		}
	
	@overrides(TradeSetup)
	def trigger(self,trade_signalling_data):
		
		np_candles = trade_signalling_data.np_candles
	
		wma50 = self.indicator_bag['wma50']
		wma200 = self.indicator_bag['wma200']
		
		wma50_result = wma50(np_candles)
		wma200_result = wma200(np_candles)
		
		deviation = wma50_result[:,:,0] - wma200_result[:,:,0]
		
		cx = CrossTool()
		gold_cross, death_cross = cx.markup(deviation)
		
		return gold_cross, death_cross
	
	

class ICHIMOKU(TradeSetup):
	#price above cloud
	#above 200ema
	#conversion cross base
	#price/close? above lines
	#SL just below base 
	
	@overrides(TradeSetup)
	def indicators(self):
		self.indicator_bag = {
			'ichimoku':IchimokuCloud(),
			'ema200':EMA(200)
		}
	
	def trigger(self,trade_signalling_data):
		
		np_candles = trade_signalling_data.np_candles
		
		ichimoku = self.indicator_bag['ichimoku']
		ema200 = self.indicator_bag['ema200']
		
		ichimoku_result = ichimoku(np_candles)
		ema200_result = ema200(np_candles)
		
		ema_bullish = ema200_result[:,:,0] < np_candles[:,:,csf.low]
		ema_bearish = ema200_result[:,:,0] > np_candles[:,:,csf.high]
		
		cloud_lagger = ValueLagTool(ichimoku.base_period)
		cloud_a = cloud_lagger.markup(ichimoku_result[:,:,2])
		cloud_b = cloud_lagger.markup(ichimoku_result[:,:,3])
		
		#cloud colour? 
		
		bullish_cloud = (np_candles[:,:,csf.close] > cloud_a) & (np_candles[:,:,csf.close] > cloud_b)
		bearish_cloud = (np_candles[:,:,csf.close] < cloud_a) & (np_candles[:,:,csf.close] < cloud_b)
		
		cx = CrossTool()
		cross_bullish, cross_bearish = cx.markup(ichimoku_result[:,:,0] - ichimoku_result[:,:,1])
		
		price_lines_bullish = (np_candles[:,:,csf.close] > ichimoku_result[:,:,0]) & (np_candles[:,:,csf.close] > ichimoku_result[:,:,1])
		price_lines_bearish = (np_candles[:,:,csf.close] > ichimoku_result[:,:,0]) & (np_candles[:,:,csf.close] > ichimoku_result[:,:,1])
		
		bullish = ema_bullish & bullish_cloud & price_lines_bullish & cross_bullish 
		bearish = ema_bearish & bearish_cloud & price_lines_bearish & cross_bearish 
		
		return bullish, bearish
		
		
		
	

class BOLLINGER_BANDS(TradeSetup):
	#cross below lower band
	#reversal candle stick upwards
	#200ema above
	pass
	








##
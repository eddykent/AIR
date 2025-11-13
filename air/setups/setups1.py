
import pdb

from utils import overrides


from setups.trade_setup import *
from indicators.volatility import BollingerBands, KeltnerChannel, ATR
from indicators.reversal import RSI
from indicators.trend import ADX 
from indicators.moving_average import EMA
from indicators.indicator import Typical, HeikinAshi
from indicators.volume import VWAPDaily

#https://medium.com/codex/trading-stocks-using-bollinger-bands-keltner-channel-and-rsi-in-python-980e87e8109d
class BB_KC_RSI(TradeSetup):
	
	bollinger_bands = None
	keltner_channel =  None 
	relative_strength_index = None
	
	grace_period = 60#need atleast 60 datapoints to look back on to get an accurate reading 
	
	#def __init__(self,*args,**kwargs):
	#	super().__init__(*args,**kwargs)
	
	#@overrides(TradeSetup)
	#def get_setups(self,start_date,end_date):
	#	candlesticks, available_instruments = self.get_candlestick_data(start_date,end_date,block=True)
	#	timeline = self.get_timeline(candlesticks)
	#	self.relative_strength_index = RSI()
	#	self.bollinger_bands = BollingerBands()
	#	self.keltner_channel = KeltnerChannel()
	#	
	#	#parameter setups for each indicator
	#	self.relative_strength_index.oversold = 0.3
	#	self.relative_strength_index.overbought = 0.7
	#	
	#	rsi_values = self.relative_strength_index.calculate_multiple(candlesticks)  #missing 1! :/
	#	bollinger_bands_values = self.bollinger_bands.calculate_multiple(candlesticks)
	#	keltner_channel_values = self.keltner_channel.calculate_multiple(candlesticks)
	#	
	#	#if BB is contained in KC, 
	#	#	if RSI is below 30 buy. if RSI is above 70, sell. 
	#	
	#	bb_upper = self.bollinger_bands.channel_keys.get('UPPER')
	#	bb_lower = self.bollinger_bands.channel_keys.get('LOWER')
	#	
	#	kc_upper = self.keltner_channel.channel_keys.get('UPPER')
	#	kc_lower = self.keltner_channel.channel_keys.get('LOWER')
	#	
	#	rsi_rsi = self.relative_strength_index.channel_keys.get('RSI')
	#	rsi_overbought = self.relative_strength_index.channel_keys.get('OVERBOUGHT')
	#	rsi_oversold = self.relative_strength_index.channel_keys.get('OVERSOLD')
	#	
	#	bbukc = (bollinger_bands_values[:,:,bb_upper] < keltner_channel_values[:,:,kc_upper])
	#	bblkc = (bollinger_bands_values[:,:,bb_lower] > keltner_channel_values[:,:,kc_lower])
	#	
	#	rsi_buy = rsi_values[:,:,rsi_rsi] < rsi_values[:,:,rsi_oversold]
	#	rsi_sell = rsi_values[:,:,rsi_rsi] > rsi_values[:,:,rsi_overbought]
	#	
	#	buy_signals = bbukc & bblkc & rsi_buy     #refactor 
	#	sell_signals = bbukc & bblkc & rsi_sell
	#	
	#	
	#	
	#	#need to set up the TP and SL values! 
	#	average_true_range = ATR() #use for setting TP and SL - perhaps pull this into its own function 
	#	average_true_range_values = average_true_range.calculate_multiple(candlesticks)
	#	
	#	tp_factor = 5
	#	sl_factor = 3
	#	
	#	tp_distances = tp_factor * average_true_range_values[:,:,0]
	#	sl_distances = sl_factor * average_true_range_values[:,:,0]
	#
	#	typical = Typical()
	#	typical_values = typical.calculate_multiple(candlesticks) #could be used for entry?
	#	entry_prices = typical_values[:,:,0]
	#	
	#	trade_signals = []
	#	
	#	#export these? would be much faster for any further computation such as filtering...
	#	buy_coords = np.stack(np.where(buy_signals),axis=1)
	#	sell_coords = np.stack(np.where(sell_signals),axis=1)
	#	
	#	#now build the signals!  --could go in its own function?
	#	for (instrument_index,timeline_index) in buy_coords:
	#		if timeline[timeline_index] < start_date:
	#			continue
	#		the_date = timeline[timeline_index]
	#		instrument = available_instruments[instrument_index]
	#		strategy_ref = self.__class__.__name__
	#		direction = TradeDirection.BUY
	#		entry = None #consider entry_prices[instrument_index,timeline_index]
	#		take_profit_distance = tp_distances[instrument_index,timeline_index]
	#		stop_loss_distance = sl_distances[instrument_index,timeline_index]
	#		
	#		ts = TradeSignal.from_full(the_date,instrument,strategy_ref,direction,entry,take_profit_distance,stop_loss_distance)
	#		trade_signals.append(ts)
	#	
	#	for (instrument_index,timeline_index) in sell_coords:
	#		if timeline[timeline_index] < start_date:
	#			continue
	#		the_date = timeline[timeline_index]
	#		instrument = available_instruments[instrument_index]
	#		strategy_ref = self.__class__.__name__
	#		direction = TradeDirection.SELL
	#		entry = None #consider entry_prices[instrument_index,timeline_index]
	#		take_profit_distance = tp_distances[instrument_index,timeline_index]
	#		stop_loss_distance = sl_distances[instrument_index,timeline_index]
	#		
	#		ts = TradeSignal.from_full(the_date,instrument,strategy_ref,direction,entry,take_profit_distance,stop_loss_distance)
	#		trade_signals.append(ts)
	#	
	#	return trade_signals
	
	
	@overrides(TradeSetup)
	def detect(self, trade_signalling_data):
		
		self.relative_strength_index = RSI()
		self.bollinger_bands = BollingerBands()
		self.keltner_channel = KeltnerChannel()
		
		#parameter setups for each indicator
		self.relative_strength_index.oversold = 0.3
		self.relative_strength_index.overbought = 0.7
		
		candlesticks = trade_signalling_data.candlesticks
		
		rsi_values = self.relative_strength_index.calculate_multiple(candlesticks)  #missing 1! :/
		bollinger_bands_values = self.bollinger_bands.calculate_multiple(candlesticks)
		keltner_channel_values = self.keltner_channel.calculate_multiple(candlesticks)
		
		#if BB is contained in KC, 
		#	if RSI is below 30 buy. if RSI is above 70, sell. 
		
		bb_upper = self.bollinger_bands.channel_keys.get('UPPER')
		bb_lower = self.bollinger_bands.channel_keys.get('LOWER')
		
		kc_upper = self.keltner_channel.channel_keys.get('UPPER')
		kc_lower = self.keltner_channel.channel_keys.get('LOWER')
		
		rsi_rsi = self.relative_strength_index.channel_keys.get('RSI')
		rsi_overbought = self.relative_strength_index.channel_keys.get('OVERBOUGHT')
		rsi_oversold = self.relative_strength_index.channel_keys.get('OVERSOLD')
		
		bbukc = (bollinger_bands_values[:,:,bb_upper] < keltner_channel_values[:,:,kc_upper])
		bblkc = (bollinger_bands_values[:,:,bb_lower] > keltner_channel_values[:,:,kc_lower])
		
		rsi_buy = rsi_values[:,:,rsi_rsi] < rsi_values[:,:,rsi_oversold]
		rsi_sell = rsi_values[:,:,rsi_rsi] > rsi_values[:,:,rsi_overbought]
		
		buy_signals = bbukc & bblkc & rsi_buy     #refactor 
		sell_signals = bbukc & bblkc & rsi_sell	
		
		return buy_signals, sell_signals 

#https://www.youtube.com/watch?v=vBM0imYSzxI
class ADX_EMA_RSI(TradeSetup):

	#rsi(3,20,80), adx(5,30), ema(50)
	
	grace_period = 60#need atleast 60 datapoints to look back on to get an accurate reading 
	
	#def __init__(self,*args,**kwargs):
	#	super().__init__(*args,**kwargs)
	
	@overrides(TradeSetup)
	def detect(self,trade_signalling_data):
		adx = ADX()
		rsi = RSI() 
		ema = EMA() 
		
		adx.period = 5
		
		rsi.period = 3
		rsi.overbought = 0.8 
		rsi.oversold = 0.2
		#rsi.candle_channel = csf.close
		
		ema.period = 50
		#ema.candle_channel = csf.close
		
		candlesticks = trade_signalling_data.candlesticks 
		
		adx_result = adx.calculate_multiple(candlesticks)
		rsi_result = rsi.calculate_multiple(candlesticks)
		ema_result = ema.calculate_multiple(candlesticks)[:,:,0]
		
		adx_mask = adx_result > 30 
		
		rsi_buy = rsi_result[:,:,0] < rsi_result[:,:,2]# could change to 0.2
		rsi_sell = rsi_result[:,:,0] > rsi_result[:,:,1] #could change to 0.8
		
		adx_filter = adx_result[:,:,0] > 30  #adx must be larger than 30 
		
		ema_buy = ema_result < candlesticks[:,:,csf.low]
		ema_sell = ema_result > candlesticks[:,:,csf.high]
		
		buy_signals = ema_buy & adx_filter & rsi_buy  #rafactgor
		sell_signals = ema_sell & adx_filter & rsi_sell
	
		
		return buy_signals, sell_signals
		#return self.generate_using_atr(candlesticks,available_instruments,start_date,buy_signals,sell_signals,tp_factor=4,sl_factor=4)
		
		
#reports positive W/L on 3/2 TPSL but rare & possible divergence bug
class HA_VWAP_RSI_DIVERGENCE(TradeSetup):
	
	grace_period = 50
	
	@overrides(TradeSetup)
	def detect(self,trade_signalling_data):
		
		vwap = VWAPDaily()
		heikinashi = HeikinAshi()
		rsi = RSI()
		typical = Typical()
		
		candlestickvolumes = trade_signalling_data.candlesticks
		
		vw_result = vwap.calculate_multiple(candlestickvolumes)
		ha_result = heikinashi.calculate_multiple(candlestickvolumes)
		rsi_result = rsi.calculate_multiple(candlestickvolumes)
		typical_result = typical.calculate_multiple(candlestickvolumes)
		
		div_tool = MomentumDivergenceTool()
		#config here
		div_tool.set_signals(typical_result[:,:,0],rsi_result[:,:,0])
		div_result = div_tool.detect()
		
		#conditions - bullish
		bullish_ha = ha_result[:,:,0] < ha_result[:,:,3]
		low_ha = ha_result[:,:,2] >= ha_result[:,:,3] 
		
		vwap_b = ha_result[:,:,0] >= vw_result[:,:,0]
		div_b = div_result > 0 
		
		#conditions - bearish 
		bearish_ha = ha_result[:,:,0] > ha_result[:,:,3]
		high_ha = ha_result[:,:,1] <= ha_result[:,:,0]
		
		vwap_s = ha_result[:,:,0] <= vw_result[:,:,0]
		div_s = div_result < 0
		
		
		buy_signals = bullish_ha &  low_ha & div_b & vwap_b #  & div_b
		sell_signals = bearish_ha & high_ha & div_s & vwap_s # & div_s
		
		return buy_signals, sell_signals 		
		
		
		
		










































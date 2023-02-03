

import numpy as np 

from setups.trader_dna import * 
from setups.trade_pro import * 
from setups.trading_rush import * 

trader_dna_list = [
	TripleRSIADX,
	DoubleCCICross,
	RSI_MACD_STOCH,
	MACD123,
	ZeroLagEMA,
	MACD_DOUBLE_DIV,
]

trade_pro_list = [
	MACD_MFT, 
	RSIS_EMA_X, 
	RSIS_EMA_1, 
	#HISTOGRAM, #not implemented
	CMF_MACD_ATR,
	ENGULFING,
	SIMPLE_MONEY
]

trading_rush_list = [
	MACD_TR,
	#DONCHIAN,
	#KNOW_SURE_THING,
	MACD_STOCH,
	#SCHAFF_TREND_CYCLE,
	GOLDEN_CROSS,
	ICHIMOKU,
	#BOLLINGER_BANDS
]

third_party_list = trader_dna_list + trade_pro_list + trading_rush_list

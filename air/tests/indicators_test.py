
import datetime 

from configuration import Configuration 
from data.tools.cursor import Database, DataComposer

from utils import ListFileReader
from indicators.indicator import * 
from indicators.moving_average import *
from indicators.trend import *
from indicators.reversal import * 
from charting.candle_stick_pattern import CandleStickPattern
from charting.chart_viewer import PlotlyChartPainter

import numpy as np

lfr = ListFileReader()
currencies = lfr.read('fx_pairs/currencies.txt')
fx_pairs = lfr.read('fx_pairs/fx_mains.txt')

the_date = datetime.datetime(2022,5,20,12,0)

candles = []
with Database(commit=False, cache=False) as cursor: 
	composer = DataComposer(cursor) #.candles(params).call()...
	#composer.call('get_candles_volumes_from_currencies',{'currencies':currencies,'this_date':the_date,'days_back':100,'chart_resolution':15})
	composer.call('get_candles_from_currencies',{'currencies':currencies,'this_date':the_date,'days_back':50,'chart_resolution':15})

	candle_result = composer.result(as_json=True)
	candles = composer.as_candles(candle_result,fx_pairs)


#OurIndicator = SMA
#OurIndicator = BollingerBands
#OurIndicator = STDDEV
#OurIndicator = KeltnerChannel
#OurIndicator = MultiMovingAverage
#OurIndicator = MACD #needs special draw_snapshot()
#OurIndicator = RSI #needs special draw_snapshot
#OurIndicator = ADX
#OurIndicator = Accelerator
#OurIndicator = Momentum
#OurIndicator = Aroon
#OurIndicator = PPO
#OurIndicator = ParabolicSAR
#OurIndicator = IchimokuCloud
#OurIndicator = RVI
#OurIndicator = CCI
#OurIndicator = DonchianChannel
#OurIndicator = WilliamsPercentRange
OurIndicator = MassIndex
#OurIndicator = SuperTrend
#OurIndicator = TEMA



indicator = OurIndicator()

candle_streams = np.array([candles[fx] for fx in fx_pairs])
#results = indicator.calculate_multiple(candle_streams)


#pdb.set_trace()
this_view = chv.ChartView()
this_view.draw_candles(candle_streams[0])
indicator.candle_type = CandleType.CANDLE
indicator_view = indicator.draw_snapshot(candle_streams,0)
this_view += indicator_view


pcp = PlotlyChartPainter()
#pcp.paint(indicator_view)
pcp.paint(this_view)
pcp.show()

#pcp = PlotlyChartPainter()

#pcp.show()






















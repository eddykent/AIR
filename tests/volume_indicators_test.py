
import datetime 

from utils import Database, DataComposer, Configuration, ListFileReader
from indicators.volume import * 
import charting.chart_viewer as chv


lfr = ListFileReader()
currencies = lfr.read('fx_pairs/currencies.txt')
fx_pairs = lfr.read('fx_pairs/fx_mains.txt')

	
the_date = datetime.datetime(2022,5,20,12,0)



#OurIndicator = VWAP
#OurIndicator = BidAskVWAP
#OurIndicator = ClientSentimentRatio
OurIndicator = ClientSentiment



indicator = OurIndicator()

candles = []
with Database(commit=False, cache=False) as cursor: 
	composer = DataComposer(cursor) #.candles(params).call()...
	#composer.call('get_candles_volumes_from_currencies',{'currencies':currencies,'this_date':the_date,'days_back':100,'chart_resolution':15})
	composer.call('get_candles_volumes_from_currencies',{'currencies':currencies,'this_date':the_date,'days_back':50,'chart_resolution':60})

	candle_result = composer.result(as_json=True)
	candles = composer.as_candles_volumes(candle_result,fx_pairs)

#indicator.normalisation_window = 100
#indicator.period = 5
#indicator.diff = 0


candle_streams = [candles[fx] for fx in fx_pairs]
results = indicator.calculate_multiple(candle_streams)


#pdb.set_trace()
this_view = chv.ChartView()
if indicator.candle_sticks:
	this_view.draw_candles(candle_streams[0])
indicator_view = indicator.draw_snapshot(candle_streams[0])
this_view += indicator_view


pcp = chv.PlotlyChartPainter()
#pcp.paint(indicator_view)
pcp.paint(this_view)
pcp.show()

#pcp = PlotlyChartPainter()

#pcp.show()






















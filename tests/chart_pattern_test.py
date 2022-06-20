




import datetime 

from utils import Database, DataComposer, Configuration, ListFileReader
from charting.chart_pattern import SupportAndResistance, PivotPoints
from charting.match_pattern import MatchPatternInstance
from charting.trend_pattern import SymmetricTriangle
import charting.chart_viewer as chv

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


#chart_pattern = SupportAndResistance()
#chart_pattern = PivotPoints()
#chart_pattern  = MatchPatternInstance()
chart_pattern = SymmetricTriangle()


instrument_index = 2

candle_streams = [candles[fx] for fx in fx_pairs]
#chart_pattern.set_haystack(candle_streams)

results = chart_pattern.calculate_multiple(candle_streams)

this_view = chv.ChartView()
this_view.draw_candles(candle_streams[2])
np_candles, _ = chart_pattern._construct(candle_streams)

chart_view = chart_pattern.draw_snapshot(np_candles,snapshot_index=[-1],instrument_index=2)
this_view += chart_view

pcp = chv.PlotlyChartPainter()
#pcp.paint(indicator_view)
pcp.paint(this_view)
pcp.show()






















import datetime 

from utils import Database, Configuration, ListFileReader
from indicators.indicator import * 
from charting.candle_stick_pattern import CandleStickPattern
from charting.chart_viewer import PlotlyChartPainter

cur = Database() 
query = ''

with open('queries/candle_stick_selector.sql','r') as f:
	query = f.read()

lfr = ListFileReader()
currencies = lfr.read('fx_pairs/currencies.txt')
fx_pairs = lfr.read('fx_pairs/fx_mains.txt')

	
the_date = datetime.datetime(2022,3,4,12,0)
params = {
	'chart_resolution':60,
	'the_date':the_date,
	'hour':the_date.hour,
	'days_back':20,
	'candle_offset':0,
	'currencies':currencies		
}
cur.execute(query,params)
database_response = cur.fetchall()


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
#OurIndicator = DonchianChannel
#OurIndicator = WilliamsPercentRange
OurIndicator = SuperTrend



indicator = OurIndicator()

candle_streams = [CandleStickPattern.to_candles(database_response,instrument) for instrument in fx_pairs]
results = indicator.calculate_multiple(candle_streams)


#pdb.set_trace()

this_view = chv.ChartView()
this_view.draw_candles(candle_streams[0])
indicator_view = indicator.draw_snapshot(candle_streams[0])
this_view += indicator_view


pcp = PlotlyChartPainter()
#pcp.paint(indicator_view)
pcp.paint(this_view)
pcp.show()

#pcp = PlotlyChartPainter()

#pcp.show()






















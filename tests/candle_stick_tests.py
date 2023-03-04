import pickle
import psycopg2
import datetime

from plotly import graph_objects as chart
import pdb


from configuration import Configuration
from data.tools.cursor import Database

import charting.candle_stick_functions as csf
from charting.candle_stick_pattern import * #grab all patterns 
import charting.chart_viewer as chv



from trade_schedule import TradeSchedule
from utils import ListFileReader, TimeZipper

config = Configuration()

cur = Database()


the_date = datetime.datetime(2022,3,10,12,0)

lfr = ListFileReader()
currencies = lfr.read('fx_pairs/currencies.txt')
fx_pairs = lfr.read('fx_pairs/fx_mains.txt')


query = ''
with open('queries/candle_stick_selector.sql','r') as f:
	query = f.read()

params = {
	'chart_resolution':240,
	'the_date':the_date,
	'candle_offset':120,
	'hour':the_date.hour,
	'days_back':150,
	'currencies':currencies
}

cur.execute(query,params)

candlestreams = cur.fetchcandles(fx_pairs)
candles = [candlestreams[fx] for fx in fx_pairs]

candle_pattern = MorningEveningStars()
#candle_pattern = Engulfing()
#candle_pattern = SoldiersAndCrows()
#candle_pattern = MorningEveningStars()
#candle_pattern = Harami()
#candle_pattern = ThreeLineStrikes()

pattern_result = candle_pattern.calculate_multiple(candles)
#pdb.set_trace()

#draw engulfer indicators
candle_pattern_points = []
pattern_traces = []


eurjpy_candles = candlestreams['EUR/JPY']
this_view = candle_pattern.draw_snapshot(eurjpy_candles)
this_view.draw_candles(eurjpy_candles)

chart_painter = chv.PlotlyChartPainter()
chart_painter.paint(this_view)
chart_painter.show()



##REFACTOR - turn the loop into one single dataset and then draw it as traces on the chart
# pull whatever you need out of this then delete it all 
#
#andlestick_chart_data = chart.Candlestick(
#	#x=x,
#	open=[candle[csf.open] for candle in candles],
#	high=[candle[csf.high] for candle in candles],
#	low=[candle[csf.low] for candle in candles],
#	close=[candle[csf.close] for candle in candles],
#	name='EUR/USD'
#
#andlestick_chart_data.increasing.fillcolor = 'rgba(0,100,255,0.9)'
#andlestick_chart_data.increasing.line.color = 'rgba(20,150,255,0.9)'
#andlestick_chart_data.decreasing.fillcolor = 'rgba(255,70,70,0.9)'
#andlestick_chart_data.decreasing.line.color = 'rgba(255,20,50,0.9)'
#
#for i,e in enumerate(pattern_result):
#	if e != 0:		
#		(x,y,arrow_x,arrow_y,these_candles,these_indexs) = candle_pattern.draw_snapshot(i,candles) #maybe better way of doing this than sending hugh tuples one by one
#		highlight_box_trace = chart.Scatter(
#			x=x,
#			y=y,
#			fill='toself',
#			mode='lines',
#			text = ("Bullish " if e > 0 else "Bearish ") + type(candle_pattern).__name__
#		)
#		highlight_box_trace.line.width = 1
#		highlight_box_trace.line.color = 'rgb(100,100,100)'
#		highlight_box_trace.fillcolor='rgba(255,0,0,0.3)' if e < 0 else 'rgba(0,255,0,0.3)'
#		
#		highlight_border_trace = chart.Candlestick(
#			x=these_indexs,
#			open=[candle[csf.open] for candle in these_candles],
#			high=[candle[csf.high] for candle in these_candles],
#			low=[candle[csf.low] for candle in these_candles],
#			close=[candle[csf.close] for candle in these_candles],
#		)
#		#keep fill as same
#		highlight_border_trace.increasing.fillcolor = candlestick_chart_data.increasing.fillcolor
#		highlight_border_trace.decreasing.fillcolor = candlestick_chart_data.decreasing.fillcolor
#		
#		#add nice borders
#		if e < 0:
#			highlight_border_trace.increasing.line.color = 'rgb(255,0,0)'
#			highlight_border_trace.decreasing.line.color = 'rgb(255,0,0)'
#		elif e > 0:
#			highlight_border_trace.increasing.line.color = 'rgb(0,0,255)'
#			highlight_border_trace.decreasing.line.color = 'rgb(0,0,255)'
#		
#		highlight_border_trace.increasing.line.width = 1
#		highlight_border_trace.decreasing.line.width = 1
#		
#		#highlight_box_trace.text = ['BULLISH'] if e > 0 else ['BEARISH']
#		#highlight_box_trace.hovertemplate = "%{text}"
#		
#		pattern_traces.append(highlight_box_trace)
#		pattern_traces.append(highlight_border_trace)
#		
#
#fig = chart.Figure(data=[candlestick_chart_data])
#for pt in pattern_traces:	
#	fig.add_trace(pt)
#fig.show()

























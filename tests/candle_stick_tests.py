import pickle
import psycopg2
import datetime

from plotly import graph_objects as chart
import pdb

import charting.candle_stick_functions as csf
from charting.candle_stick_pattern import * #grab all patterns 

from trade_schedule import TradeSchedule
from utils import Configuration, ListFileReader, TimeZipper

config = Configuration()
con = psycopg2.connect(config.database_connection_string())
cur = con.cursor()

the_date = datetime.datetime(2022,1,26,12,0)

query = ''
with open('queries/candle_stick_selector.sql','r') as f:
	query = f.read()

params = {
	'chart_resolution':240,
	'the_date':the_date,
	'hour':the_date.hour,
	'days_back':150,
	'currencies':['EUR','USD']
}

cur.execute(query,params)
database_response = cur.fetchall()
candles = CandleStickPattern.to_candles(database_response,'EUR/USD')
#candle_pattern = PinBar()
#candle_pattern = Engulfing()
#candle_pattern = SoldiersAndCrows()
#candle_pattern = MorningEveningStars()
candle_pattern = Harami()

pattern_result = candle_pattern.detect(candles)
#pdb.set_trace()

candlestick_chart_data = chart.Candlestick(
	#x=x,
	open=[candle[csf.open] for candle in candles],
	high=[candle[csf.high] for candle in candles],
	low=[candle[csf.low] for candle in candles],
	close=[candle[csf.close] for candle in candles],
	name='EUR/USD'
)
candlestick_chart_data.increasing.fillcolor = 'rgba(0,100,255,0.9)'
candlestick_chart_data.increasing.line.color = 'rgba(20,150,255,0.9)'
candlestick_chart_data.decreasing.fillcolor = 'rgba(255,70,70,0.9)'
candlestick_chart_data.decreasing.line.color = 'rgba(255,20,50,0.9)'

#draw engulfer indicators
candle_pattern_points = []
pattern_traces = []

##REFACTOR - turn the loop into one single dataset and then draw it as traces on the chart
for i,e in enumerate(pattern_result):
	if e != 0:		
		(x,y,arrow_x,arrow_y,these_candles,these_indexs) = candle_pattern.draw_snapshot(i,candles) #maybe better way of doing this than sending hugh tuples one by one
		highlight_box_trace = chart.Scatter(
			x=x,
			y=y,
			fill='toself',
			mode='lines',
			text = ("Bullish " if e > 0 else "Bearish ") + type(candle_pattern).__name__
		)
		highlight_box_trace.line.width = 1
		highlight_box_trace.line.color = 'rgb(100,100,100)'
		highlight_box_trace.fillcolor='rgba(255,0,0,0.3)' if e < 0 else 'rgba(0,255,0,0.3)'
		
		highlight_border_trace = chart.Candlestick(
			x=these_indexs,
			open=[candle[csf.open] for candle in these_candles],
			high=[candle[csf.high] for candle in these_candles],
			low=[candle[csf.low] for candle in these_candles],
			close=[candle[csf.close] for candle in these_candles],
		)
		#keep fill as same
		highlight_border_trace.increasing.fillcolor = candlestick_chart_data.increasing.fillcolor
		highlight_border_trace.decreasing.fillcolor = candlestick_chart_data.decreasing.fillcolor
		
		#add nice borders
		if e < 0:
			highlight_border_trace.increasing.line.color = 'rgb(255,0,0)'
			highlight_border_trace.decreasing.line.color = 'rgb(255,0,0)'
		elif e > 0:
			highlight_border_trace.increasing.line.color = 'rgb(0,0,255)'
			highlight_border_trace.decreasing.line.color = 'rgb(0,0,255)'
		
		highlight_border_trace.increasing.line.width = 1
		highlight_border_trace.decreasing.line.width = 1
		
		#highlight_box_trace.text = ['BULLISH'] if e > 0 else ['BEARISH']
		#highlight_box_trace.hovertemplate = "%{text}"
		
		pattern_traces.append(highlight_box_trace)
		pattern_traces.append(highlight_border_trace)
		

fig = chart.Figure(data=[candlestick_chart_data])
for pt in pattern_traces:	
	fig.add_trace(pt)
fig.show()

pdb.set_trace()
























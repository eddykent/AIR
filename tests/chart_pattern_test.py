#this file shows all the correlations of the pairs on a 2d plane. 
#points that are close together are strongly correlated
#to collect together points by weakest correlation, use 1.0 - distance

import numpy 
import psycopg2
import datetime

from sklearn import manifold
from plotly import graph_objects as chart

import pdb

from charting import candle_stick_functions as csf
from utils import Configuration, ListFileReader
from charting.chart_pattern import * #grab all patterns 


config = Configuration()
con = psycopg2.connect(config.database_connection_string())
cur = con.cursor()

lfr = ListFileReader()
currencies = lfr.read('fx_pairs/currencies.txt')
fx_pairs = lfr.read('fx_pairs/fx_mains.txt')
sorted(fx_pairs)

the_date = datetime.datetime(2022,2,4,16,0)

parameters = {
	'chart_resolution':60,
	'the_date':the_date,
	'hour':the_date.hour,
	'days_back':20,
	'currencies':currencies	
}

query = ''
with open('queries/candle_stick_selector.sql','r') as f:
	query = f.read()

cur.execute(query,parameters)
database_response = cur.fetchall()
chart_pattern = SupportAndResistance()
#chart_pattern.bounce_size = 2
chart_pattern.memory_window = 250
pair = 'GBP/USD'
candle_stream = chart_pattern.to_candles(database_response,pair)



result = chart_pattern.detect(candle_stream) #this calls _get_levels
#levels = chart_pattern._get_levels(len(candle_stream)-5)


candlestick_chart_data = chart.Candlestick(
	#x=x,
	open=[candle[csf.open] for candle in candle_stream],
	high=[candle[csf.high] for candle in candle_stream],
	low=[candle[csf.low] for candle in candle_stream],
	close=[candle[csf.close] for candle in candle_stream],
	name=pair
)

fig = chart.Figure(data=[candlestick_chart_data])


def show_levels(_levels):
		
	xs = []
	ys = []
	highlight_xs = []
	highlight_ys = []
	
	#for level in _levels:
	
		#if "{:.4f}".format(level.value) != '1.3246':
		#	continue
	
		#fig.add_hline(l)
		#x,y = level.draw() #need to figure out highlight for green and red
		#xs += x + [None]
		#ys += y + [None]
		#highlight_xs = highlight_x
		#highlight_ys = highlight_y
		#xs += [None]
		#ys += [None]
		#highlight_xs = [None]
		#highlight_ys = [None]
		
	#level_line = chart.Scatter(
	#	x=xs,
	#	y=ys,
	#	mode='lines'
	#) #use this instead to draw lines - works perfectly! 
	#level_line.line.color = '#000000'
	#level_line.line.width = 1
	
	all_xmins,all_ymins,all_xmaxs,all_ymaxs = super(TriangleBreakouts,chart_pattern).draw()
	
	xmins,ymins, xmaxs,ymaxs = chart_pattern.draw_snapshot(113)
	
	all_points = chart.Scatter(
		x=all_xmins+all_xmaxs,
		y=all_ymins+all_ymaxs,
		mode='markers',
		marker={'color':'#0000ff'}
	)
	
	min_points = chart.Scatter(
		x=xmins,
		y=ymins,
		mode='markers',
		marker={'color':'#00ff00'}
	)
	max_points = chart.Scatter(
		x=xmaxs,
		y=ymaxs,
		mode='markers',
		marker={'color':'#ff0000'}
	)
	
	#fig.add_trace(level_line)
	fig.add_trace(all_points)
	fig.add_trace(min_points)
	fig.add_trace(max_points)
	
	fig.show()


#def show_actions(_actions):	

	
key_levels, level_fitness_tab = chart_pattern._determine(200,candle_stream,chart_pattern._get_extremes(200))
pdb.set_trace()
#actions = chart_pattern._determine(200,candle_stream,chart_pattern._get_extremes(200))
level_fitness_tab = sorted(level_fitness_tab,key=lambda lft:lft[2],reverse=True)

show_levels(key_levels)

#print(actions['1.3246'])

#for a in activities:
#	print(a)
#show_actions(actions)

















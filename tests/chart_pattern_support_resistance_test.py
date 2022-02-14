

##this is a test file for chart patterns. In particular, this one was used to test the support and resistance pattern 
##This file also has plenty of material that can be used when creating a chart viewer 

import numpy 
import psycopg2
import datetime

from sklearn import manifold
from plotly import graph_objects as chart

import pdb
import time


assert __name__ != "__main__", "You must run tests through the run_test.py hoister"

from charting import candle_stick_functions as csf
from utils import Configuration, ListFileReader
from charting.chart_pattern import * #grab all patterns 
from charting.trending_pattern import * #grab all advanced patterns too 


config = Configuration()
con = psycopg2.connect(config.database_connection_string())
cur = con.cursor()

lfr = ListFileReader()
currencies = lfr.read('fx_pairs/currencies.txt')
fx_pairs = lfr.read('fx_pairs/fx_mains.txt')
sorted(fx_pairs)

the_date = datetime.datetime(2022,2,14,18,0)

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

#OurChartPattern = TrendingPattern
#OurChartPattern = TriangleBreakout
#OurChartPattern = FallingTriangleBreakout
#OurChartPattern = RisingTriangleBreakout
#OurChartPattern = WedgeBreakout  
#OurChartPattern = ApproximateChannelBreakout
#OurChartPattern = SupportAndResistanceAction
OurChartPattern = SupportAndResistance
#OurChartPattern = ParallelChannelBreakout



#pdb.set_trace()


chart_pattern = OurChartPattern()

#chart_pattern = TriangleBreakout()

#chart_pattern.bounce_size = 2
#chart_pattern.memory_window = 250
pair = 'GBP/USD'
candle_stream = chart_pattern.to_candles(database_response,pair)


t0 = time.time()
result = chart_pattern.detect(candle_stream) #this calls _get_levels
#levels = chart_pattern._get_levels(len(candle_stream)-5)
t1 = time.time()

print(f"Drawing time for {chart_pattern.__class__.__name__} was {t1-t0}")

fig = chart.Figure(data=[])





def show_candles(candles):
	candlestick_chart_data = chart.Candlestick(
		#x=x,
		open=[candle[csf.open] for candle in candles],
		high=[candle[csf.high] for candle in candles],
		low=[candle[csf.low] for candle in candles],
		close=[candle[csf.close] for candle in candles],
		name=pair
	)
	fig.add_trace(candlestick_chart_data)




def show_levels(_levels,snapshot_index):
		
	xs = []
	ys = []
	highlight_xs = []
	highlight_ys = []
	
	for level in _levels:
	
		#if "{:.4f}".format(level.value) != '1.3246':
		#	continue
	
		#fig.add_hline(l)
		x,y = level.draw() #need to figure out highlight for green and red
		xs += [x[0],snapshot_index] + [None]
		ys += y + [None]
		#highlight_xs = highlight_x + [None]
		#highlight_ys = highlight_y + [None]
		
		
	level_line = chart.Scatter(
		x=xs,
		y=ys,
		mode='lines'
	) #use this instead to draw lines - works perfectly! 
	level_line.line.color = '#aaaaaa'
	level_line.line.width = 1
	
	
	xmins,ymins, xmaxs,ymaxs = chart_pattern.draw_snapshot(snapshot_index) 
	
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
	
	fig.add_trace(level_line)
	fig.add_trace(min_points)
	fig.add_trace(max_points)


def show_points(points,colour='#0044ff'):
	
	all_points = chart.Scatter(
		x=points[0],
		y=points[1],
		mode='markers',
		marker={'color':'#0000ff'}
	)
	fig.add_trace(all_points)
	
	
def show_best_levels(level_fitness_tab, snapshot_index):
	
	colors = ['red','blue','yellow']

	for i in range(0,3):	#first, second and third best levels 
		level = level_fitness_tab[i][0]
		x,y=  level.draw()
		level_line = chart.Scatter(
			x=[x[0],snapshot_index],
			y=y,
			mode='lines'
		) #use this instead to draw lines - works perfectly! 
		level_line.line.color = colors[i]
		level_line.line.width = 2
		
		fig.add_trace(level_line)

def show_trendline(trendline,direction):
	
	trend_line = chart.Scatter(
		x=trendline[0],
		y=trendline[1],
		mode='lines'
	)
	trend_line.line.color = 'green' if direction == 1 else 'red' if direction == -1 else 'black'
	trend_line.line.width = 2
	
	fig.add_trace(trend_line)
	

def show_snapshot_position(snapshot_index,candles):
	
	chigh = csf.highest_body(candles)
	clow = csf.lowest_body(candles)
	#crange = chigh - clow
	#chigh +=  0.05 * crange
	#clow += 0.05 * crange
	snap_line = chart.Scatter(
		x=[snapshot_index,snapshot_index],
		y=[clow,chigh],
		mode='lines'
	) #use this instead to draw lines - works perfectly! 
	snap_line.line.color = 'black'
	snap_line.line.width = 1

	fig.add_trace(snap_line)


def show_result(result,candles)	:
	
	bull_region_x = []
	bull_region_y = [] 
	
	bear_region_x = []
	bear_region_y = [] 
	
	chigh = csf.highest_body(candles)
	clow = csf.lowest_body(candles)
	crange = chigh - clow
	#chigh +=  0.05 * crange
	#clow += 0.05 * crange
	
	for i,r in enumerate(result):
		if i == 0:
			continue
		if r < 0:
			bear_region_x += [i-1,i,i,i-1,i-1,None]
			bear_region_y += [chigh,chigh,clow,clow,chigh,None]
		if r > 0:
			bull_region_x += [i-1,i,i,i-1,i-1,None]
			bull_region_y += [chigh,chigh,clow,clow,chigh,None]
	bear_region = chart.Scatter(
		x=bear_region_x,
		y=bear_region_y,
		mode='lines',
		fill='toself',
		fillcolor="rgba(255,0,0,0.1)",
		name="BEARISH",
		line={'width':0}
	)
	bull_region = chart.Scatter(
		x=bull_region_x,
		y=bull_region_y,
		mode='lines',
		fill='toself',
		fillcolor="rgba(0,255,0,0.1)",
		name="BULLISH",
		line={'width':0}
	)
	fig.add_trace(bear_region)
	fig.add_trace(bull_region)
	
	
snapshot_index = len(result) - 1

def draw_all(snapshot_index):
	
	#key_levels, level_fitness_tab = chart_pattern._get_key_level_information(snapshot_index,candle_stream,chart_pattern._get_extremes(snapshot_index))

	#actions = chart_pattern._determine(200,candle_stream,chart_pattern._get_extremes(200))
	#level_fitness_tab = sorted(level_fitness_tab,key=lambda lft:lft[2],reverse=True)
	t0 = time.time()
	fig.data = []
	
	show_result(result,candle_stream)
	show_candles(candle_stream)
	show_snapshot_position(snapshot_index,candle_stream)
	
	
	extremes = chart_pattern._get_extremes(snapshot_index)
	points_x = [e.index for e in extremes]
	points_y = [e.value for e in extremes]
	show_points([points_x,points_y])
	#show_levels(key_levels,snapshot_index)
	#show_best_levels(level_fitness_tab,snapshot_index)
	
	
	
	#line = chart_pattern._determine(snapshot_index,candle_stream,chart_pattern._get_extremes(snapshot_index))
	chart_pattern._determine(snapshot_index,candle_stream)
	chart_pattern_view = chart_pattern.draw_snapshot(snapshot_index,candle_stream)
	show_trendline(line,0)
	#show_trendline(line1,-1)
	#show_trendline(line2,1)
	
	
	fig.show()
	t1 = time.time()
	#return level_fitness_tab
	#return#line#line1,line2 #level_fitness_tab
	print(f"Rendering time for {chart_pattern.__class__.__name__} was {t1-t0}")
	
	highers,lowers = chart_pattern._highers_lowers(snapshot_index)
	gap = chart_pattern._rolling_range_mean[snapshot_index]
	print("gap was "+str(gap))
	lines = chart_pattern._generate_trendlines(highers,lowers,gap,snapshot_index)
	return lines


#draw_all(snapshot_index)
#the_best_line_index = np.argmin(result)
#draw_all(the_best_line_index)
#pdb.set_trace()

#print(actions['1.3246'])

#for a in activities:
#	print(a)
#show_actions(actions)

















import numpy 
import psycopg2
import datetime

import pdb
import time


from configuration import Configuration
from data.tools.cursor import Database


from utils import ListFileReade
from charting.chart_viewer import ChartView, PlotlyChartPainter
from charting.candle_stick_pattern import CandleStickPattern

lfr = ListFileReader()
currencies = lfr.read('fx_pairs/currencies.txt')
fx_pairs = lfr.read('fx_pairs/fx_mains.txt')
sorted(fx_pairs)

the_date = datetime.datetime(2022,3,1,16,0)

parameters = {
	'chart_resolution':240,
	'the_date':the_date,
	'hour':the_date.hour,
	'days_back':50,
	'currencies':currencies,
	'candle_offset':120
}

cur = Database()

query = ''
with open('queries/candle_stick_selector.sql','r') as f:
	query = f.read()

cur.execute(query,parameters)
database_response = cur.fetchall()


candles = CandleStickPattern.to_candles(database_response,'GBP/USD')

this_view = ChartView()
this_view.draw_candles(candles)

pcp = PlotlyChartPainter()
pcp.paint(this_view)
pcp.show()


























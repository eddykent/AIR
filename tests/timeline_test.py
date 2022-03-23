assert __name__ != '__main__', 'use run_test.py'

import datetime
import pdb

from utils import ListFileReader, Database
from web.feed_collector import RSSCollect, ArticleCollector
from fundamental import TextAnalysis, KeywordMapHelper, NewsIndicator

import charting.chart_viewer as chv


lfr = ListFileReader()
sources = lfr.read('sources/rss_feeds.txt')
currencies = lfr.read('fx_pairs/currencies.txt')
fx_pairs = lfr.read('fx_pairs/fx_mains.txt')
fx_pairs = sorted(fx_pairs)

cur = Database(cache=False,commit=False) 
query = ''
with open('queries/candle_stick_selector.sql','r') as f:
	query = f.read()

the_date = datetime.datetime(2022,2,15,12,0)
params = {
	'chart_resolution':15,
	'the_date':the_date,
	'hour':the_date.hour,
	'days_back':50,
	'candle_offset':0,
	'currencies':currencies		
}
cur.execute(query,params)


rss = RSSCollect(sources)
rss.parse_feeds()

article_collector = ArticleCollector()
article_collector.pass_articles(rss)

text_analyser = TextAnalysis()
this_instrument = 'GBP/USD'

#pdb.set_trace()
candles = cur.fetchcandles(fx_pairs)
candle_streams = [candles[fx] for fx in fx_pairs]

news_indicator = NewsIndicator(article_collector,text_analyser)
news_indicator.pass_instrument_names(fx_pairs)
news_indicator.calculate_multiple(candle_streams)
news_indicator.instrument = this_instrument 

this_view = chv.ChartView()
this_view.draw_candles(candles[this_instrument])
this_view += news_indicator.draw_snapshot(candles[this_instrument])

pcp = chv.PlotlyChartPainter()
#pcp.paint(indicator_view)
pcp.paint(this_view)
pcp.show()




















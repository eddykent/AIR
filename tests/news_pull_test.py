

##test pulling data from the internet and putting it into the database 
from datetime import datetime

import pdb

from utils import ListFileReader, Database

import random

#from data.text import 
from data.text import DirectKeywordInstrumentMap
from data.tools.newnews import NewsHeadlines, DailyFXArchive, FXStreetSearch, RSSFeedParser, NewsItemProcessor

lfr = ListFileReader() 
fx_pairs = lfr.read('fx_pairs/fx_mains.txt')


dailyfxurl1 = DailyFXArchive.get_url((3,2023))
dailyfxurl2 = DailyFXArchive.get_url((2,2023))
dailyfxurl3 = DailyFXArchive.get_url((1,2023))
fxstreeturl1 = FXStreetSearch.get_url('GBP/USD')
fxstreeturl2 = FXStreetSearch.get_url('EUR/USD')
fxstreeturl3 = FXStreetSearch.get_url('AUD/CAD')
fxstreeturl4 = FXStreetSearch.get_url('USD/JPY')

fxstreeturls = [FXStreetSearch.get_url(fx_pair) for fx_pair in fx_pairs]


 
rsses = [
RSSFeedParser("https://www.dailyfx.com/feeds/market-news"),
RSSFeedParser("https://analysis.hotforex.com/feed/"),
RSSFeedParser("https://www.fxstreet.com/rss"),
RSSFeedParser("https://www.forexcrunch.com/feed/"),
RSSFeedParser("https://www.forexlive.com/feed/")
]

archive_urls = [
dailyfxurl1,
#dailyfxurl2,
#dailyfxurl3, 
#fxstreeturl1,
#fxstreeturl2,
#fxstreeturl3,
#fxstreeturl4
] + fxstreeturls

new_news_items = None

def run_test():
	cur = Database(cache=False)
	news_headlines = NewsHeadlines(rsses,archive_urls)
	news_items = news_headlines.get_items()
	
	dkim = DirectKeywordInstrumentMap(fx_pairs=fx_pairs)
	
	news_item_processor = NewsItemProcessor(cur,dkim)
	news_items = news_item_processor.prune_items(news_items)
	
	#sample_items = random.sample([ni for ni in news_items if 'hotforex' not in ni['source_ref']],10) #remove hotforex news
	
	#print('test multi process news scraper')
	items = news_item_processor.perfrom_scraping(news_items)
	news_item_processor.put_to_database(items)
	new_news_items = items
	
	
def run_one():
	from data.tools.newnews import FXStreet, DailyFXNews, ForexCrunch, ForexLive
	fxstreet = FXStreet('https://www.fxstreet.com/news/gold-price-forecast-xau-usd-advances-on-its-path-toward-1830-on-soft-us-dollar-202302281709')
	result = fxstreet.scrape()
	pdb.set_trace()
	print('check result')
	

#pdb.set_trace()




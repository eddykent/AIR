

##test pulling data from the internet and putting it into the database 
from datetime import datetime

import pdb

from utils import ListFileReader, Database

#from data.text import 
from data.tools.newnews import News, DailyFXArchive, FXStreetSearch, RSSFeedParser

lfr = ListFileReader() 
fx_pairs = lfr.read('fx_pairs/fx_mains.txt')


dailyfxurl = DailyFXArchive.get_url((2,2023))
fxstreeturl = FXStreetSearch.get_url('GBP/USD')
rssurl1 = "https://www.forexlive.com/feed/"


dailyfx1 = DailyFXArchive(dailyfxurl)#fill with months
fxstreet1 = FXStreetSearch(fxstreeturl)#fill with instruments 
rsses = [
RSSFeedParser("https://www.dailyfx.com/feeds/market-news"),
RSSFeedParser("https://analysis.hotforex.com/feed/"),
RSSFeedParser("https://www.fxstreet.com/rss"),
RSSFeedParser("https://www.forexcrunch.com/feed/"),
RSSFeedParser("https://www.forexlive.com/feed/")
]

cur = Database(cache=False)
news = News(rsses,cur)
news_tasks = news.get_items()

pdb.set_trace()




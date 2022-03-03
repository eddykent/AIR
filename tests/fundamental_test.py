import datetime
import pdb


from utils import ListFileReader
from fundamental import *
import scrape.feed_collector as feedco



assert __name__ != "__main__", "You must run tests through the run_test.py hoister" #need to remind myself! :) 

	
lfr = ListFileReader()
lfr.errors = 'ignore'
fx_pairs = lfr.read('fx_pairs/fx_mains.txt')
#cs = ClientSentiment(fx_pairs)##put fx pairs in!
#cs.fetch()
	

rss = feedco.RSSCollect(lfr.read('sources/rss_feeds.txt'))
#keyword_mappings_example = [
#	('USD',['FEDERAL RESERVE', 'US DOLLAR', 'GREEN BACK', 'GREENBACK', 'USD']),
#	('GBP/USD',['GBP/USD','GBPUSD','GBP','usd','CABLE'])  #put after USD to be detected second - but usd matches USD so all the other keys can be added (but in lower case) to this
	#which is why helper is needed! :) 
#]
rss.parse_feeds()
kwh = KeywordMapHelper()
ta = TextAnalysis(kwh)
rss.analyse_articles(ta)
rss.collect()


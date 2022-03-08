
import pickle
import zlib
from hashlib import md5


from web.feed_collector import RSSCollect
import web.feed_collector as feedco
from fundamental import KeywordMapHelper, TextAnalysis
from utils import ListFileReader

lfr = ListFileReader()

def load_cached():
	rss = None
	with open('pickles/rss_collected.pkl','rb') as f:
		rss = pickle.load(f)
	with open('pickles/rss_collected_articles.pkl','rb') as f:
		rss.articles = pickle.load(f)
	rss.parse_feeds()
	#kwh = KeywordMapHelper()
	#ta = TextAnalysis(kwh)
	#rss.analyse_articles(ta)
	#rss.collect()
	#rss.save_articles()
	return rss

def get_hash(article):
	total_text = ' '.join([article.title,article.summary,article.full_text,article.link])
	md5_hash = md5(total_text.encode()).hexdigets()
	return md5_hash


def load_fresh():
	rss = feedco.RSSCollect(lfr.read('sources/rss_feeds.txt'))
	rss.parse_feeds()
	kwh = KeywordMapHelper()
	ta = TextAnalysis(kwh)
	rss.analyse_articles(ta)
	rss.collect()
	return rss
	

def load_db():
	rss = feedco.RSSCollect(lfr.read('sources/rss_feeds.txt'))
	rss.load_articles()
	kwh = KeywordMapHelper()
	ta = TextAnalysis(kwh)
	rss.analyse_articles(ta) #doesnt collect anymore since full_text is full 
	return rss


def show_articles(rss):
	for (i,(a,t)) in enumerate(zip(rss.articles,rss._article_types)):
		print((' ' if i < 10 else '') + str(i) + ' - ' + str(t) + ' - ' + str(a)) 
		
		
#rss.save_articles() #test this! 
#rss.load_articles(datetime? ) 





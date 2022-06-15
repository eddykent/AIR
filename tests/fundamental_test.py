import datetime
import pdb


from utils import ListFileReader
from fundamental import *
import web.feed_collector as feedco



assert __name__ != "__main__", "You must run tests through the run_test.py hoister" #need to remind myself! :) 

	
lfr = ListFileReader()
lfr.errors = 'ignore'
#fx_pairs = lfr.read('fx_pairs/fx_mains.txt')
#cs = ClientSentiment()##put fx pairs in!
#cs.fetch()
	

rss = feedco.RSSCollect(lfr.read('sources/rss_feeds.txt'))
#keyword_mappings_example = [
#	('USD',['FEDERAL RESERVE', 'US DOLLAR', 'GREEN BACK', 'GREENBACK', 'USD']),
#	('GBP/USD',['GBP/USD','GBPUSD','GBP','usd','CABLE'])  #put after USD to be detected second - but usd matches USD so all the other keys can be added (but in lower case) to this
	#which is why helper is needed! :) 
#]
rss.parse_feeds() #this goes online and grabs the latest news
kwh = KeywordMapHelper()
ta = TextAnalysis(kwh)

#consider pickle.load(f), open('pickles/stories.pkl') to get faster test result

aco = feedco.ArticleCollector()
aco.pass_articles(rss)
aco.analyse_articles(ta)
aco.save_articles()
aco.collect()



def show_articles(rss):
	for (i,(a,t)) in enumerate(zip(rss.articles,rss._article_types)):
		print((' ' if i < 10 else '') + str(i) + ' - ' + str(t) + ' - ' + str(a)) 




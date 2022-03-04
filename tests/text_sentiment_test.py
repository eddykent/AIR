
#this is a work in progress to develop a strategy for reading a NEWS STORY and getting any insights from it
#sentiment analysis comes to mind, but it is probably not a good idea to place a sentiment score against a whole story
#stories can have more than 1 thing in them and each thing can have a different sentiment - lets make something that 
#will collect insights (together with some strength score or something) to get a bias from a collection of stories. 


import nltk
from textblob import TextBlob

import pickle

from fundamental import ForexSlashHelper, KeywordMapHelper, TextAnalysis


def load_cached():
	rss = None
	with open('pickles/rss_collected.pkl','rb') as f:
		rss = pickle.load(f)
	with open('pickles/rss_collected_articles.pkl','rb') as f:
		rss.articles = pickle.load(f)
	return rss
		
def load_fresh():
	rss = feedco.RSSCollect(lfr.read('sources/rss_feeds.txt'))
	rss.parse_feeds()
	kwh = KeywordMapHelper()
	ta = TextAnalysis(kwh)
	rss.analyse_articles(ta)
	rss.collect()
	return rss
	
	
def perform_sentiment(some_text):
	fsh = ForexSlashHelper()
	textblob = TextBlob(fsh.strip_slashes(some_text).lower())
	overall = textblob.sentiment
	specific = []
	kwh = KeywordMapHelper()
	for sentence in textblob.sentences:
		keys = kwh.relevant_keys(sentence)
		if keys:
			specific.append((keys,sentence.sentiment))
	return overall, specific





def show_articles(rss):
	for (i,(a,t)) in enumerate(zip(rss.articles,rss._article_types)):
		print((' ' if i < 10 else '') + str(i) + ' - ' + str(t) + ' - ' + str(a)) 
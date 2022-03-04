
#this is a work in progress to develop a strategy for reading a NEWS STORY and getting any insights from it
#sentiment analysis comes to mind, but it is probably not a good idea to place a sentiment score against a whole story
#stories can have more than 1 thing in them and each thing can have a different sentiment - lets make something that 
#will collect insights (together with some strength score or something) to get a bias from a collection of stories. 


import nltk
import nltk.sentiment
from textblob import TextBlob

import pickle

from utils import ListFileReader
from fundamental import ForexSlashHelper, KeywordMapHelper, TextAnalysis
import web.feed_collector as feedco

lfr = ListFileReader()

def load_cached():
	rss = None
	with open('pickles/rss_collected.pkl','rb') as f:
		rss = pickle.load(f)
	with open('pickles/rss_collected_articles.pkl','rb') as f:
		rss.articles = pickle.load(f)
	return rss

def save_rss(rss):
	with open('pickles/rss_collected.pkl','wb') as f:
		pickle.dump(rss,f)
	with open('pickles/rss_collected_articles.pkl','wb') as f:
		pickle.dump(rss.articles,f)
	
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
	sa = nltk.sentiment.SentimentIntensityAnalyzer()
	textblob = TextBlob(fsh.strip_slashes(some_text).lower())
	polarity = sa.polarity_scores(str(textblob))
	overall = {'subjectivity':textblob.sentiment.subjectivity,'polarity': polarity['compound']}
	specifics = []
	kwh = KeywordMapHelper()
	for sentence in textblob.sentences:
		keys = kwh.relevant_keys(sentence)
		if keys:
			polarity = sa.polarity_scores(str(sentence))
			specifics.append((sentence,keys,{'subjectivity':sentence.sentiment.subjectivity,'polarity': polarity['compound']}))
	return overall, specifics





def show_articles(rss):
	for (i,(a,t)) in enumerate(zip(rss.articles,rss._article_types)):
		print((' ' if i < 10 else '') + str(i) + ' - ' + str(t) + ' - ' + str(a)) 
		
		
		
		
		
		
		
		
		
		
		
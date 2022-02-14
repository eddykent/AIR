
import feedparser
import re
import time
import datetime

import pdb

from scrape.scraper import Article, Bias, SentimentDatum
	
class FeedCollect:

	sources = [] 
	keyword_mappings = []
	articles = [] 
	instrument_summary = [] #for each instrument, keep the bullish/bearish scores and sources
	relevance_threshold = 0.1

	def __init__(self,sources): 
		self.sources = sources
		
	#def __analyse_???? sentiment analysis stuff 
	 
	def parse_feeds(self):
		raise NotImplementedError('This method must be overridden')
	
	def sentiment_analysis(self,sentiment_analyser):
		for article in self.articles:
			if article.relevance_score is None: 
				article.relevance_score = sentiment_analyser.get_relevance(article)
			
		#perform an async here?
		#async [article.fetch_full_text() for article in self.articles if article.sentiment_scores]
		for article in self.articles:
			if article.relevance_score > self.relevance_threshold: #so this article is relevant
				article.sentiment_score = sentiment_analyser.get_score(article)
	
	def collect(self,keyword_helper=None):
		self.instrument_summary = [] 
		for article in self.articles: 
			relevant_keys = keyword_helper.relevant_keys(article) if keyword_helper else article._relevant_keys
			
	
	#def keyword_collect(self):
	def parse_historic(self):
		pass #one can dream
	
	@staticmethod
	def _pretty_sourcename(link):
		bits = re.split('//|/|\?',link)
		return bits[1].replace('www.','')

##collectors that look at feeds and do some simple analysis to find market sentiment 
class RSSCollect(FeedCollect):
	
	entries = [] 
	
	def parse_feeds(self):
		self.entries = []
		for source in self.sources: 				
			rss = feedparser.parse(source)
			self.entries += rss.entries
			
			source_title = self._pretty_sourcename(source)
			if rss.feed.title:
				source_title = rss.feed.title
			
			#create articles from this rss feed article
			for entry in rss.entries:
				entry.source_title = source_title #add the source title for easier publishing/debugging later
				article = Article.from_rss_entry(entry)
				self.articles.append(article)		
	
#TODO: 
class TwitterCollect(FeedCollect):
	
	tweets = []
	
	def parse_feeds(self):
		self.tweets = []
		for source in self.sources:
			pass #do twitter thing

class SubRedditCollect(FeedCollect):
	pass

# 






























import feedparser
import re
import time
import datetime
from enum import Enum
from collections import namedtuple

import pdb

from scrape.scraper import Article

class Bias(Enum):
	BEARISH = -2 #filter 
	SLIGHT_BEARISH = -1 #setup
	MIXED = 0
	SLIGHT_BULLISH = 1 #setup
	BULLISH = 2 #filter


class TextType(Enum):
	UNKNOWN = 0
	INVITATION = 1 #eg to a webinar or something
	TUTORIAL = 2 #also include video etc - these are not useful to us and we should avoid them if possible 
	TRADE_SIGNAL = 3 #we can store the trade signal stories for later if needed! 
	STORY = 4 #this is the one we actually want! We perform sentiment analysis on stories only. We could use the trade signals though. 
	

#the_date - date of the article and when it was published 
#instrument - eg EUR/USD 
#keyword  - the keyword that was found in the article/story or whatever 
#category - the category of the article since sometimes they are passages, sometimes they are orders
#title - the title from the artricle for displaying later & for debugging purposes
#summary - the summary from the article for displaying later & for debugging purposes
#source_url - the url where the source is 
#degree - 1 if the article is directly related and 2 if the article is indirectly related (eg federal reserve on GBP/USD)
#bias - BULLISH, BEARISH, MIXED
#significance - final sentiment score for using when performing fundamental analysis on the instrument 
SentimentDatum  = namedtuple('SentimentDatum','the_date instrument keyword title summary source_url degree bias significance')

class FeedCollect:

	sources = [] 
	articles = [] 
	all_findings = [] #for each instrument, keep the bullish/bearish scores and sources in SentimentDatum objects
	instrument_summary = []# for each instrument, keep a simple "bullish"/"bearish" score gerneated from the findings 
	
	_sentiment_scores = []#keep internal results of sentiment for each article
	_relevant_key_info = []#keep internal results of all relevant keys found for all articles 
	_text_types = []#keep internal results of what type of text the passage was for each article

	def __init__(self,sources): 
		self.sources = sources
		
	#def __analyse_???? sentiment analysis stuff 
	 
	def parse_feeds(self):
		raise NotImplementedError('This method must be overridden')
	
	#walk through each article, decide whether to open it or not and perform analysis on it to gauge 
	#key words it is talking about as well as sentiment about those words 
	def analyse_articles(self,text_analyser):
		#initalise lists 
		self._sentiment_scores = [0 for a in self.articles] 
		self._relevant_key_info = [[] for a in self.articles]
		self._text_types = [TextType.UNKNOWN for a in self.articles]
		
		for i, article in enumerate(self.articles):
			relevant_keys_in_title = text_analyser.get_relevant_keys(article.title + ' ' + article.summary)
			
			if not relevant_keys_in_title:
				continue # this article has no information about stuff we are interested in in the title so we can skip it 
			
			article.fetch_full_text() #async from here? 
			self._relevant_key_info[i] = text_analyser.get_relevant_keys(article.full_text)
	
	#generate list of SentimentDatum and store in insturment_summary
	def collect(self,keyword_helper=None):
		self.all_findings = [] 
			
	
	#def keyword_collect(self):
	def parse_historic(self):
		pass #one can dream - do something about loading/saving articles to the database for this
	
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





























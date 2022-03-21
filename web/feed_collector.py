
import feedparser
import re
import time
import datetime as DateTime
from enum import Enum
from collections import namedtuple, defaultdict

import zlib
import hashlib
import json

import pdb

from web.scraper import Article


from utils import Database, Inject


class TextBias(Enum):
	BEARISH = -2 #filter 
	SLIGHT_BEARISH = -1 #setup
	MIXED = 0
	SLIGHT_BULLISH = 1 #setup
	BULLISH = 2 #filter

class TextType(Enum):
	UNKNOWN = 0 #initalise to unknown to tell us we havent checked yet 
	MEDIA = 1# if it is a youtube video or something
	TUTORIAL = 2 #also include video etc - these are not useful to us and we should avoid them if possible 
	TRADE_SIGNAL = 3 #we can store the trade signal stories for later if needed! 
	STORY = 4 #this is the one we actually want! We perform sentiment analysis on stories only. We could use the trade signals though. 
	

#the_date - date of the article and when it was published 
#instrument - eg EUR/USD 
#keyword  - the keyword that was found in the article/story or whatever 
#title - the title from the artricle for displaying later & for debugging purposes
#summary - the summary from the article for displaying later & for debugging purposes
#source_url - the url where the source is 
#degree - 1 if the article is directly related and 2 if the article is indirectly related (eg federal reserve on GBP/USD)
#bias - BULLISH, BEARISH, MIXED
#significance - final sentiment score for using when performing fundamental analysis on the instrument 
SentimentData  = namedtuple('SentimentData','the_date instrument keyword title summary source_url degree bias significance')
TimelineData = namedtuple('TimelineData','the_date source_ref source_url bias significance') 

class TallyBias:
	
	@staticmethod
	def collect(tally):
		collected_result = TextBias.MIXED
				
		has_bull = TextBias.BULLISH in tally or TextBias.SLIGHT_BULLISH in tally
		has_bear = TextBias.BEARISH in tally or TextBias.SLIGHT_BEARISH in tally
		
		if not (has_bull and has_bear): #if we are not bullish AND bearish
			
			if TextBias.BULLISH in tally:
				collected_result = TextBias.BULLISH
			elif TextBias.SLIGHT_BULLISH in tally:
				collected_result = TextBias.SLIGHT_BULLISH
					
			if TextBias.BEARISH in tally:
				collected_result = TextBias.BEARISH
			elif TextBias.SLIGHT_BEARISH in tally:
				collected_result = TextBias.SLIGHT_BEARISH
				
		return collected_result
	
#this suffers from "god class" and needs to be refactored into smaller pieces
class ArticleCollector:

	articles = [] 
	
	all_findings = [] #SentimentData objects
	_reduced_findings = []
	instrument_summary = {}# for each instrument, keep a simple "bullish"/"bearish" score gerneated from the findings 
	instrument_timelines = {}#for each instrument, keep a nice timeline of what news there was plus sentiment scores etc 
	
	_article_sentiment = []#keep sentiment per article
	_article_topics = []
	#_article_signals = [] 
	_article_types = []#keep internal results of what type of text the passage was for each article
	
	parameter_settings = {'subjectivity_threshold':0.2,'slight_threshold':0.25,'full_threshold':0.5,'significance_threshold':0.0}

	def get_text_type(self,article,text_analyser):
		the_type = TextType.STORY #default to story
		if article.full_text == 'VIDEO':
			the_type = TextType.MEDIA
		if text_analyser.is_signal(article.full_text):
			the_type = TextType.TRADE_SIGNAL
		if text_analyser.tutorial_title(article.title + ' ' + article.summary) and text_analyser.is_tutorial(article.full_text):
			the_type = TextType.TUTORIAL
		return the_type
	
	#walk through each article, decide whether to open it or not and perform analysis on it to gauge 
	#key words it is talking about as well as sentiment about those words 
	def analyse_articles(self,text_analyser):
		#initalise lists 
		self._article_types = [TextType.UNKNOWN for a in self.articles]
		#self._article_signals = [[] for a in self.articles]
		self._article_sentiment = [{} for a in self.articles]
		self._article_topics = [{} for a in self.articles]
		
		for i, article in enumerate(self.articles):
			
			relevant = text_analyser.keyword_helper.relevant_keys(article.title + ' ' + article.summary)
			
			if not relevant:
				if text_analyser.tutorial_title(article.title + ' ' + article.summary):
					self._article_types[i] = TextType.TUTORIAL #may as well note the tutorials :)
				continue # this article has no information about stuff we are interested in in the title so we should skip it to speed things up
			
			if article.full_text is None or article.full_text == '':
				article.fetch_full_text() #async?
			
			the_text_type = self.get_text_type(article,text_analyser)
			self._article_types[i] = the_text_type
			self._article_topics[i] = relevant
			
			if the_text_type == TextType.STORY:
				overall, specifics = text_analyser.get_sentiment(article.full_text)
				self._article_sentiment[i] = {'overview':overall,'specifics':specifics} 
			
			#if the_text_type == TextType.TRADE_SIGNAL:
			#	pass # perhaps can create a trade signal object here... might require a specialist parser though 
	
	def _get_bias(self,value):
		if value < -self.parameter_settings['full_threshold']:
			return TextBias.BEARISH
		if value < -self.parameter_settings['slight_threshold']:
			return TextBias.SLIGHT_BEARISH
		if value > self.parameter_settings['full_threshold']:
			return TextBias.BULLISH
		if value > self.parameter_settings['slight_threshold']:
			return TextBias.SLIGHT_BULLISH
		return TextBias.MIXED
		
		
	def _get_signficance(self,sentiment,subjectivity,nkeys,main):
		base = (abs(sentiment) / (1 + subjectivity)) * (1 / nkeys)
		return base if main else base / 2.0 #less significance if it is from a sentence in an article 
		
	#produce the list of sentiment data
	def _collect_findings(self):
			
		self.all_findings = []
		for i, article in enumerate(self.articles):
			if not self._article_types[i] == TextType.STORY:
				continue 
			sentiments = self._article_sentiment[i]
			subjectivity = sentiments['overview']['subjectivity']
			
			first_keys = self._article_topics[i]
			the_date = article.the_date 
			title = article.title
			summary = article.summary 
			source_url = article.link
			polarity = sentiments['overview']['polarity']
			n_hits = len(first_keys)
			
			if subjectivity < self.parameter_settings['subjectivity_threshold']:
				for instrument,rel in first_keys.items():  #rel = RelevanceInfo(degree,direction,keyword)
					degree = rel.degree
					this_sentiment = polarity * rel.direction #negate the score if the relevance goes the other way. always 1 anyway though for first_keys
					keyword = rel.keyword
					bias = self._get_bias(this_sentiment)
					significance = self._get_signficance(this_sentiment,subjectivity,n_hits,degree==1)#if degree is 1 it is quite significant
					sd = SentimentData(the_date,instrument,keyword,title,summary,source_url,degree,bias,significance)
					self.all_findings.append(sd)
			
			for sentence,sentence_keys,sentence_sentiment in sentiments['specifics']:
				polarity = sentence_sentiment['polarity']
				subjectivity = sentence_sentiment['subjectivity']
				n_hits = len(sentence_keys)
				if subjectivity < self.parameter_settings['subjectivity_threshold']:
				
					for instrument,rel in sentence_keys.items():
						degree = rel.degree
						this_sentiment = polarity * rel.direction
						keyword = rel.keyword
						bias = self._get_bias(this_sentiment)
						significance = self._get_signficance(this_sentiment,subjectivity,n_hits,False) #always since degree=2 OR from sentence
						sd = SentimentData(the_date,instrument,keyword,title,summary,source_url,degree,bias,significance)
						self.all_findings.append(sd)
			
	
#SentimentData  = namedtuple('SentimentData','the_date instrument keyword title summary source_url degree bias significance')		
	
	#consider improving by removing all degree=2 and allow for less significant degree=1 findings to be used
	#maybe also only key by instrument and get latest etc 
	def _reduce_findings(self,expire=1440):	
		findings_by_title = {}
		self.reduced_findings = []
		for sd in set(self.all_findings): 
			if sd.the_date > DateTime.datetime.now() - DateTime.timedelta(minutes=expire):  #1440 = 1 day. Article is less than 1 day old 
				findings_by_title.setdefault(sd.title,[]).append(sd) #why?
		for title,sds in findings_by_title.items():
			findings_by_instrument = {}
			[findings_by_instrument.setdefault(sd.instrument,[]).append(sd) for sd in sds]
			for instrument, ssds in findings_by_instrument.items():
				#latest! not significance!
				collected_bias = TallyBias.collect([sd.bias for sd in ssds if sd.significance > self.parameter_settings['significance_threshold']]) 
				most_significant = [sd for sd in ssds if sd.significance == max([sd.significance for sd in ssds])]
				if most_significant:
					md = most_significant[0]
					self._reduced_findings.append(SentimentData(md.the_date,md.instrument,md.keyword,md.title,md.summary,md.source_url,md.degree,collected_bias,md.significance))
		
	
	
	#generate insturment_summary from all articles, and generate SentimentData for storing the reasons 
	#this function works for right now but not for across a timeline. use to_timelines() for that
	def collect(self):
		self._collect_findings()
		self._reduce_findings()
		self.instrument_summary = {}  
		
		findings_by_instrument = {} 
		#use self.reduced_findings to build summary for each instrument
		[findings_by_instrument.setdefault(sd.instrument,[]).append(sd) for sd in self._reduced_findings]
		
		for instrument, sds in findings_by_instrument.items():
			self.instrument_summary[instrument] = TallyBias.collect([sd.bias for sd in sds])
	
	#plot per article 
	def to_article_timelines(self,instruments=[]):	
		instrument_timelines = defaultdict(list)
		for article,topic,sentiment in zip(self.articles,self._article_topics,self._article_sentiment):
			#pdb.set_trace()
			for instrument,relevance_info in topic.items():
				sentiment_value = sentiment.get('overview',{}).get('polarity',0)
				if relevance_info.degree == 1: #only stack things that are relevant to the first degree
					bias_number = sentiment_value * relevance_info.direction
					timeline_data = TimelineData(\
						the_date=article.the_date,\
						source_ref=article.source_ref,
						source_url=article.link,
						bias=self._get_bias(bias_number),
						significance=abs(sentiment_value)
					)  #the_date source_ref source_url bias significance
					instrument_timelines[instrument].append(timeline_data)	
		#return a bunch of timelines that have the article date, the article bias etc organised per instrument
		for instrument, timeline in instrument_timelines.items(): #sort them by date in ascending order
			instrument_timelines[instrument] = sorted(timeline,key=lambda tld:tld.the_date)
		return instrument_timelines
	
	#plot per finding - eg in sentences in articles etc 
	def to_findings_timelines(self,instruments=[]):
		instrument_timelines = defaultdict(list)
		self._collect_findings()
		for sentiment_data in self.all_findings:
			timeline_data = TimelineData(\
				the_date=sentiment_data.the_date,\
				source_ref=FeedCollect._pretty_sourcename(sentiment_data.source_url),\
				source_url=sentiment_data.source_url,\
				bias=sentiment_data.bias,\
				significanc=sentiment_data.significance\
			)
			instrument_timelines[sentiment.instrument].append(timeline_data)
		for instrument, timeline in instrument_timelines.items(): #sort them by date in ascending order
			instrument_timelines[instrument] = sorted(timeline,key=lambda tld:tld.the_date)
		return instrument_timelines
	
	
	def pass_articles(self,some_collector):
		self.articles.extend(some_collector.articles)
	
	def clear_articles(self):
		self.articles.clear()
	
	def dedupe(self,key_funct=None): #perhaps choose what to use as the key here 
		#key by source? link? 
		if not callable(key_funct) or key_funct is None:
			key_funct = lambda a: a.link
		articles_by_key = defaultdict(list)
		for article in self.articles:
			key = key_funct(article)
			articles_by_key[key].append(article)
		self.clear_articles()
		for key in articles_by_key:
			sorted_same_articles = sorted(articles_by_key[key],key=lambda a:a.the_date)
			self.articles.append(sorted_same_articles[-1]) #get latest 
	
	#load articles from the database that are saved from before if no from_Data/to_date is provided every article ever will be loaded!
	def load_articles(self,start_date=DateTime.datetime(2000,1,1),end_date=DateTime.datetime.now()):
		query = ''
		with open('queries/load_articles.sql','r') as f:
			query = f.read()
		article_data = []
		with Database(commit=False,cache=False) as cur:
			cur.execute(query,{'start_date':start_date, 'end_date':end_date})
			article_data = cur.fetchall()
		for a in article_data:
			self.articles.append(Article.from_database_row(a))
		
		
	#we can save articles to the database
	def save_articles(self):
		rows = []
		sql_row =  "(%(hash_identifier)s,%(published_date)s,%(source_ref)s,%(title_head)s,%(compression)s)" #Article.sql_row
		for i,article in enumerate(self.articles):
			text_type = self._article_types[i]  
			if text_type == TextType.STORY: #only save stories in the database since other types are not useful. Signals should be saved in a separate table 
				rows.append(article.to_database_row())
		#pdb.set_trace()
		if rows:
			to_delete = [r['hash_check'] for r in rows]
			with Database(commit=True,cache=False) as cur:
				with open('queries/save_articles.sql','r') as f:
					query = f.read()
					#build params
					sql_rows = []
					for row in rows:
						sql_rows.append(cur.mogrify(sql_row,row).decode())
					all_rows = ','.join(sql_rows)
					params = {
						'remove_hashes':to_delete,
						'articles':Inject(all_rows)
					}
					#pdb.set_trace()
					cur.execute(query,params) #why is this not committing?
				#cur.connection.commit()#	
			
	

#a feed collect goes to the web and scrapes sources for latest news 
class FeedCollect:
	
	sources = []
	articles = []
	
	def __init__(self,sources): 
		self.sources = sources
	
	def parse_feeds(self):
		raise NotImplementedError('This method must be overridden')
	
	@staticmethod
	def _pretty_sourcename(link):
		bits = re.split('//|/|\?',link)
		return bits[1].replace('www.','')

##collectors that look at feeds from the web to get most recent news data
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





























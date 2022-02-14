import datetime
import re

import nltk
import nltk.sentiment
from collections import namedtuple

import json

#test change
#from requests_html import HTMLSession

import pdb

from utils import ListFileReader, CurrencyPair

import scrape.client_sentiment_scraper as clisps
import scrape.feed_collector as feedco

KeywordMap = namedtuple('KeywordMap','keyword values')
RelevanceInfo = namedtuple('RelevanceInfo', 'degree direction')

## TODO:
## rss feeds 
## twitter feeds 
## news feeds (eg bbc news, cbn etc) 
##
## Sentiment analysis eg, using word count
## 	-this is hardest step! may have to do some research into this and perhaps use ANN to do the majority of the work 
## Sentiment using number of buyers/sellers
##
## fetch() for the current. 
## history() for any historical stuff we can find 
## data populator - database tables etc. 

#use websites to get position summary of each pair? eg how many buyers and how many sellers there are

#class for reading sentiment indicators on the internet and getting the values
class ClientSentiment: #a client sentiment is just how many are buying/selling. Not market news
	
	instruments = []
	sources = []
	findings = {}
	
	def __init__(self,instruments=[]):
		lfr = ListFileReader()
		if not instruments:
			instruments = lfr.read('fx_pairs/fx_mains.txt')
		self.instruments = instruments 
		self.sources = lfr.read('sources/sentiment_indicators.txt')
		self.findings = {pair:[] for pair in self.instruments}
	
	def fetch(self):
		result = []
		for source in self.sources:
			source_split = re.split('/|\.',source)
			scraper = None
			if 'dailyfx' in source_split:
				scraper = clisps.DailyFX(source,self.instruments)
			elif 'forexclientsentiment' in source_split:
				scraper = clisps.ForexClientSentiment(source,self.instruments)
			elif 'myfxbook' in source_split:
				scraper = clisps.MyFXBook(source,self.instruments)
			elif 'dukascopy' in  source_split:
				scraper = clisps.Dukascopy(source,self.instruments)
			else:
				print('Parser not implemented for source: \n'+source)
				pdb.set_trace()
			result += scraper.get_client_sentiment_info() if scraper else []
		self.__process_findings(result)
	
	def fetch_historic(self):  ##get data from ages ago & cache in a database if we want to use in RNN
		pass
	
	def __process_findings(self,results):
		#TODO: write some tactic to process the tuples into findings so we can use it in a filter
		pdb.set_trace()



	
##not sure how this will work yet - could just be something that prevents trading at choppy times when 
##big news is about to come out 
##OR it could be something that suggests a trade based on the economic calendar prediction
class EconomicCalendar:
	pass
	
	
#something to help parse all keywords from any files into a keywords object for a FeedCollect
#keyword mappings are a list of [{'USD/JPY':['USD/JPY','USDJPY','USD','jpy']}] with a hack:- 
#bullish = caps and bearish = lowercase 
#this class can also get 2nd degree mappings (eg, 'federal reserve'  -> 'USD' -> 'USD/JPY'
#		Another example:'bank of england' -> 'GBP' -> 'eur/gbp' (notice the case!) 
#		Putting this together could help put all feeds into a tree structure, which can then
#		be used to generate fundamental signals 
#		higher degree relationships should be put first to be determined first. Eg, we want to 
#		Hear about the USD and thus about the federal reserve before we hear about the EUR/USD
#		so we can conclude it all together nicely with a focus on the higher degree 
class KeywordMapHelper:
	
	input_keyword_map = [] 
	bloated_keyword_map = []
	all_words_relevance = []
	map_file = 'keyword_mappings.json'
	
	def __init__(self,keyword_map_file=None):
		if keyword_map_file is not None:
			self.map_file = keyword_map_file
		lfr = ListFileReader()
		keyword_maps_str = lfr.read_full_text(self.map_file)
		keyword_maps = json.loads(keyword_maps_str)
		self.input_keyword_map = self.__construct_keyword_map(keyword_maps.items())
		self.bloated_keyword_map = self.input_keyword_map
		self.all_words_relevance = self.__generate_all_words(self.input_keyword_map)
	
	#if an article title or an article summary has any words that are interesting to us, it is relevant. 
	#otherwise we can probably filter it out to save computational resources! 
	#this step organises things for us to be able to update sentiments based on relevance and degree
	def relevant_keys(self,article):	
		#perhaps we should move all author name words from the article first to ensure we don't get false relevances XD
		
		if article._relevant_keys:
			return article._relevant_keys
			
		summary_text = article.title + ' ' + article.summary

		words = nltk.word_tokenize(summary_text.lower())
		intersect = self.all_words_relevance.intersection(words)
		
		if not intersect:
			return []
	
		#Ah! which keys is intersect relevant to? - now check in these the full phrases
		#deeper checks - check if the actual full token with mutliple words is in the article title/summary 
		relevant_keys = {} #check for first degree first 
		degree = 1
		for keyword_mapping in self.input_keyword_map:
			keyword = keyword_mapping.keyword
			values = keyword_mapping.values
			
			if keyword.lower() in words or keyword.replace('/','').lower() in words:
				relevant_keys[keyword] = [RelevanceInfo(1,1)] #it is obv bullish if the key is used so sentiment up => this key up 
			
			for value in values:
				direction = 1 if self.bullish(value) else -1
				pad_val = ' ' + value.lower() + ' ' #ensure it is a word and not part of a word
				if value.lower() in words:
					relevant_keys[keyword] = relevant_keys.get(keyword,[]) + [RelevanceInfo(degree,direction)]
					
				elif pad_val in summary_text:
					relevant_keys[keyword] = relevant_keys.get(keyword,[]) + [RelevanceInfo(degree,direction)]
					
					
		#then check for second degree
		degree = 2
		for keyword_mapping in self.bloated_keyword_map:
			keyword = keyword_mapping.keyword
			values = keyword_mapping.values
							
			#checked key already - check bloat values
			for value in values:
				direction = 1 if self.bullish(value) else -1
				pad_val = ' ' + value + ' '
				if value.lower() in words:
					relevant_keys[keyword] = relevant_keys.get(keyword,[]) + [RelevanceInfo(degree,direction)]
					
				elif pad_val in summary_text:
					relevant_keys[keyword] = relevant_keys.get(keyword,[]) + [RelevanceInfo(degree,direction)]
		
		article._relevant_keys = relevant_keys 
		return relevant_keys
	
	def bloat(self):
		self.bloated_keyword_map = []
		build_this_dict = {}
		# set bloated keyword maps to have move values from previous key words etc 
		# example: if keyword 'USD' has a keyword value 'FEDERAL RESERVE' then we should add 'federal reserve' to GBP/USD etc 
		for keyword_mapping in self.input_keyword_map:
			keyword = keyword_mapping.keyword
			values = keyword_mapping.values
			if '/' in keyword:
				pair = CurrencyPair(keyword)
				bullish_stuff = build_this_dict.get(pair.from_currency,[])
				bearish_stuff = build_this_dict.get(pair.to_currency,[])
				values += bullish_stuff + [v.lower() for v in bearish_stuff]
			build_this_dict[keyword] = values
		self.bloated_keyword_map = self.__construct_keyword_map(build_this_dict.items())
	
	def collect_by_keywords(self,articles): #article duplciation? 
		for key,values in self.bloated_keyword_map:
			for article in articles:
				pass
	
	@staticmethod
	def __generate_all_words(keyword_map):
		return set([k.keyword.lower() for k in keyword_map] + [v.lower() for k in keyword_map for v in k.values])
	
	@staticmethod
	def __construct_keyword_map(keyword_map):
		#we also want to put in the actual key into the value right?
		#for keyword, values in keyword_map:
		return [KeywordMap(km[0],km[1]) for km in keyword_map]
	
	@staticmethod
	def bullish(value):
		return value == value.upper()
	
	@staticmethod
	def bearsh(value):
		return value == value.lower()
	
	
#from a bunch of text, is it good or bad?
class SentimentAnalysis:
	
	stopwords = []
	keyword_helper = None ##use to help filter sentences etc 
	filter_articles = ['seminar','video','tutorial'] #think of any other stuff here! 
	analyzer = None
	
	def __init__(self, keyword_helper):
		self.stopwords = nltk.corpus.stopwords.words('english')
		self.analyzer = nltk.sentiment.SentimentIntensityAnalyzer()
		self.keyword_helper = keyword_helper
	
	#motivation: https://realpython.com/python-nltk-sentiment-analysis/
	def get_score(self,article):
		article.fetch_full_text() #comment out once we have done an async call on all relevant articles
		if type(article.full_text) != str:
			print("the text is not a string?")
			pdb.set_trace()
		score = self.analyzer.polarity_scores(article.full_text)
		return score['compound'] # 0 means no sentiment at all (not positive or negative). 1 is good and -1 is  bad 
	
	def get_relevance(self,article):
		##determine if this article is actually relevant first - perhaps look for things like filter_words and if there are none it might be relevant!
		relevant_keys = self.keyword_helper.relevant_keys(article)
		if not relevant_keys:
			return 0.0 # well there's no keywords in the title/summary! 
		
		tokens = nltk.word_tokenize(article.title.lower() + ' ' + article.summary.lower()) 
		##need to do something to prevent webinar invites seeping through... 
		distribution = nltk.FreqDist([t for t in tokens if t not in self.stopwords])
		#TODO - use the distribution to assess relevance & reject things like values in filter_article
		return 1.0 #crude but works for now. 
	
#may want to do own sentiment analysis - to do so  replace analyzer in the SentimentAnayzer class with something like the below base class



if __name__ == '__main__':
	
	lfr = ListFileReader()
	fx_pairs = lfr.read('fx_pairs/fx_mains.txt')
	cs = ClientSentiment(fx_pairs)##put fx pairs in!
	cs.fetch()
		
	
	#rss = feedco.RSSCollect(lfr.read('sources/rss_feeds.txt'))
	#keyword_mappings_example = [
	#	('USD',['FEDERAL RESERVE', 'US DOLLAR', 'GREEN BACK', 'GREENBACK', 'USD']),
	#	('GBP/USD',['GBP/USD','GBPUSD','GBP','usd','CABLE'])  #put after USD to be detected second - but usd matches USD so all the other keys can be added (but in lower case) to this
		#which is why helper is needed! :) 
	#]
	#rss.parse_feeds()
	#kwh = KeywordMapHelper()	
	#sa = SentimentAnalysis(kwh)
	#rss.sentiment_analysis(sa)
	#rss.collect(kwh)





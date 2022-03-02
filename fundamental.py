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
from scrape.feed_collector import Bias

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
	findings = {} #all findings from multiple sources
	collected_result = {} #the over-all result for each instrument from the findings 
	
	def __init__(self,instruments=[]):
		lfr = ListFileReader()
		if not instruments:
			instruments = lfr.read('fx_pairs/fx_mains.txt')
		self.instruments = instruments #currencies too?
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
		#TODO: write some tactic to process the tuples into findings, then into a summary so we can use it in a filter
		self.findings = {pair:[] for pair in self.instruments}
		self.collected_result = {pair:Bias.MIXED for pair in self.instruments} 
		for r in results:
			if r.bias != Bias.MIXED:
				instrument_result = self.findings.get(r.instrument,[])
				instrument_result.append(r)
				self.findings[r.instrument] = instrument_result
		for instrument in self.findings:  #might want to include something about the timeframe or the date? 
			csinfos = self.findings[instrument]
			tally = {} 
			for csi in csinfos:
				score = tally.get(csi.bias,0)
				score += 1
				tally[csi.bias] = score
			
			collected_result = Bias.MIXED
			
			has_bull = Bias.BULLISH in tally or Bias.SLIGHT_BULLISH in tally
			has_bear = Bias.BEARISH in tally or Bias.SLIGHT_BEARISH in tally
			
			if not (has_bull and has_bear): #if we are not bullish AND bearish
				
				if Bias.BULLISH in tally:
					collected_result = Bias.BULLISH
				elif Bias.SLIGHT_BULLISH in tally:
					collected_result = Bias.SLIGHT_BULLISH
						
				if Bias.BEARISH in tally:
					collected_result = Bias.BEARISH
				elif Bias.SLIGHT_BEARISH in tally:
					collected_result = Bias.SLIGHT_BEARISH
					
			self.collected_result[instrument] = collected_result


	
##not sure how this will work yet - could just be something that prevents trading at choppy times when 
##big news is about to comeresults out 
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
	def relevant_keys(self,summary_text):	
		#perhaps we should move all author name words from the article first to ensure we don't get false relevances XD
				
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
		
		return relevant_keys
	
	def bloat(self):
		self.bloated_keyword_map = []
		build_this_dict = {}
		# set bloated keyword maps to have move values from previous key words etc 
		# example: if keyword 'USD' has a keyword value 'FEDERAL RESERVE' then we should add 'federal reserve' to GBP/USD etc 
		pdb.set_trace()
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
	
	
#Tool for doing all natural language stuff for articles found online. News storys are articles collected from a feed collector
#they are then passed into this tool for further clarification. Is the story actually a buy/sell signal? Is it relevant? is the
#author positive or negative about whatever it is they are talking about? What are the main key words we can use etc 
class ArticleAnalysis:
	
	stopwords = []
	keyword_helper = None ##use to help filter sentences etc 
	filter_articles = ['seminar','video','tutorial'] #think of any other stuff here! 
	#may want to do own sentiment analysis - to do so  replace sentiment_analyzer 
	sentiment_analyzer = None
	
	def __init__(self, keyword_helper):
		self.stopwords = nltk.corpus.stopwords.words('english')
		self.sentiment_analyzer = nltk.sentiment.SentimentIntensityAnalyzer()
		self.keyword_helper = keyword_helper
	
	#motivation: https://realpython.com/python-nltk-sentiment-analysis/
	def get_sentiment(self,article):
		article.fetch_full_text() #comment out once we have done an async call on all relevant articles
		if type(article.full_text) != str:
			print("the text is not a string?")
			pdb.set_trace()
		#sentences = nltk.sentence_tokenize(article.full_text)
		score = self.sentiment_analyzer.polarity_scores(article.full_text) #we should do this on relevant sentences, not on the full text
		return score['compound'] # 0 means no sentiment at all (not positive or negative). 1 is good and -1 is  bad 
		
	#for fast filtering articles that have no relevant stuff in their title (prevents us doing 100s of web calls)
	def get_relevance(self,article):
		relevant_keys = self.keyword_helper.relevant_keys(article.title + ' ' + article.summary)
		if not relevant_keys:
			return 0.0 # well there's no keywords in the title/summary  
		return 1.0 #crude but works for now. 
	
	def get_keywords(self,article):
		##determine if this article is actually relevant first - perhaps look for things like filter_words and if there are none it might be relevant!
		relevant_keys = self.keyword_helper.relevant_keys(article.full_text)
	
	def get_type(self,article): 
		article.fetch_full_text()
		tokens = nltk.word_tokenize(article.title.lower() + ' ' + article.summary.lower()) 
		##need to do something to prevent webinar invites seeping through... 
		distribution = nltk.FreqDist([t for t in tokens if t not in self.stopwords])
		#TODO - use the distribution to assess relevance & reject things like values in filter_article
	








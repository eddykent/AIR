import datetime
import re


#import spacy
import nltk
import nltk.sentiment
from textblob import TextBlob

from typing import Optional,List
import numpy as np

from collections import namedtuple
from string import punctuation
import json

#test change
#from requests_html import HTMLSession

import pdb

from utils import ListFileReader, CurrencyPair

import web.client_sentiment_indicators as clisps
import web.feed_collector as feedco
from web.crawler import SeleniumHandler
from web.feed_collector import TextBias as Bias, TextType, TallyBias

from indicators.indicator import Indicator
import charting.chart_viewer as chv

KeywordMap = namedtuple('KeywordMap','keyword values')
RelevanceInfo = namedtuple('RelevanceInfo', 'degree direction keyword')
CalendarEvent = namedtuple('CalendarEvent','the_date description impact instrument previous consensus actual')

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
			instruments += lfr.read('fx_pairs/currencies.txt')
		self.instruments = instruments 
		self.sources = lfr.read('sources/sentiment_indicators.txt')
		self.findings = {pair:[] for pair in self.instruments}
	
	def fetch(self):
		result = []
		
		with SeleniumHandler(hidden=True) as handle:  #a selenium handler for any crawlers (scrapers won't need it though) 
			for source in self.sources:
				source_split = re.split('/|\.',source)
				client_sentiment_indicator = None
				if 'dailyfx' in source_split:
					client_sentiment_indicator = clisps.DailyFX(source,self.instruments)  #scraper
				elif 'forexclientsentiment' in source_split:
					client_sentiment_indicator = clisps.ForexClientSentiment(handle,source,self.instruments)  #crawler
				elif 'myfxbook' in source_split:
					client_sentiment_indicator = clisps.MyFXBook(source,self.instruments) #scraper
				elif 'dukascopy' in  source_split:
					client_sentiment_indicator = clisps.Dukascopy(handle,source,self.instruments) #crawler
				else:
					print('Parser not implemented for source: \n'+source)
					pdb.set_trace()
				result += client_sentiment_indicator.get_client_sentiment_info() if client_sentiment_indicator else []
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
		for instrument in self.findings: 
			#might want to include something about the timeframe? or the date? especially if we are reading anything historic
			csinfos = self.findings[instrument]
			tally = {} 
			for csi in csinfos:
				score = tally.get(csi.bias,0)
				score += 1
				tally[csi.bias] = score
			
			collected_result = TallyBias.collect(tally)
					
			self.collected_result[instrument] = collected_result


##not sure how this will work yet - could just be something that prevents trading at choppy times when 
##big news is about to comeresults out 
##OR it could be something that suggests a trade based on the economic calendar prediction - or both
class EconomicCalendar:
	
	events = [] 
	query = 'queries/economic_calendar.sql'
	instrument_map = {}
	
	def __init__(self):
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
	fsh = None
	
	def __init__(self,keyword_map_file=None,fsh=None):
		if keyword_map_file is not None:
			self.map_file = keyword_map_file
		lfr = ListFileReader()
		keyword_maps_str = lfr.read_full_text(self.map_file)
		keyword_maps = json.loads(keyword_maps_str)
		self.input_keyword_map = self.__construct_keyword_map(keyword_maps.items())
		self.bloated_keyword_map = self.input_keyword_map
		self.all_words_relevance = self.__generate_all_words(self.input_keyword_map)
		self.fsh = fsh if fsh else ForexSlashHelper()
	
	#if an article title or an article summary has any words that are interesting to us, it is relevant. 
	#otherwise we can probably filter it out to save computational resources! 
	#this step organises things for us to be able to update sentiments based on relevance and degree
	def relevant_keys(self,summary_text,degree=None):	
		#perhaps we should move all author name words from the article first to ensure we don't get false relevances XD
				
		textblob = TextBlob(self.fsh.strip_slashes(summary_text).lower())
		intersect = self.all_words_relevance.intersection(textblob.words)
		
		if not intersect:
			return {}
		
		relevant_keys = {} #check for second degree first 
		
		for keyword_mapping in self.bloated_keyword_map:
			keyword = keyword_mapping.keyword
			values = keyword_mapping.values		
			#check bloat values only for degree 2 relationships 
			for value in values:
				direction = 1 if self.bullish(value) else -1 if self.bearish(value) else 0
				if value.lower() in str(textblob):  #phrase-like not word like
					relevant_keys[keyword] = RelevanceInfo(2,direction,value)
		
		#then check for first degree - overwrite if exists
		for keyword_mapping in self.input_keyword_map:
			keyword = keyword_mapping.keyword
			values = keyword_mapping.values
			
			if keyword.replace('/','').lower() in textblob.words:
				relevant_keys[keyword] = RelevanceInfo(1,1,keyword) #it is obv bullish if the key is used so sentiment up => this key up 
			
			if '/' in keyword:
				continue #add hack to stop EVERYTHING becoming degree 1 for pairs - BUG TO FIX >:-/
			if values: 	#values is usually [] for input_keyword_map
				for value in values:
					if value and value.lower() in str(textblob):
						direction = 1 if self.bullish(value) else -1 if self.bearish(value) else 0
						relevant_keys[keyword] = RelevanceInfo(1,direction,value)
			
		return {k:v for k,v in relevant_keys.items() if v.degree == degree or degree is None}
	
	# set bloated keyword maps to have move values from previous key words etc 
	# example: if keyword 'USD' has a keyword value 'FEDERAL RESERVE' then we should add 'federal reserve' to GBP/USD etc
	def bloat(self):
		self.bloated_keyword_map = []
		build_this_dict = {} 
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
		return set([k.keyword.replace('/','').lower() for k in keyword_map] + [v.lower() for k in keyword_map for v in k.values])
	
	@staticmethod
	def __construct_keyword_map(keyword_map):
		#we also want to put in the actual key into the value right?
		#for keyword, values in keyword_map:
		return [KeywordMap(km[0],km[1]) for km in keyword_map]
	
	@staticmethod
	def bullish(value):
		return value == value.upper()
	
	@staticmethod
	def bearish(value):
		return value == value.lower()
	


#little class for removing slashes from forex names (eg USD/JPY -> USDJPY) so they are treated as a single token later on in NLP stuff
class ForexSlashHelper:
	
	fx_pairs = [] 
	
	def __init__(self,fx_pairs=[]):
		if not fx_pairs:
			lfr = ListFileReader()
			fx_pairs = lfr.read('fx_pairs/fx_mains.txt') # expand to all fx pairs? 
		self.fx_pairs = fx_pairs
	
	#nice crude function :) 
	#removes all / from FX names, and also adds a space after every \n to ensure words are picked up without them
	def strip_slashes(self,text):#
		text = text.replace('\\n','\n') #fix newlines 
		lines = text.split('\n')
		new_lines = []
		for line in lines:
			words = line.split()
			new_words = []
			for word in words:
				if word.upper() in self.fx_pairs:
					word = word.replace('/','')
				new_words.append(word)
			new_lines.append(' '.join(new_words)) 
		return ' \n '.join(new_lines) #add spaces after new line characters to cheat a little :) 
		
		
		
		

#Tool for doing all natural language stuff for passages found online. News storys are articles collected from a feed collector
#their text is then passed into this tool for further clarification. Is the story actually a buy/sell signal? Is it relevant? 
#is the author positive or negative about whatever it is they are talking about? What are the main key words we can use etc 
class TextAnalysis:
	
	stopwords = []
	keyword_helper = None ##use to help filter sentences etc 
	
	#filter_articles = ['seminar','video','tutorial'] #think of any other stuff here! 
	#may want to do own sentiment analysis - to do so  replace sentiment_analyzer 
	sentiment_analyzer = None
	fsh = None
	text_type_config = {}
	
	def __init__(self, keyword_helper=None, text_type_config_file='text_type_words.json'):
		self.stopwords = set(nltk.corpus.stopwords.words('english'))
		self.sentiment_analyzer = nltk.sentiment.SentimentIntensityAnalyzer()
		if keyword_helper is None:
			keyword_helper = KeywordMapHelper()#use default 
		self.keyword_helper = keyword_helper
		if callable(self.keyword_helper.bloat):
			self.keyword_helper.bloat() 
		lfr = ListFileReader()
		self.text_type_config = json.loads(lfr.read_full_text(text_type_config_file))
		self.fsh = ForexSlashHelper()
	
	#motivation: https://realpython.com/python-nltk-sentiment-analysis/
	def get_sentiment(self,passage_text):
		if type(passage_text) != str:
			print("the text is not a string?")
			pdb.set_trace()
		
		#sa = nltk.sentiment.SentimentIntensityAnalyzer()
		textblob = TextBlob(self.fsh.strip_slashes(passage_text).lower())
		polarity = self.sentiment_analyzer.polarity_scores(str(textblob))
		overall = {'subjectivity':float(textblob.sentiment.subjectivity),'polarity': float(polarity['compound'])}
		specifics = []
		for sentence in textblob.sentences:
			keys = self.keyword_helper.relevant_keys(sentence)
			if keys:
				polarity = self.sentiment_analyzer.polarity_scores(str(sentence))
				specifics.append((sentence,keys,{'subjectivity':float(sentence.sentiment.subjectivity),'polarity': float(polarity['compound'])}))
		return overall, specifics
	
	#use spacy to clean and lemmatize etc. Pass spacy in because it is a ballache to load 
	def create_feature_vector(self,passage_text,spacy_handler):
		passage_text = self.fsh.strip_slashes(passage_text).lower()
		#any other cleaning to do?
		
		doc = spacy_handler(passage_text)
		#either return doc.tensor #apparently dont use this?
		#or 
		return np.array([tok.vector for tok in doc if tok not in self.stopwords])
		
		
		
	#determine if a passage of text is actually a trading signal 
	def is_signal(self,some_text):
		#add to these as we discover more indicators that the text might be a signal
		
		textblob = TextBlob(self.fsh.strip_slashes(some_text.lower()))
		words = [w for w in textblob.words if w not in punctuation]
		new_text = ' '.join(words)
		
		if any(' {} '.format(o) in new_text for o in ['buy','sell']):
			if any(' {} '.format(o) in new_text for o in self.text_type_config['stop_loss_words']):
				if any(' {} '.format(o) in new_text for o in self.text_type_config['take_profit_words']):
					#pretty sus! we got a buy or sell together with a take profit and stop loss
					return True
		return False
	
	#use with is_tutorial - if there is a word in the title + summary then it is probably a tutorial. But check too with is_tutorial
	def tutorial_title(self,some_title_and_summary):
		textblob = TextBlob(some_title_and_summary.lower()) 
		return any(lw in textblob.words for lw in self.text_type_config['tutorial_words']) \
			or any(' {} '.format(ph) in some_title_and_summary.lower() for ph in self.text_type_config['tutorial_phrases'])
	
	#used in conjunction with tutorial_title(). A tutorial has lots of question words in it and has lots of referals to self or you 
	def is_tutorial(self,some_text): 
		
		textblob = TextBlob(self.fsh.strip_slashes(some_text.lower()))			
		personifiers = sum(textblob.word_counts[w] for w in self.text_type_config['personifiers'])
		questionables = sum(textblob.word_counts[w] for w in self.text_type_config['question_words'])
		
		divizor = len(textblob.words) ** 0.5
		
		return ((questionables + personifiers) / divizor) > 0.75 or (questionables / divizor) > 0.5 or (personifiers / divizor) > 0.5 



#make an indicator style news reading tool - it can call detect() and everything else just like any other indicator?
#or we pluralise filters. make them work on a particular time frame (eg 1h, 4h or 1d) 
class NewsIndicator(Indicator):
	
	timelines = {}
	instrument = 'AUD/CAD' #set the instrument before calling draw_snapshot as a hack to get it to fking work like an indicator
	article_collector = None
	text_analyser = None
	
	def __init__(self,article_collector,text_analyser):
		self.article_collector = article_collector #set up should read all news etc! 
		self.text_analyser = text_analyser
	
	def draw_snapshot(self,candle_stream : list ,snapshot_index : int = -1) -> chv.ChartView:
		this_view = chv.ChartView() 
		
		candle_stream_timeline = [c[-1] for c in candle_stream]
		start_date = candle_stream_timeline[0]
		end_date = candle_stream_timeline[-1]
		
		indexs = self._find_indexs(candle_stream_timeline)
		timeline = self.timelines.get(self.instrument,[])
		timeline = [t for t in timeline if t.the_date >= start_date and t.the_date < end_date]
		timeline = sorted(timeline,key=lambda x:x.the_date)
		maxy = max([c[1] for c in candle_stream])
		miny = min([c[2] for c in candle_stream])
		timefloats = {}
		for td, index in zip(timeline,indexs):
			if index is not None:
				timefloats[index] = self._timefloat(candle_stream_timeline[index],td.the_date,candle_stream_timeline[index+1])
		for td, index in zip(timeline,indexs):
			if index is None:
				continue
			timefloat = timefloats[index]
			x = index + timefloat - 0.5 #why not just do all like this :) - because the time will not marry up to the candles due to weekends etc
			line = chv.Line(x,maxy,x,miny)
			if td.bias in [Bias.SLIGHT_BEARISH,Bias.BEARISH]:
				this_view.draw('carets bearish lines',line)
			elif td.bias in [Bias.SLIGHT_BULLISH,Bias.BULLISH]:
				this_view.draw('carets bullish lines',line)
			else:
				this_view.draw('carets neutral lines',line)
		return this_view
	
	def _perform(self,candle_stream : list,candle_stream_index : Optional[int]=-1) -> np.array:
		#dont actually do anything with the candles as we are going to load in all the news instead & get sentiment 
		start_date = self.timeline[0][0]
		end_date = self.timeline[-1][0]
		#load from db not from web since we should have already cached it from the web
		#generate timelines with sentiment & topics etc
		self.article_collector.load_articles(start_date,end_date)
		self.article_collector.dedupe()
		self.article_collector.analyse_articles(self.text_analyser)
		self.timelines = self.article_collector.to_article_timelines() #what about findings? 
		
		
	
	def generate_setups(self,criteria : list) -> list:
		return [] #no setups are created from the news indicator - it is used as a filter instead
	
	
	def detect(self,criteria : list=[]) -> np.array:
		result = [0 for t in self.timeline] #only one channel? what about other instruments 
		pass #find way of returning 1 for a positive news story release and -1... 

	#helper function to get indexs from the candle stream of where the news stories are. 
	def _find_indexs(self,candle_stream_timeline):
		#draw carets onto the chart based on which instrument it is... 
		start_date = candle_stream_timeline[0]
		end_date = candle_stream_timeline[-1]
		timeline = self.timelines.get(self.instrument,[])
		#loop through candles and find where each news story is  
		timeline = [t for t in timeline if t.the_date >= start_date and t.the_date < end_date]
		candle_indexs = []
		timeline = sorted(timeline,key=lambda x:x.the_date)
		timeline_index = 0
		i = 0
		while i < len(candle_stream_timeline)-1:
			this_candle_start = candle_stream_timeline[i]
			next_candle_start = candle_stream_timeline[i+1]
			this_story = timeline[timeline_index]
			if this_story.the_date >= this_candle_start and this_story.the_date < next_candle_start:
				candle_indexs.append(i)
				timeline_index += 1 #it exits early because we get more than 1 news story in one candle! :(
				if timeline_index == len(timeline):
					break #must have found all the candle indexs now 
			else:
				i += 1
		return candle_indexs
	
	@staticmethod
	def _timefloat(dtl, dtc, dth):
		return (dtc.timestamp() - dtl.timestamp()) / (dth.timestamp() - dtl.timestamp()) if dth != dtl else 0

	


















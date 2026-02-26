import datetime
import re
import zlib
import hashlib
import json
from typing import List
from dataclasses import dataclass, fields

#textblob

from tqdm import tqdm

from air.data.tools.cursor import Database, Inject

sql = {}


import pdb

##format of what will be returned from scraping

#data class for holding a news article and reading/writing it to the database compressed 
#deprecate this class and use NewsArticle instead - we want to make this class only view from the db
#reading from the web and into DB should be done separately - segragate duties 
#delete asap - fuck compression
class Article:
	the_date = None
	title = None 
	summary = None
	author = None #might be useful? 
	link = None
	idlink = None #these same? 
	source_title = None
	source_ref = None
	full_text = None #dynamically grabbed using requests object if needed 
	__lazy_load = True
	instruments = [] #what this article talks about 
	
	
	TITLE_HEAD_LEN = 50
	
	sql_row = "(%(hash_identifier)s,%(published_date)s,%(source_ref)s,%(title_head)s,%(compression)s)"
	
	def __init__(self,the_date,author,title,summary,source_title,link):
		self.the_date = the_date
		self.author = author
		self.title = title
		self.summary = summary
		self.link = link
		self.source_title = source_title
		#get source_id
		try:
			bits = re.split('//|/|\?',self.link)
			servername = bits[1]
			self.source_ref = servername.lower().replace('www.','')
			
		except (ValueError,IndexError) as e:
			log.warning(f"unable to extract a pretty source ref from {self.link}.\nUsing the full link as the source ref.",exec_info=True)
			self.source_ref = link # not specific enough :( 
	
	@classmethod   #for json compression 
	def relevant_properties(self):
		return ['title','summary','author','link','source_title','full_text']
	
	def relevant_values(self): #everything that is returned in the json for compression 
		
		the_dict = self.__dict__
		props = self.relevant_properties()
		article_data = { prop:the_dict[prop] for prop in self.relevant_properties() }
#			'title': self.title,
#			'summary':self.summary,
#			'author':self.author,
#			'link':self.link,
#			'source_title':self.source_title,
#			'full_text':self.full_text
#		}
		return article_data
	
	
	def __repr__(self):
		return 'Article('+self.source_ref + ' - ' + self.title+')'
	
	
	@staticmethod 
	def filter_old(links):
		#from list of links, check which ones we do NOT have in the database 
		return links 
	
	@staticmethod
	def from_rss_entry(entry):
		this_article = None
		struct_time = None
		if 'published_parsed' in entry:
			struct_time = entry.published_parsed
		elif 'updated_parsed' in entry:
			struct_time = entry.updated_parsed
		if 'author' not in entry:#no author? no problem! 
			entry.author = entry.source_title

		try:
			assert struct_time is not None, "Unable to get the published date from this article"
			assert entry.author is not None, "No author detected"
			assert entry.title is not None, "No title detected"
			assert entry.summary is not None, "No summary detected" 
			assert entry.link is not None, "No link detected"
			assert entry.source_title is not None, "No source title detected"
			
			this_article = Article(
				datetime.datetime.fromtimestamp(time.mktime(struct_time)),
				entry.author,
				entry.title,
				entry.summary,
				entry.source_title,
				entry.link
			)
		except Exception as e:
			log.error('Missing data on one of the feeds.',exec_info=True)
		
		if 'content' in entry:
			this_article.full_text = entry.content[0].value			
			this_article.__lazy_load = False
		
		return this_article
	
	@staticmethod 
	def from_dict(article_data):
		publish_date = article_data['the_date'] #turn to datetime
		if article_data.get('summary') is None:
			article_data['summary'] = article_data['full_text'][:150]
		this_article = Article(
			publish_date, 
			article_data['author'],
			article_data['title'],
			article_data['summary'],
			article_data['source_title'],
			article_data['link']
		)
		this_article.full_text = article_data['full_text']
		this_article.source_ref = article_data['source_ref']
		this_article.__lazy_load = False
		return this_article
		
	
	@staticmethod
	def from_database_row(row):
		guid, md5_hash, publish_date, source_ref, title_head, compressed, captured_date, instruments, idlink = row #unpack the row
		decompressed_json = zlib.decompress(compressed).decode()
		article_data = json.loads(decompressed_json)
		this_article = Article(
			publish_date,
			article_data['author'],
			article_data['title'],
			article_data['summary'],
			article_data['source_title'],
			article_data['link']
		)
		this_article.full_text = article_data['full_text']
		this_article.source_ref = source_ref
		this_article.idlink = idlink, 
		this_article.instruments = instruments
		this_article.__lazy_load = False
		return this_article
		
	#deprecate? - wrong place?
	def to_database_row(self):
		#keep in here all stuff we want to compress - we don't want to hold shit loads of crap in the database :)
		article_data = self.relevant_values()
		json_bytes = json.dumps(article_data).encode()
		compressed_bytes = zlib.compress(json_bytes)
		md5_hash = hashlib.md5(json_bytes).hexdigest()
		title_head = self.title[:self.TITLE_HEAD_LEN] #for human readability in the database 
		
		#also perform a check to see if we have an article in the database but the fulltext = article.title + ' ' + article_summary
		check_data = article_data
		check_data.update({'full_text':self.full_text_fallback()})
		md5_check = hashlib.md5(json.dumps(check_data).encode()).hexdigest() #why? just use link!
		
		return {
			'hash_identifier':md5_hash,
			'published_date':self.the_date,  
			'source_ref':self.source_ref,
			'title_head':title_head,
			'compression':compressed_bytes,
			'hash_check':md5_check, #this is deleted 
			'idlink':self.idlink,
			'instruments':self.instruments
		}
	
	
	#@staticmethod
	#def from_tweet(tweet):
	#def from_subreddit(item):
	
	def full_text_fallback(self):
		return self.title + ' ' + self.summary
	
	#page_parsers are scrapers classes we can create & differentiate using the source_ref
	#take this out and put into scraper instead? - article should just be an interface class to the DB 
	#def fetch_full_text(self,specialist_scraper=None): #make async?
	#
	#	if self.full_text is not None: #we already got the full text! :) 
	#		return 
	#		
	#	if not specialist_scraper:
	#		if self.source_ref == 'dailyfx.com':
	#			specialist_scraper = DailyFXNews
	#		if self.source_ref == 'fxstreet.com':
	#			specialist_scraper = FXStreet
	#		if self.source_ref == 'forexlive.com':   #TODO - but the news is very small! 
	#			specialist_scraper = ForexLive
	#		if self.source_ref == 'forexcrunch.com':
	#			specialist_scraper = ForexCrunch
	#	
	#	if specialist_scraper: 
	#		scraper = specialist_scraper(self.link)
	#		self.full_text = scraper.scrape()
	#		if self.full_text == '':
	#			log.warning(f"full_text was blank when scraping {self.link}. Using the title and summary instead.")
	#			self.full_text = self.full_text_fallback()
	#	else:
	#		log.warning(f"Unable to get full_text for {self.link}. Using the title and summary instead.")
	#		self.full_text = self.full_text_fallback() #crude but will do for now
	
	#no idea why ever this function would  be used 
	def reset(self):
		if self.__lazy_load: 
			self.full_text = None
		self.relevance_score = None 
		self.sentiment_scores = None 
		self._relevant_keys = {}

@dataclass   #frozen?
class NewsArticle:
	
	link : str
	title : str
	summary : str
	published_date : datetime.datetime
	author : str
	source_ref : str
	full_text : str
	instruments : List[str] #freeze?
	
	#columns = ['link','title','summary','published_date','author','source_ref','full_text','instruments'] 
	sql_row = "(%(link)s,%(title)s,%(summary)s,%(published_date)s,%(author)s,%(source_ref)s,%(full_text)s,%(instruments)s)"
	
	
	@staticmethod
	def link_to_src_ref(link):
		bits = re.split('//|/|\?',link)
		servername = bits[1]
		return servername.lower().replace('www.','') 
	
	
	@staticmethod
	def from_database_row(row):
		pass
	
	@staticmethod
	def from_dict(the_dict):
		return NewsArticle(*[the_dict[k] for k in [field.name for field in fields(NewsArticle)]])
	
	
	def to_database_row(self,cur):
		pass 
	

#helper classes  - for a piece of text, tell me what instruments it is associated with 
#class AssociativeKeywordInstrumentMap  #more complex - further work. "this news story impacts this instrument positively/negatively"

#map for saying "this news story directly is about this instrument" 
class DirectKeywordInstrumentMap:
	
	non_space_keyword_instrument_map = {} #many to 1 rel
	instruments = []
	
	#stick to FX for now, use named entities for stocks later
	def __init__(self, fx_pairs=[]): ##perhaps other can be passsed here  
		
		for fx_pair in fx_pairs:
			self.non_space_keyword_instrument_map[fx_pair] = fx_pair
			self.non_space_keyword_instrument_map[fx_pair.lower()] = fx_pair
			self.non_space_keyword_instrument_map[fx_pair.replace('/','')] = fx_pair
			self.non_space_keyword_instrument_map[fx_pair.replace('/','').lower()] = fx_pair
			
			#add to ensure we capture things like "USD/CAD,"
			self.instruments.extend(fx_pairs)
		
	#from a piece of text, get what instruemnts it might be talking about 
	def get_relevent_instruments(self, text):
					
		instruments = self._space_based_matchings(text) 
		instruments += self._phrasal_based_matchings(text) #eg "bank of england", "Tesla Motors?" 
		
		return sorted(list(set(instruments)))
		
	
	def _space_based_matchings(self,text):
		instruments = []
		text_words = text.split(' ') #\n? \t?
		for k,i in self.non_space_keyword_instrument_map.items():
			if k in text_words:
				instruments.append(i)
		return instruments
	
	def _phrasal_based_matchings(self,text):
		return [instrument for instrument in self.instruments if instrument in text]




















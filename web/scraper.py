
import requests_html
import datetime
import time
import re
import zlib
import hashlib
import json

from enum import Enum
from collections import namedtuple


import pdb




##format of a scraper object - a simple class that 'has a' html parsed inside it 
##client_sentiment_scraper objects inherit this
class Scraper:
	
	source = ''
	html = None
	#session = None
	
	def __init__(self,source):
		self.change_link(source)
	
	##function to override to get stuff from a website that we want
	def scrape(self):
		raise NotImplementedError('This method must be overridden')
	
	def change_link(self,link):
		self.source = link
		session = requests_html.HTMLSession()
		response = session.get(self.source)
		self.html = response.html


##format of what will be returned from scraping
class Article:
	the_date = None
	title = None 
	summary = None
	author = None #might be useful? 
	link = None
	source_title = None
	source_ref = None
	full_text = None #dynamically grabbed using requests object if needed 
	__lazy_load = True
	
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
			self.source_ref = link # not specific enough :( 
	
	@classmethod
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
			print('Oh dear - it looks like some stuff is missing on one of the feeds.')
			print(e)
			pdb.set_trace()
		
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
		guid, md5_hash, publish_date, source_ref, title_head, compressed, captured_date = row #unpack the row
		article_data = json.loads(zlib.decompress(compressed).decode())
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
		this_article.__lazy_load = False
		return this_article
		
	
	def to_database_row(self):
		#keep in here all stuff we want to compress - we don't want to hold shit loads of crap in the database :)
		article_data = self.relevant_values()
		json_bytes = json.dumps(article_data).encode()
		compressed_bytes = zlib.compress(json_bytes)
		md5_hash = hashlib.md5(json_bytes).hexdigest()
		title_head = self.title[:50] #for human readability in the database 
		
		#also perform a check to see if we have an article in the database but the fulltext = article.title + ' ' + article_summary
		check_data = article_data
		check_data.update({'full_text':self.full_text_fallback()})
		md5_check = hashlib.md5(json.dumps(check_data).encode()).hexdigest()
		
		return {
			'hash_identifier':md5_hash,
			'published_date':self.the_date,  
			'source_ref':self.source_ref,
			'title_head':title_head,
			'compression':compressed_bytes,
			'hash_check':md5_check #this is deleted 
		}
	
	
	#@staticmethod
	#def from_tweet(tweet):
	#def from_subreddit(item):
	
	def full_text_fallback(self):
		return self.title + ' ' + self.summary
	
	#page_parsers are scrapers classes we can create & differentiate using the source_ref
	def fetch_full_text(self,specialist_scraper=None): #make async?

		if self.full_text is not None: #we already got the full text! :) 
			return 
			
		if not specialist_scraper:
			if self.source_ref == 'dailyfx.com':
				specialist_scraper = DailyFXNews
			if self.source_ref == 'fxstreet.com':
				specialist_scraper = FXStreet
			if self.source_ref == 'forexlive.com':   #TODO - but the news is very small! 
				specialist_scraper = ForexLive
			if self.source_ref == 'forexcrunch.com':
				specialist_scraper = ForexCrunch
		
		if specialist_scraper: 
			scraper = specialist_scraper(self.link)
			self.full_text = scraper.scrape()
			if self.full_text == '':
				print("We are not able to get the full_text for "+self.link)
				#pdb.set_trace()
				self.full_text = self.full_text_fallback()
		else:
			print("We are not able to get the full_text for "+self.link)
			pdb.set_trace()
			self.full_text = self.title + ' ' + self.summary #crude but will do for now
	
	#no idea why ever this function would  be used 
	def reset(self):
		if self.__lazy_load: 
			self.full_text = None
		self.relevance_score = None 
		self.sentiment_scores = None 
		self._relevant_keys = {}

			
class DailyFXNews(Scraper):
	
	def scrape(self):
		
		article_body = self.html.xpath("//*[@class='dfx-articleBody']") #change if website changes!
		full_text = ''
		
		if article_body:
			full_text = article_body[0].text
			if full_text == '':
				possible_video = article_body[0].xpath(".//*[contains(@class,'youTubeVideo')]")
				if possible_video:
					full_text = 'VIDEO'
		return full_text

class FXStreet(Scraper):
	
	def scrape(self):
		short_article_body = self.html.xpath("//*[@class='fxs_article_content']") #change if website changes!
		
		if not short_article_body:
			return '' #report error
			
		all_anchs = short_article_body[0].find('a')
		readmores = [a for a in all_anchs if a.text.lower().startswith('read more')]
		
		if not readmores:
			return short_article_body[0].text 
			
		read_more_links = readmores[0].xpath("//@href")
		if not read_more_links:
			return short_article_body[0].text
			
		self.change_link(read_more_links[0])
		
		full_text = ''
		story_body = self.html.xpath("//*[@class='fxs_article_content']")
		if story_body:
			full_text = story_body[0].text
		return full_text


##this one doesnt give much info so currently using the title + summary 
##todo - this is not actually the case! There are commonly some articles that have some useful stuff in them!
class ForexLive(Scraper):
	
	def scrape(self):
		article_elems = self.html.xpath("//article")
		if not article_elems:
			return ''
		ps = article_elems[0].xpath("//p")
		return '\n'.join([p.text for p in ps])
		
		

#this one again was a bit weird
class ForexCrunch(Scraper):
	
	def scrape(self):
		entry_content = self.html.xpath("//div[@class='entry-content']")
		if not entry_content:
			pdb.set_trace()
			return ''
		ps = entry_content[0].xpath("//p[@class='p3']") + entry_content[0].xpath("//p[@class='p4']") + entry_content[0].xpath("//p[@class='p6']")
		if not ps:
			ps = entry_content[0].find('p')
		return '\n'.join([p.text for p in ps])

	

















import requests_html
import datetime
import time
import re

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
	_relevant_keys = {} 
	relevance_score = None
	sentiment_score = None
	
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
			assert struct_time, "Unable to get the published date from this article"
			assert entry.author, "No author detected"
			assert entry.title, "No title detected"
			assert entry.summary, "No summary detected" 
			assert entry.link, "No link detected"
			assert entry.source_title, "No source title detected"
			
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
		
	
	
	#@staticmethod
	#def from_tweet(tweet):
	#def from_subreddit(item):
	
	#page_parsers are scrapers classes we can create & differentiate using the source_ref
	def fetch_full_text(self,specialist_scraper=None): #make async?

		if self.full_text is not None: #we already got the full text! :) 
			return 
			
		if not specialist_scraper:
			if self.source_ref == 'dailyfx.com':
				specialist_scraper = DailyFXNews
			if self.source_ref == 'fxstreet.com':
				specialist_scraper = FXStreet
			#if self.source_ref == 'fxstreet.com':   #TODO - but the news is very small! 
			#	specialist_scraper = FXStreet
			if self.source_ref == 'forexcrunch.com':
				specialist_scraper = ForexCrunch
		
		if specialist_scraper: 
			scraper = specialist_scraper(self.link)
			self.full_text = scraper.scrape()
			if self.full_text == '':
				print("We are not able to get the full_text for "+self.link)
				pdb.set_trace()
				self.full_text = self.title + ' ' + self.summary
		else:
			if self.source_ref not in ['forexlive.com']:  #refs that don't need a scraper as their content is very small 
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
class ForexLive(Scraper):
	
	def scrape(self):
		pdb.set_trace()

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

	
















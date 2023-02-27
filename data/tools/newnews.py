

import multiprocessing
from multiprocessing import Process, Queue
from typing import List
import datetime
import time
import re
import feedparser

import pandas as pd
##file for handling reading from a number of news sources and putting the articles into the database 
##if the link is already in the database, the news article is ignored to prevent spamming news websites 
##multiprocessing - does many at once so this can be ran prior to performing calculations 

#1) find the news links from various sources (multi-process)
#2) check the database if the links are already there (and housekeeping - eg is full text blank?)
#3) read all the news data from the list of links (multi-process) 


import pdb 

from web.scraper import Scraper 
from web.crawler import Crawler #for more complex news grabbing tasks

from utils import TimeHandler

NOW = datetime.datetime.now()

sql = {}

#get the contents of the page as a string into "full_text" field 
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
	
	def get_date_str(self):
		time_obj = self.html.xpath("//span[@class='fxs_entry_metaInfo']/time")[0]
		return time_obj.attrs['datetime']
	
	def scrape(self):
		#if text_ln
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




#list of scrapers to get the current set of news and create into news fetch tasks 
class NewsFinder(Scraper):
	pass
	#def __init__(self,*args,**kwargs):
	#	super().__init__(*args,**kwargs,render=True) #allowed?
	
	

class FXStreetSearch(NewsFinder):
	
	#old daily url (shame it doesnt exist anymore)
	#daily_url_str = 'https://www.fxstreet.com/news/all?date={year:0>4}-{month:0>2}-{day:0>2}' 
	
	fxs_search_url = "https://www.fxstreet.com/news?q={instrument}&hPP={limit}&idx=FxsIndexPro&p=0"
	
	@staticmethod
	def get_url(instrument,limit=500):
		return FXStreetSearch.fxs_search_url.format(instrument=instrument,limit=limit)
	
	def scrape(self):
		self.render(wait=5) 
		items = self.html.xpath("//main[@id='hits']//div[@class='ais-hits--item']")
		article_data = []
		for item in items:
			
			title_link = item.xpath(".//article//h4//a")
			if len(title_link) == 0:
				continue #debug? log? pdb? 
			
			title = title_link[0].text
			link = title_link[0].attrs['href']
			
			meta = item.xpath(".//*[@class='fxs_entry_metaInfo']")
			if not meta:
				continue
			
			author_box = meta[0].xpath(".//*[@class='fxs_article_author']")	
			author = None
			the_date = None 
			if author_box:
				author = author_box[0].text
			#datetime_box =  meta[0].xpath("/time[@datetime]") #nt found.. 
			
			
			article_data.append({
				'title':title,
				'the_date':None, #leave blank here since cant find it 
				'author':author,
				'link':link,
				'source_ref':'fxstreet.com'
			})
			
		return article_data		
			
			
	

class DailyFXArchive(NewsFinder):

	monthly_url_str = 'https://www.dailyfx.com/archive/{year:0>4}/{month:0>2}'
	
	
	@staticmethod
	def get_url(monthyear):  #consider going up a level to NewsLoader - not here! put in News() or somewhere
		m, y = monthyear
		url  = DailyFXArchive.monthly_url_str.format(year=y,month=m)
		return url 
	
	@staticmethod
	def handle_date(full_date_str):
		return datetime.datetime.strptime(full_date_str,"%d %B, %Y (%A) @%I:%M %p +00:00")
	
	def scrape(self):
		
		self.html.render() 
		#get all sections so we can create a list of hyperlinked 
		sections = self.html.xpath("//div[@class='dfx-archiveList']/section[@class='my-6']")
		#pdb.set_trace()
		article_data = []
		
		for section in sections:	
			date_header = section.xpath(".//h2[contains(@class,'text-black')]")
			article_list = section.xpath(".//div[contains(@class,'dfx-articleList')]")
			if date_header and article_list:
				date_str = date_header[0].text #turns out this isnt needed
				article_hyperlinks = article_list[0].xpath(".//a[contains(@class,'dfx-articleListItem')]")
				for article_hyperlink in article_hyperlinks:
					#pdb.set_trace()
					
					article_url = article_hyperlink.attrs.get('href') if article_hyperlink.attrs else None
					
					title = article_hyperlink.xpath(".//span[contains(@class,'dfx-articleListItem__title')]")
					the_time= article_hyperlink.xpath(".//span[contains(@class,'jsdfx-articleListItem__date')]")
					author = article_hyperlink.xpath(".//span[contains(@class,'jsdfx-articleListItem__author')]")
					
					article_title = title[0].text
					article_time = the_time[0].text
					article_author = author[0].text.replace(' by ',' ')[1:].strip()
					#try:
					full_date_str = date_str+' @'+article_time 
					the_date = self.handle_date(full_date_str)
					
						#TimeHandler.from_str_2(article_time)
					#except:					
					article_data.append({
						'title':article_title,
						'the_date':the_date,
						'author':article_author,
						'link':article_url,
						'source_ref':'dailyfx.com'
						#'source_ref':source_ref,
						#'source_title':source_title
					})
					
		#pdb.set_trace()			
		return article_data	

#cheat class for getting articles from rss feeds - faster than what we had before! :) 
class RSSFeedParser(NewsFinder):
	
	@staticmethod
	def link2sref(link):
		bits = re.split('//|/|\?',link)
		servername = bits[1]
		return servername.lower().replace('www.','') 
		
	def extract_date(self,entry,source_ref):
		the_date = None 
		if 'updated_parsed' in entry:
			the_date = datetime.datetime.fromtimestamp(time.mktime(entry['updated_parsed']))
		elif 'published_parsed' in entry:
			the_date = datetime.datetime.fromtimestamp(time.mktime(entry['published_parsed']))
		#if the_date is None:
		#	raise ValueError('Unable to get the date')
		return the_date #dont care about null dates? 
	
	def extract_author(self,entry,source_ref):
		author = None
		if 'authors' in entry:
			author = entry['authors'][0]['name']
		if 'author' in entry:
			author = entry['author']
		return author #dont care about null authors
	
	def extract_title(self,entry,source_ref):
		return entry['title']
	
	def extract_link(self,entry,source_ref):
		return entry['link']
	
	def scrape(self):
		source_ref = self.link2sref(self.source)
		parsed = feedparser.parse(self.source)
		article_data = [] 
		
		print(source_ref)
				
		for entry in parsed.get('entries',[]):
		
			title = self.extract_title(entry,source_ref)
			the_date = self.extract_date(entry,source_ref)
			author = self.extract_author(entry,source_ref)
			link = self.extract_link(entry,source_ref)
			
			article_data.append({
				'title':title,
				'the_date':the_date,
				'author':author,
				'link':link,
				'source_ref':source_ref
			})
			
		return article_data
		
	
	
#from a set of news loaders, identify and get news items that can be passed to a news fetch worker 
##The purpose of this task is to get a load of new links to news articles that we do not already have, ready for loading into the db 
class News: #turn into multi-process! 

	
	news_finders : List[NewsFinder]
	
	def __init__(self,news_finders,cur):
		self.news_finders = news_finders 
		
	@staticmethod
	def get_months_years(date_from,date_to):
		myds = pd.period_range(start=date_from,end=date_to,freq='M')
		return [(my.month,my.year) for my in myds]
	
	#deprecate once multiprocess 
	def get_items(self):
		
		#months_years = self.get_months_years(date_from,date_to)
		news_items = [] 
		
		for news_loader in self.news_finders:
			#if news_loader.monthy_url:
			#	for my in months_years:
					#news_loader.set_month_year(my)
			news_items += news_loader.scrape() 
		
		return news_items # News.filter_old(self.cur,news_items)
	
	#MOVE TO news selection - process that decorates with instrument and also filters the news items based on database  
	@staticmethod #use after we got all the links from the headlines (rss, fxstreet & dailyfx)
	def filter_old(cur,news_items):
		links = [ni['link'] for ni in news_items]
		cur.execute(sql['new_links'],{'links':links})
		new_links = [nl[0] for nl in cur.fetchall()]
		return [ni for ni in news_items if ni['link'] in new_links]
		
#multiprocess version of News? (refactor into ProcessPool & ProcessWorker classes) for Dukascopy, NewsSnatcher and this) 

#class for decorating news stories with an instrument, checking for irrelevant articles (eg tutorials) and checking against the db if the news has already been captured 
#class NewsItemProcessor:
#	pass

#class for performing a news fetch task - Scrape, crawl or both depending on phase (first scrape jobs then crawl jobs) 
class NewsFetchWorker: #(ProcessWorker) 
		
	news_queue = None 
	news_results = None
	
	def set_queues(self,news_queue, news_results):
		self.news_queue = news_queue
		self.news_results = news_results
	
	#def pre_loop(self):
	#	pass
	
	def run(self):
		
		looping = True
		
		while looping:
			 
			news_task = self.news_queue.get()
			
			if news_task is not None:
				#try
				self.perform_task(news_task) 
			else:
				looping = False #indicate that we are done 
			
			self.news_queue.task_done()
		
	
	def perform_task(self):
		#use scraper/crawler to get the text 
		pass
	
	def __call__(self,**kwargs): #absorb args
		self.run()


#from a load of links from News, get all the news stories (multiprocess) and put them into the database
class NewsSnatcher:
	
	pool_size = 1
	#browser_threads = None #store available browsers 
	worker_pool = []
	browser_threads = []
	startup_wait = 0.5 # wait this long to ensure no spam of dukascopy and disconnect 
	
	news_queue = None #store all data processing tasks 
	news_results = None
	
	def __init__(self, pool_size=None):
		if pool_size is not None:
			self.pool_size = pool_size
	
	#make a load of selenium handlers and put them in the pool 
	def setup(self,configs=[]):
		#account setups
		config = Configuration() #use configs 
		username = config.get('dukascopy','username')
		password = config.get('dukascopy','password')
		fetch_details = {'username':username, 'password':password} 
		
		
		for i in range(self.pool_size):
			#setup selenium objects here
			worker = NewsFetchWorker(i,credentials)
			self.worker_pool.append(worker)
			#pass
		
		#put into worker threads? 		
		
	def get_instruments(self,instruments,date_from,date_to=NOW):
		
		start_tasks = [] 
		
		for instrument in instruments:
			start_tasks.append({'instrument':instrument,'date_from':date_from,'date_to':date_to})
		self.perform(start_tasks)
			
	def perform(self,news_tasks):
		
		self.setup()
		
		self.browser_threads = [] #flat list of available browsers 
		manager = multiprocessing.Manager()
		self.news_queue = manager.Queue() 
		self.news_results = manage.Queue()
		
		
		
		for news_task in news_tasks: 
			self.news_queue.put(news_task)

		#start threads 
		for worker in self.worker_pool:
		#or i in range(self.pool_size):
			#worker = CandleTaskProcess(i,self.task_queue)
			worker.set_queues(self.news_queue,self.news_results)
			
			#worker()#for debugging 
			
			browser_thread = Process(target=worker,args={})
			browser_thread.start()
			self.browser_threads.append(browser_thread)
			if self.startup_wait:
				time.sleep(self.startup_wait) 
		
		
		##should now be running all at once
		#wait until completion 
		while not self.news_queue.empty():
			time.sleep(1) #keep checking if  the queue is empty or not and when it is, tear down 
		
		self.tear_down() 
	
	def tear_down(self):
		#print('TEAR DOWN CALLED')
		
		for worker in self.browser_threads: 
			self.news_queue.put(None) #flag a worker to finish
			
		for worker in self.browser_threads: 
			worker.join() 
	
	
	
	
	

sql['new_links'] = """
WITH links AS (
	SELECT UNNEST(%(links)s) AS link
)
SELECT link FROM links ls WHERE NOT EXISTS (
	SELECT 1 FROM news_article na WHERE na.link = ls.link
);
"""

sql['outdated_links'] = """

"""


sql['empty_links'] = """

"""



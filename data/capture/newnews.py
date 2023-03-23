
from enum import Enum
from collections import defaultdict
import multiprocessing
import lxml
#from multiprocessing import Process, Queue
from typing import List
import datetime
import time
import re
import feedparser
from tqdm import tqdm
import itertools

import psycopg2
import pandas as pd
##file for handling reading from a number of news sources and putting the articles into the database 
##if the link is already in the database, the news article is ignored to prevent spamming news websites 
##multiprocessing - does many at once so this can be ran prior to performing calculations 

#1) find the news links from various sources (multi-process)
#2) check the database if the links are already there (and housekeeping - eg is full text blank?)
#3) read all the news data from the list of links (multi-process) 


import pdb 

from web.scraper import Scraper 
from web.crawler import Crawler, SeleniumHandler #for more complex news grabbing tasks

from data.tools.cursor import Inject

from data.tools.processpool import ProcessPool, ProcessWorker
from utils import TimeHandler, overrides

from data.text import NewsArticle

import logging 
log = logging.getLogger(__name__)

NOW = datetime.datetime.now()

sql = {}



def safe_float(string):
	try:	
		return float(re.sub('[^0-9.\-+]','',string))
	except ValueError as ve:
		pdb.set_trace()
		log.warning(f"'{string}' was not able to be converted to float. Returning None")
		#log.warning(''.join(traceback.format_tb(ve.__traceback__))) #cant get where it was called from :(
		return None
		
		
def safe_int(string):
	try:	
		return int(float(re.sub('[^0-9.\-+]','',string)))
	except ValueError as ve:
		pdb.set_trace()
		log.warning(f"'{string}' was not able to be converted to int. Returning None")
		#log.warning(''.join(traceback.format_tb(ve.__traceback__)))
		return None



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
		
		return {'full_text':full_text}

class FXStreet(Scraper):
	
	def get_date_str(self):
		time_obj = self.html.xpath("//span[@class='fxs_entry_metaInfo']/time")[0]
		return time_obj.attrs['datetime']
	
	def scrape(self):
		#if text_ln
		#render?
		result = {'full_text':None}
		
		short_article_body = self.html.xpath("//*[@class='fxs_article_content']") #change if website changes!
		
		the_date_str = self.get_date_str()
		
		the_date = datetime.datetime.strptime(the_date_str,"%Y-%m-%dT%H:%M:%SZ")
		result['the_date'] = the_date
		
		
		if not short_article_body:
			return result 
			
		all_anchs = short_article_body[0].find('a')
		readmores = [a for a in all_anchs if a.text.lower().startswith('read more')]
		
		if not readmores:
			result['full_text'] = short_article_body[0].text 
			return result
			
		read_more_links = readmores[0].xpath("//@href")
		if not read_more_links:
			result['full_text'] =  short_article_body[0].text
			return result
			
		self.change_link(read_more_links[0])
		
		full_text = ''
		story_body = self.html.xpath("//*[@class='fxs_article_content']")
		if story_body:
			result['full_text'] = story_body[0].text
				
		return result


##this one doesnt give much info so currently using the title + summary 
##todo - this is not actually the case! There are commonly some articles that have some useful stuff in them!
class ForexLive(Scraper):
	
	def scrape(self):
		article_elems = self.html.xpath("//article")
		if not article_elems:
			return ''
		ps = article_elems[0].xpath("//p")
		full_text = '\n'.join([p.text for p in ps])
		
		return {'full_text':full_text} 
		
		

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
		full_text = '\n'.join([p.text for p in ps])
		return {'full_text':full_text} 


class FXCO(Scraper):	

	def scrape(self):
		
		content = self.html.xpath("//div[contains(@class,'block-article__body')]/p/text()")
		return {'full_text':'\n'.join(content)}
		

class ActionForex(Scraper):
	
	def scrape(self):
		
		html = lxml.etree.HTML(self.html.html)
		
		content = html.xpath(".//div[contains(@class,'td-post-content')]//p/text()")
		return {'full_text':'\n'.join(content)}

#class BabyPips
#class FXEmpire https://www.fxempire.com/
#class LeapRate


#scrapers to get all the headlines as news fetch tasks from a set of urls 
class NewsFinder(Scraper):
	pass
	

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
	def get_months_years(date_from,date_to):
		myds = pd.period_range(start=date_from,end=date_to,freq='M')
		return [(my.month,my.year) for my in myds]
	
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

class FXCOHeadlines(Crawler): #might be able to turn into scraper

	url = 'https://www.fx.co/en/top-articles'
	url_base = 'https://www.fx.co'
	
	
	@staticmethod
	def get_url(days_back=0):
		offset_str = f"?offset={days_back}" if days_back else ""
		return 'https://www.fx.co/en/top-articles' + offset_str 
	
	
	@staticmethod
	def get_text(elems):
		return '\n'.join(''.join(e.itertext()) for e in elems)
	
	#def load_articles(self):
	#	self.scroll_lazy_load(repeats=20,steps=30,wait=0.01) #repeats 30
	
	def crawl(self):
		#self.load_articles()
	
		article_data = []		
		
		html = lxml.etree.HTML(self.browser.page_source)
		article_banners = html.cssselect("a.block-article-feed__item")
		for article_banner in article_banners:

			try:
				title_l = article_banner.xpath(".//h2[contains(@class,'block-article-feed__title')]") #get all text
				author_l = article_banner.xpath(".//div[contains(@class,'block-article-feed__author')]/object/a")
				summary_l = article_banner.xpath(".//div[contains(@class,'block-article-feed__description')]") #get all text
				
				timestamp_l = article_banner.xpath(".//div[contains(@class,'block-article-feed__date')]/span/@data-timestamp")
				link_l = article_banner.xpath("@href")
				
				title = self.get_text(title_l)
				author = self.get_text(author_l)
				summary = self.get_text(summary_l)
				link = self.url_base + link_l[0] if link_l[0] and not link_l[0].startswith('http') else link_l[0]
				
				the_date = datetime.datetime.utcfromtimestamp(safe_int(timestamp_l[0]))
				
				##sample 
				article = {
					'title':title,
					'summary':summary,
					'the_date':the_date,
					'author':author,
					'link':link,
					'source_ref':'fx.co'
				}
				article_data.append(article)
			except Exception as e:
				log.warning(f"Failed to read an article banner - {str(e)}")
		
		return article_data
		
	
class ForexLiveHeadlines(NewsFinder):
	
	URL = "https://www.forexlive.com"#page/{page}"
	
	@staticmethod
	def get_url(page=0):
		pagestr = '/'
		if page > 0:
			pagestr = f"/page/{page}"
		return FXLiveHeadlines.URL + pagestr
		
	def scrape(self):
		article_data = []		
		
		self.render()
		
		html = lxml.etree.HTML(self.html.html)
		article_banners = html.cssselect("div.article-list__item-wrapper")
		for article_banner in article_banners:
			try:
				#pdb.set_trace()
				title_l = article_banner.xpath(".//h3[contains(@class,'article-slot__title')]/a/text()")
				summary_l = article_banner.xpath("./div/@brief")
				summary2_l = article_banner.xpath(".//ul[contains(@class,'article-slot__tldr')]/li/text()")
				the_date_str_l = article_banner.xpath(".//div[contains(@class,'publisher-details__date')]/text()")
				author_l = article_banner.xpath(".//a[contains(@class,'publisher-details__publisher-name')]/text()")
				link_l = article_banner.xpath(".//h3[contains(@class,'article-slot__title')]/a/@href") #add base url!
				
				
				
				title = title_l[0].strip() if title_l else None
				summary1 = summary_l[0].strip() if summary_l else ''
				summary2 = '\n'.join(s2.strip() for s2 in summary2_l)
				summary = '\n'.join([summary1,summary2])
				
				the_date_str = the_date_str_l[0].strip() if the_date_str_l else None 
				the_date_str = ' '.join(the_date_str.split(' ')[:-1]) if the_date_str else None
				the_date = datetime.datetime.strptime(the_date_str,"%A, %d/%m/%Y | %H:%M")
				
				author = author_l[0].strip() if author_l else None 
				link_sub = link_l[0] if link_l else None 
				link = self.URL + link_sub if link_sub else None 
				
				if not link: 
					log.warning(f"Failed to read an article banner - link missing")
					continue
				if not title:
					log.warning(f"Failed to read an article banner - title missing") 
					continue
				if not summary:
					log.warning(f"Failed to read an article banner - summary missing") 
					continue
				if not the_date:
					log.warning(f"Failed to read an article banner - date missing") 
					continue
				
				article_head = {
					'title':title,
					'summary':summary,
					'author':author,
					'link':link,
					'the_date':the_date,
					'source_ref':'forexlive.com'
				}
				
				article_data.append(article_head)
				
				
				
				
			except Exception as e:
				log.warning(f"Failed to read an article banner - {str(e)}")
				
		return article_data
		

#class LeapRateHeadlines(NewsFinder):
#	
#	URL = "https://www.leaprate.com/category/forex/" #page/{page}/"

#class FXEmpireHeadlines(NewsFinder):
#	url = 'https://www.fxempire.com/news" #?page=' 


class ActionForexHeadlines(NewsFinder):
	
	URL = "https://www.actionforex.com/category/contributors/" #page/{}/"
	
	@staticmethod
	def get_url(page=0):
		pagestr = ''
		if page > 0 :
			pagestr = f"page/{page}/"
		return ActionForexHeadlines.URL + pagestr
	
	def scrape(self):
		
		article_data = []		
		
		self.render()
		
		html = lxml.etree.HTML(self.html.html)
		article_banners = html.cssselect("div.td-module-container")
		for article_banner in article_banners:
			title_l = article_banner.xpath(".//h3[contains(@class,'td-module-title')]/a/text()")
			link_l = article_banner.xpath(".//h3[contains(@class,'td-module-title')]/a/@href")
			author_l = article_banner.xpath(".//span[@class='td-post-author-name']/a/text()")
			the_date_str_l = article_banner.xpath(".//span[@class='td-post-date']/time/@datetime")
			
			title = title_l[0] if title_l else None 
			link = link_l[0] if link_l else None
			author = author_l[0] if author_l else None
			the_date_str = the_date_str_l[0] if the_date_str_l else None
			the_date = datetime.datetime.strptime(the_date_str[:-6],"%Y-%m-%dT%H:%M:%S") if the_date_str else None #remove timezone!
			
			if not link: 
				log.warning(f"Failed to read an article banner - link missing")
				continue
			if not title:
				log.warning(f"Failed to read an article banner - title missing")
				continue
			if not the_date:
				log.warning(f"Failed to read an article banner - date missing") 
				continue
			
			article_head = {
				'title':title,
				'summary':None,
				'author':author,
				'link':link,
				'the_date':the_date,
				'source_ref':'actionforex.com'
			}
			article_data.append(article_head)		
		
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
		
		for entry in parsed.get('entries',[]):
		
			title = self.extract_title(entry,source_ref)
			the_date = self.extract_date(entry,source_ref)
			author = self.extract_author(entry,source_ref)
			link = self.extract_link(entry,source_ref)
			
			article = {
				'title':title,
				'the_date':the_date,
				'author':author,
				'link':link,
				'source_ref':source_ref
			}
			
			if 'content' in entry:
				contents = [content_item['value'] for content_item in entry['content']]
				article['full_text'] = '\n--break--\n'.join(contents)
			
			article_data.append(article)
			
		return article_data
		
class NewsHeadlineWorker(ProcessWorker):
	
	@overrides(ProcessWorker)
	def perform_task(self,archive_url):
		news_items = [] 
		matched = False 
		
		if archive_url.startswith("https://www.fxstreet.com/"):
			fxstreet = FXStreetSearch(archive_url)
			news_items += fxstreet.scrape()
			matched = True
		
		if archive_url.startswith("https://www.dailyfx.com/"):
			dailyfx = DailyFXArchive(archive_url)
			news_items += dailyfx.scrape() 
			matched = True
		
		if archive_url.startswith("https://www.fx.co/"):
			with SeleniumHandler(hidden=True) as sh:
				fxcoheadlines = FXCOHeadlines(sh,archive_url)
				news_items += fxcoheadlines.crawl()
			matched = True
		
		if archive_url.startswith("https://www.actionforex.com/"):
			actionforexheadlines = ActionForexHeadlines(archive_url)
			news_items += actionforexheadlines.scrape()
			matched = True
		
		if not matched:
			log.warning(f"News archive URL {archive_url} did not match any of the archive classes")
		
		#print(news_items) 
		return news_items
	
#from a set of news loaders, identify and get news items that can be passed to a news fetch worker 
##The purpose of this task is to get a load of new links to news articles that we do not already have, ready for loading into the db 
class NewsHeadlines: #turn into multi-process! 

	class ArchiveBehaviour(Enum):
		SKIP = -1 #do not gather any archive news 
		CHECK = 0 #check using the date if archive news needs to be fetched
		FORCE = 1 #always gather archive news 
	
	archive_behaviour = ArchiveBehaviour.FORCE
	
	rss_feeds : List[NewsFinder]
	news_archive_urls : List[NewsFinder]
	last_news_date : datetime.datetime
	
	num_workers = 7
	
	#get_older_news : bool = False #if true, run the news headline multiprocess no fxstreet, dailyfx and any other 
	
	def __init__(self,rss_feeds,news_archive_urls=[],last_news_date=datetime.datetime(1990,1,1)):
		self.news_archive_urls = news_archive_urls 
		self.rss_feeds = rss_feeds
		self.last_news_date = last_news_date

	def get_rss_items(self):
		news_items = []
		for rss_feed in self.rss_feeds:
			news_items += rss_feed.scrape() 
		return news_items

	def check_last_date(self,news_items):
		source_min_dates = defaultdict(list)
		for ni in news_items: #check only the archivables? 
			source_min_dates[ni['source_ref']].append(ni['the_date'])
		max_min_date = max([min(dates) for (source_ref,dates) in source_min_dates.items()])
		return max_min_date > self.last_news_date
	
	def perform_archive(self):#multi process func
		scrape_workers = [NewsHeadlineWorker(i) for i in range(self.num_workers)]
		scraper_pool = ProcessPool(scrape_workers)
		return itertools.chain.from_iterable(scraper_pool.perform(self.news_archive_urls)) #implode
	
	def get_archive_items(self): 
		
		news_items = []
		if self.archive_behaviour == NewsHeadlines.ArchiveBehaviour.SKIP:
			return news_items 
			
		perform_archive = len(news_items) == 0 or \
				self.check_last_date(news_items) or \
				self.archive_behaviour == NewsHeadlines.ArchiveBehaviour.FORCE 
		
		if perform_archive:
			news_items = self.perform_archive()
		
		return news_items
		
	
	def get_items(self):
		
		#months_years = self.get_months_years(date_from,date_to)
		news_items = self.get_rss_items()
		rss_links = [ni['link'] for ni in news_items]
		news_items += [ni for ni in self.get_archive_items() if ni['link'] not in rss_links] #only add extra items to the list
		
		return news_items # News.filter_old(self.cur,news_items)
	

#class for performing a news fetch task - Scrape, crawl or both depending on phase (first scrape jobs then crawl jobs) 
#rm in favour of ProcessPool
class NewsItemWorker(ProcessWorker):
		
	scraper_map = {
		'dailyfx.com':DailyFXNews,
		'fxstreet.com':FXStreet,
		'forexlive.com':ForexLive,
		'forexcrunch.com':ForexCrunch,
		'fx.co':FXCO,
		'actionforex.com':ActionForex
	}
	
	def perform_task(self, news_item):
		#use scraper/crawler to get the text - use source_ref to determine scraper
		source_ref = news_item['source_ref']
		link = news_item['link']
		
		#short circut anything that already has been loaded - can happen with RSS feeds 
		if 'full_text' in news_item and news_item['full_text']: #better validation needed!
			return news_item
			
		scraper = self.scraper_map.get(source_ref)
		
		result_dict = None
		if scraper is None:
			log.warning(f"No scraper found for {source_ref}. Item will not be saved with null full_text field.")
			result_dict = {'full_text': None}
		else:
			scraper_obj = scraper(link)
			result_dict = scraper_obj.scrape()
		
		if 'error' not in result_dict:
			#replemist any keys with the scraped results as they are more accurate 
			news_item = {**news_item, **result_dict}
		return news_item

#class for decorating news stories with an instrument, checking for irrelevant articles (eg tutorials) and checking against the db if the news has already been captured 
class NewsItemProcessor: 
	
	#cur : psycopg2.cursor
	dkim = None
	cur = None
	num_workers = 3
	db_chunk_size = 100
	use_progress = True
	
	def __init__(self,cur, direct_keyword_instrument_map):
		self.cur = cur 
		self.dkim = direct_keyword_instrument_map
	
	def get_subject_items(self,news_items, return_all=False):	
		for news_item in news_items:
			news_item['instruments'] = self.dkim.get_relevent_instruments(news_item['title'])
		
		if return_all:
			return news_items
	
		return [ni for ni in news_items if ni['instruments']]
	
	def get_new_items(self,news_items):
		links = [ni['link'] for ni in news_items]
		self.cur.execute(sql['new_links'],{'links':links})
		new_links = [nl[0] for nl in self.cur.fetchall()]
		return [ni for ni in news_items if ni['link'] in new_links]
	
	def get_outdated_items(self,news_items):	
		sqlrow = "(%(link)s,%(the_date)s)"
		sqlrows = [self.cur.mogrify(sqlrow,ni).decode() for ni in news_items]
		self.cur.flush()
		self.cur.execute(sql['outdated_or_empty_links'],{'link_date_pairs':Inject(','.join(sqlrows))})
		new_links = [nl[0] for nl in self.cur.fetchall()]
		return [ni for ni in news_items if ni['link'] in new_links]
	
	def prune_items(self,news_items,return_all=False):
		subject_news_items = self.get_subject_items(news_items,return_all) #get only news items that have a subject (instrument)
		new_news_items = self.get_new_items(subject_news_items)
		outdated_news_items = self.get_outdated_items(subject_news_items)
		return new_news_items + outdated_news_items #should be unique but might wanna check? 
	
	def perfrom_scraping(self, news_items):
		scrape_workers = [NewsItemWorker(i) for i in range(self.num_workers)]
		scraper_pool = ProcessPool(scrape_workers)
		full_news_stories = scraper_pool.perform(news_items)
		return full_news_stories
		#save to db here... 
	
	def put_to_database(self,news_articles):
		news_articles_full = [ni for ni in news_articles if ni['full_text']]
		if len(news_articles) > len(news_articles_full):
			log.warning("News articles with null full_text found - skipping these.")
		
		for news_article in news_articles_full:
			if 'summary' not in news_article:
				#add a blank summary - summary is not important but useful if we had it (eg for checking scraped story) 
				news_article['summary'] = '' 
			
			news_article['published_date'] = news_article['the_date'] #rename column for NewsArticle
			
		news_article_chunks = [news_articles_full[i:i+self.db_chunk_size] for i in range(0,len(news_articles_full),self.db_chunk_size)]
		news_article_chunks = tqdm(news_article_chunks) if self.use_progress else news_article_chunks
		for news_chunk in news_article_chunks:	
			sql_rows = [self.cur.mogrify(NewsArticle.sql_row,ni).decode() for ni in news_chunk]
			self.cur.execute(sql['news_article_upserts'],{'news_articles':Inject('\n,'.join(sql_rows))})
		self.cur.con.commit()


		
	
#for insert
sql['new_links'] = """
WITH links AS (
	SELECT UNNEST(%(links)s) AS link
)
SELECT ls.link FROM links ls WHERE NOT EXISTS (
	SELECT 1 FROM news_article na WHERE na.link = ls.link
);
"""

#for update
sql['outdated_or_empty_links'] = """
WITH link_dates AS (
	SELECT link, the_date FROM (
		VALUES %(link_date_pairs)s
	) AS vals(link,the_date)
)
SELECT ld.link FROM link_dates ld
JOIN news_article na ON ld.link = na.link AND na.last_update < ld.the_date
UNION 
SELECT ld.link FROM link_dates ld
JOIN news_article na ON ld.link = na.link AND NULLIF(na.full_text ,'') IS NULL;
"""

sql['news_article_upserts'] = """
WITH these_news_articles AS (
	SELECT * FROM (VALUES
		%(news_articles)s
	) AS na(link,title,summary,published_date,author,source_ref,full_text,instruments)
),
updated_articles AS (
	UPDATE news_article AS na
	SET title = tna.title,
	summary = COALESCE(NULLIF(tna.summary,''),na.summary), --keep old if new is blank!
	published_date = COALESCE(tna.published_date,na.published_date), 
	author = COALESCE(NULLIF(tna.author,''),na.author),
	source_ref = COALESCE(NULLIF(tna.source_ref,''),na.source_ref),
	full_text = COALESCE(NULLIF(tna.full_text,''),na.full_text),
	--merge any instruments together if there are already some
	instruments = ARRAY(SELECT DISTINCT instrument FROM UNNEST(tna.instruments || na.instruments) AS a(instrument) ORDER BY instrument) 
	FROM these_news_articles AS tna
	WHERE na.link = tna.link
	RETURNING na.link
)
INSERT INTO news_article(link,title,summary,published_date,author,source_ref,full_text,instruments)
SELECT link,title,summary,published_date,author,source_ref,full_text,instruments 
FROM these_news_articles tna 
WHERE NOT EXISTS (
	SELECT 1 FROM updated_articles ua 
	WHERE ua.link = tna.link 
);

"""


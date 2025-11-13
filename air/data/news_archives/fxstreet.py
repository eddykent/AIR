
import pdb

import time
import dateutil.parser

from archive_head import *

#from all_project import * --import everything from the project 
from data.tools.newnews import FXStreet #scraper for fxstreet news stories
from web.crawler import SeleniumHandler, XPathNavigator, By

#import urllib


#urllib.parse.quote_plus(str)

daily_url_str = 'https://www.fxstreet.com/news/all?date={year:0>4}-{month:0>2}-{day:0>2}'

query_url_string = 'https://www.fxstreet.com/news?q={instrument}&hPP={n_results}&idx=FxsIndexPro&p=0'

source_ref = 'fxstreet.com'
source_title = 'fxstreet.com'

hide_me_de = 'https://de.hideproxy.me/go.php?u='
hide_me_nl = 'https://nl.hideproxy.me/go.php?u='
hide_me_fi = 'https://fi.hideproxy.me/go.php?u='

days_back = 60
today = datetime.datetime.now()
today = datetime.datetime(today.year,today.month,today.day)
start_day = today - datetime.timedelta(days=1) #offset because of time strings like 'x minutes ago' - needs fixing! 

all_days = [start_day-datetime.timedelta(days=i) for i in range(0,days_back)]

#proxy = '155.4.244.218'
#proxy = '80.66.81.40:8080'
#proxy = None 



class FXStreetArchiveOld(Scraper):
	
	def scrape(self):
		article_data = [] #here wesef can only get the title and the link 
		article_heads = self.html.xpath("//div[contains(@class,'fxs_crawling_page')]//article")
		pdb.set_trace()
		for article_head in article_heads:
			anchor = article_head.xpath('.//a')[0]
			link = anchor.attrs.get('href')
			title = anchor.attrs.get('title')
			time = article_head.xpath('.//time')[0].text
			article_data.append({
				'time':time,
				'link':link,
				'title':title,
				'source_title':source_title,
				'source_ref':source_ref
			})
		return article_data

class FXStreetQuery(XPathNavigator):
	
	
	def crawl(self):
		
		ais_hits = {'tag':'div', 'class':'ais-hits--item' }
		banner = {'tag':'div','class':'fxs_prestitial-continue'} 
		
		
		article_data = []
		
		#close initial banner 
		try:	
			banner =self.get_element(banner,1)
			banner.click()
		except:
			pass
		
		#wait for page to load?
		article_heads = []
		iter = 0 
		max_iter = 3
		num = 200
		while len(article_heads) < num:
			time.sleep(1)
			iter += 1
			article_heads = self.get_multiple_elements(ais_hits,1)
			if iter >= max_iter:
				break
		
		time.sleep(1)
		for article_head in article_heads:
			
			#pdb.set_trace()
			the_date = article_head.find_element(By.XPATH,'.//address/time').get_attribute('datetime')
			link = article_head.find_element(By.XPATH,'.//h4/a').get_attribute('href') 
			title = article_head.find_element(By.XPATH,'.//h4').text 
			
			i2 = 0 
			iim = 3
			
			while not (the_date and link and title):
				i2 += 1
				time.sleep(1)
				the_date = article_head.find_element(By.XPATH,'.//address/time').get_attribute('datetime')
				link = article_head.find_element(By.XPATH,'.//h4/a').get_attribute('href') 
				title = article_head.find_element(By.XPATH,'.//h4').text 
				if i2 >= iim:
					break
			
			if not (the_date and link and title):
				continue 
				
			article_data.append({
				'time':the_date,
				'link':link,
				'title':title, 
				'source_title':source_title,
				'source_ref':source_ref
			})
		
		return article_data


class FXStreetExtra(Scraper): #make a class that reads a bit more stuff from the news article since we cant get it from the archive
	
	def scrape(self):	
		#author, summary, full_text
		summary_bits = self.html.xpath("//div[@class='fxs_article_content']/ul/li/strong")
		summary = '\n'.join([sb.text for sb in summary_bits])
		
		full_text_bits = self.html.xpath("//div[@class='fxs_article_content']/p")
		full_text = '\n'.join([fb.text for fb in full_text_bits])
		
		author_elem = self.html.xpath("//article[@class='fxs_article']/header/span/a[@data-gtmid='lateralnavigation-post-author']")
		author = author_elem[0].text if author_elem else '?'
		
		#datetime.datetime.strptime(the_date_str,"%Y-%m-%dT%H:%M:%SZ")
		#pdb.set_trace()
		
		return full_text, author, summary 


article_data = []

def parse_date(datestr):

	def extract_time_piece(astr, timestr):
		aind = astr.index(timestr) if timestr in astr else -1
		if aind > 0:
			bstr = astr[:aind]
			pieces = bstr.split(' ')
			for ps in pieces[::-1]:	
				try:	
					return int(ps)
				except:
					continue
		return 0 
	the_date = None 
	
	if 'ago' in datestr:
		
		days = extract_time_piece(datestr,'day')
		hours = extract_time_piece(datestr,'hour')
		minutes = extract_time_piece(datestr,'minute')
		
		ttrn = (14400 * days) + (60 * hours) + minutes
		the_date = datetime.datetime.utcnow() - datetime.timedelta(minutes=ttrn)
		
	else:
		#pdb.set_trace()
		try:
			the_date = datetime.datetime.strptime(the_date_str,"%Y-%m-%dT%H:%M:%SZ")
		except:
			#pdb.set_trace()
			the_date = dateutil.parser.parse(datestr)#check 
	
	return the_date

def get_articles(fx_pair,sh=None):
	query_url = query_url_string.format(instrument=fx_pair,n_results=900)
	#hidden_url = hide_me_de + urllib.parse.quote_plus(query_url)
	articles = []
	
	if sh is None:
		with SeleniumHandler(proxy=proxy, config=config) as sh: #separate instance per read so it can be async 
			fxq = FXStreetQuery(sh,query_url)
			articles = fxq.crawl()
	else:
		fxq = FXStreetQuery(sh,query_url)
		articles = fxq.crawl()
	
	print('got '+str(len(articles))+' links')
	return articles
		


print('Fetching news story URLs from search...')
with SeleniumHandler(proxy=None, config=config) as sh:
	#for fx_pair in ['NZD/USD']:
	for fx_pair in fx_pairs:
		print('Getting '+fx_pair)
		these_articles = get_articles(fx_pair,sh)
		article_data += these_articles

#for daily in tqdm(all_days):
#	daily_url = daily_url_str.format(year=daily.year,month=daily.month,day=daily.day)
#	fxsa = FXStreetArchive(daily_url,proxy)
#	this_day_articles = fxsa.scrape()
#	for this_day_article in this_day_articles:
#		this_day_article['the_date'] = daily
#	article_data.extend(this_day_articles)

print('Determining relevant stories...')
relevant_articles = []
for article_d in tqdm(article_data):	
	instruments  = dkim.get_relevent_instruments(article_d['title'])
	if not instruments:
		continue 
	article_d['instruments'] = instruments
	relevant_articles.append(article_d)

print('Fixing dates...')
for article_d in tqdm(relevant_articles):
	try:
		the_date = parse_date(article_d['time'])
		article_d['published_date'] = the_date
		del article_d['time']
	except Exception as e:
		print(e)
		print(f"check  - article article_d['time'] = '{article_d['time']}'")
		pdb.set_trace()
		print('what happened')


print('Purging articles we already have')
chunk_size = 100
article_chunks = [relevant_articles[i:i+chunk_size] for i in range(0,len(relevant_articles),chunk_size)]
all_new_articles = [] 
for article_chunk in tqdm(article_chunks):
	links = [ra['link'] for ra in article_chunk]
	cur.execute(sql['new_links'],{'links':links})
	new_links = [nl[0] for nl in cur.fetchall()]
	new_articles = [ra for ra in article_chunk if ra['link'] in new_links]
	all_new_articles += new_articles

relevant_new_articles = all_new_articles

#pdb.set_trace()
print('Reading full stories... ')
read_stories = []
for article_d in tqdm(relevant_new_articles):
	dfx = FXStreetExtra(article_d['link'])
	full_text, author, summary = dfx.scrape()
	if full_text and full_text != 'VIDEO':
		article_d['full_text'] = full_text
		article_d['author'] = author
		article_d['summary'] = summary
		read_stories.append(article_d)
	
print('Saving stories to database...')
chunk = 1000 #save in chunks of 1000 or something
partition_articles = [read_stories[i:i+chunk] for i in range(0,len(read_stories),chunk)]  
for partition in tqdm(partition_articles):
	for article_d in partition:
		article_d['source_ref'] = 'fxstreet.com'
	sql_rows = [cur.mogrify(NewsArticle.sql_row,article_d).decode() for article_d in partition]
	article_dump = ','.join(sql_rows)
	cur.execute(sql['create_news_articles'],{'news_articles':Inject(article_dump)})

cur.con.commit()
cur.close()


















import pdb

from archive_head import *

#from all_project import * --import everything from the project 
from web.scraper import FXStreet #scraper for fxstreet news stories

daily_url_str = 'https://www.fxstreet.com/news/all?date={year:0>4}-{month:0>2}-{day:0>2}'

source_ref = 'fxstreet.com'
source_title = 'fxstreet.com'

days_back = 30
today = datetime.datetime.now()
today = datetime.datetime(today.year,today.month,today.day)
start_day = today - datetime.timedelta(days=1) #offset because of time strings like 'x minutes ago' - needs fixing! 

all_days = [start_day-datetime.timedelta(days=i) for i in range(0,days_back)]

class FXStreetArchive(Scraper):
	
	def scrape(self):
		article_data = [] #here wesef can only get the title and the link 
		article_heads = self.html.xpath("//div[contains(@class,'fxs_crawling_page')]//article")
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

class FXStreetExtra(Scraper): #make a class that reads a bit more stuff from the news article since we cant get it from the archive
	
	def scrape(self):	
		#author, summary, full_text
		summary_bits = self.html.xpath("//div[@class='fxs_article_content']/ul/li/strong")
		summary = '\n'.join([sb.text for sb in summary_bits])
		
		full_text_bits = self.html.xpath("//div[@class='fxs_article_content']/p")
		full_text = '\n'.join([fb.text for fb in full_text_bits])
		
		author_elem = self.html.xpath("//article[@class='fxs_article']/header/span/a[@data-gtmid='lateralnavigation-post-author']")
		author = author_elem[0].text if author_elem else '?'
		
		return full_text, author, summary 

article_data = []
print('Fetching news story URLs from the archives...')
for daily in tqdm(all_days):
	daily_url = daily_url_str.format(year=daily.year,month=daily.month,day=daily.day)
	fxsa = FXStreetArchive(daily_url)
	this_day_articles = fxsa.scrape()
	for this_day_article in this_day_articles:
		this_day_article['the_date'] = daily
	article_data.extend(this_day_articles)

relevant_articles = []
print('Determining relevant stories...')
for article_d in tqdm(article_data):	
	relevant = keyword_map.relevant_keys(article_d['title'])
	if not relevant:
		continue 
	relevant_articles.append(article_d)

print('Fixing dates...')
for article_d in tqdm(relevant_articles):
	try:
		h, m = article_d['time'].split(',')[1][:-3].strip().split(':') #
		base_date = article_d['the_date']
		article_d['the_date'] = datetime.datetime(base_date.year,base_date.month,base_date.day,int(h),int(m))
		del article_d['time']
	except:
		print(f"check  - article article_d['time'] = '{article_d['time']}'")
		pdb.set_trace()

print('Reading full stories... ')
read_stories = []
for article_d in tqdm(relevant_articles):
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
	articles = [Article.from_dict(article_d) for article_d in partition]
	database_rows = [a.to_database_row() for a in articles]
	sql_rows = [cur.mogrify(Article.sql_row,db_row).decode() for db_row in database_rows]
	hash_checks = [db_row['hash_check'] for db_row in database_rows]
	article_dump = ','.join(sql_rows)
	cur.execute(upsert_query,{'articles':Inject(article_dump), 'remove_hashes':hash_checks})

cur.con.commit()
cur.close()
















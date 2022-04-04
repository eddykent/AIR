




import pdb

from archive_head import *

#from all_project import * --import everything from the project 
from web.scraper import DailyFXNews #scraper for dailyfx news stories


##a DailyFX archive reader to place their old news stories into the database
#if no fx pair is present in the title then it will not be stored
monthly_url_str = 'https://www.dailyfx.com/archive/{year:0>4}/{month:0>2}'

#first, get all hyperlinks that can lead to a story
hyperlinks = []

the_date = datetime.datetime.now()
this_year = the_date.year
this_month = the_date.month
earliest_year = 2022 #edit for back 
years = [y for y in range(earliest_year,this_year)]
months = [m for m in range(1,13)]

months_years = [(m,y) for m in months for y in years] + [(m,this_year) for m in months if m < this_month]
monthly_urls = [monthly_url_str.format(year=y,month=m) for (m,y) in months_years]

source_title = 'DailyFX - Market News'
source_ref = 'dailyfx.com'


class DailyFXArchive(Scraper):
	
	def scrape(self):
		
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
					
					article_data.append({
						'title':article_title,
						'the_date':th.from_str_2(article_time),
						'author':article_author,
						'link':article_url,
						'source_ref':source_ref,
						'source_title':source_title
					})
					
		#pdb.set_trace()			
		return article_data	


article_data = [] 
relevant_articles = []
print('Fetching news story URLs from the archives...')
for archive_url in tqdm(monthly_urls):
	dfxa = DailyFXArchive(archive_url) #loadiing bar?
	article_data.extend(dfxa.scrape())

print('Determining relevant stories...')
for article_d in tqdm(article_data):	
	relevant = keyword_map.relevant_keys(article_d['title'])
	if not relevant:
		continue 
	relevant_articles.append(article_d)

#pdb.set_trace()
print('Reading full stories... ')
#relevant_articles = relevant_articles[:100]
read_stories = []
for article_d in tqdm(relevant_articles):
	dfx = DailyFXNews(article_d['link'])
	full_text = dfx.scrape()
	if full_text and full_text != 'VIDEO':
		article_d['full_text'] = full_text
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




















 
 
 
 
 
 
 
 
 







import pdb
import urllib.parse

from archive_head import *

#from all_project import * --import everything from the project 
from data.tools.newnews import DailyFXNews #scraper for dailyfx news stories


##a DailyFX archive reader to place their old news stories into the database
#if no fx pair is present in the title then it will not be stored
monthly_url_str = 'https://www.dailyfx.com/archive/{year:0>4}/{month:0>2}' #blocked
#monthly_url_str = 'https://de.hideproxy.me/go.php?u=https%3A%2F%2Fwww.dailyfx.com%2Farchive%2F{year:0>4}%2F{month:0>2}'

#note: not sustainable - need to get a proxy or something to stop getting blocked 
#hidemeurl = https://nl.hideproxy.me/go.php?u={encoded_url}



#first, get all hyperlinks that can lead to a story
hyperlinks = []

the_date = datetime.datetime.now()
this_year = the_date.year
this_month = the_date.month

#earliest_year = 2022 #edit for back 
#years = [y for y in range(earliest_year,this_year+1)]
#months = [m for m in range(9,13)]
#
#months_years = [(m,y) for m in months for y in years] + [(m,this_year) for m in months if m <= this_month]
#monthly_urls = [monthly_url_str.format(year=y,month=m) for (m,y) in months_years]
#
#from_month = this_month
#from_month = 0 if from_month < 0 else from_month
#months_years = [(m,y) for (m,y) in months_years if m >= from_month] if not years else months_years
source_title = 'DailyFX - Market News'
source_ref = 'dailyfx.com'
months_years = now_to_x_months_back(this_month, this_year, 3)
monthly_urls = [monthly_url_str.format(year=y,month=m) for (m,y) in months_years]

proxy = '80.48.119.28'




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
						'published_date':th.from_str_2(article_time),
						'author':article_author,
						'link':article_url,
						'summary':''
						#'source_ref':source_ref,
						#'source_title':source_title
					})
					
		#pdb.set_trace()			
		return article_data	


article_data = [] 
relevant_articles = []
print('Fetching news story URLs from the archives...')
for archive_url in tqdm(monthly_urls):
	dfxa = DailyFXArchive(archive_url,proxy) #loadiing bar?
	article_data.extend(dfxa.scrape())

print('Determining relevant stories...')
for article_d in tqdm(article_data):	
	instruments  = dkim.get_relevent_instruments(article_d['title'])
	if not instruments:
		continue 
	article_d['instruments'] = instruments
	relevant_articles.append(article_d)


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


#pdb.set_trace()
print('Reading full stories... ')
#relevant_articles = relevant_articles[:100]
read_stories = []
#all_new_articles = all_new_articles[:3]

for article_d in tqdm(all_new_articles):
	dfx = DailyFXNews(article_d['link'],proxy)
	full_text = dfx.scrape()
	if full_text and full_text != 'VIDEO':
		article_d['full_text'] = full_text
		read_stories.append(article_d)


#incorrect here
print('Saving stories to database...')
chunk = 1000 #save in chunks of 1000 or something
partition_articles = [read_stories[i:i+chunk] for i in range(0,len(read_stories),chunk)]  
for partition in tqdm(partition_articles):
	for article_d in partition:
		article_d['source_ref'] = 'dailyfx.com'
	sql_rows = [cur.mogrify(NewsArticle.sql_row,article_d).decode() for article_d in partition]
	article_dump = ','.join(sql_rows)
	cur.execute(sql['create_news_articles'],{'news_articles':Inject(article_dump)})

cur.con.commit()
cur.close()




















 
 
 
 
 
 
 
 
 


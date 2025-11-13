
import datetime 


#tool for changing articles in the database 

#eg to have the correct relevant keys and an id link (url) reads from old table and inserts into new  
#also to fix dates in fxstreet - these are MM/DD/YYYY format on website yet we got it as DD/MM/YYY

from tqdm import tqdm
import pdb

from data.text import Article, NewsArticle
from utils import Database
from data.capture.newnews import FXStreet


sql = {}

class DBArticleConverter:

	
	direct_keyword_map = None
	
	def __init__(self,direct_keyword_map):
		self.direct_keyword_map = direct_keyword_map
	
	def get_guids(self, cur):
		guids = []
		#with Database() as cur:
		cur.execute(sql['find_neutral_article_guids'])
		guids = [x[0] for x in cur.fetchall()]
		return guids

	def convert_rows(self, guids, cur):
		cur.execute(sql['get_by_guids'],{'guids':guids})
		articles = [Article.from_database_row(row) for row in cur.fetchall()]
		
		new_sql_rows = []
		these_fields = [field.name for field in fields(NewsArticle)]
		for article in articles:	
			instruments = self.direct_keyword_map.get_relevent_instruments(article.title + ' ' + article.summary)
						
			param = {
				'link':article.link,
				'title':article.title,
				'summary':article.summary,
				'published_date':article.the_date,
				'author':article.author,
				'source_ref':NewsArticle.link_to_src_ref(article.link),
				'full_text':article.full_text,
				'instruments':instruments
			}
			new_sql_rows.append(cur.mogrify(NewsArticle.sql_row,param).decode())
			
			#pdb.set_trace()
			#na = NewsArticle.from_dict(param)
		#now insert into db
		cur.execute(sql['create_news_articles'],{'news_articles':Inject(','.join(new_sql_rows))})
			
						
		#pdb.set_trace()
	
	
	def run(self):
		cur = Database(cache=False,commit=True) 
		all_guids = self.get_guids(cur)
		
		chunk = 200
		
		guid_chunks = [all_guids[i:i+chunk] for i in range(0,len(all_guids),chunk)]
		#guid_chunks = guid_chunks[:2]
		
		for these_guids in tqdm(guid_chunks):
			self.convert_rows(these_guids, cur)
		
		#cur.commit()
		cur.con.commit()
		cur.close()
		
#use guids file to fix the dates 


class NewsDataFix:
	
	guids_file = None
	rejects_file = None
	n_fixes = 0
	
	def __init__(self,guids_file='data/fxstreetdatefix.txt',rejects_file='data/fxstreetrejectguids.txt'):
		self.guids_file = guids_file
		self.rejects_file = rejects_file
		with open(guids_file,'r') as f:
			lines = f.read().split('\n')
			self.n_fixes = len(lines)
		
	def pop_guid(self): #consider abstracting into "guid base fixer" 
		lines = None
		with open(self.guids_file,'r') as f:
			lines = f.read().split('\n')
		
		guid = lines[0] if len(lines) > 0 else None 
		with open(self.guids_file,'w') as f:
			f.write('\n'.join(lines[1:]))
		
		return guid
	
	def get_guid(self):
		lines = None
		with open(self.guids_file,'r') as f:
			lines = f.read().split('\n')
		
		guid = lines[0] if len(lines) > 0 else None 
		return guid
	
	def remove_guid(self,guid):
		lines = None
		with open(self.guids_file,'r') as f:
			lines = f.read().split('\n')
		lines = [g for g in lines if g != guid]
		
		with open(self.guids_file,'w') as f:
			f.write('\n'.join(lines))
		
	
	def note_reject(self,guid):
		with open(self.rejects_file,'a') as f:
			f.write(guid+'\n')
	
	def get_link(self,guid):
		link = None
		with Database(cache=False,commit=False) as db:
			db.execute(sql['guid2link'],{'guid':guid})
			link = db.fetchone()[0]
		return link

class FXStreetDateFix(NewsDataFix):
	
			
	def update_date(self,guid,the_date):
		with Database(cache=False,commit=True) as db:
			db.execute(sql['update_date'],{'guid':guid,'the_date':the_date})
			db.con.commit()#just incase!

	
	def fix_dates(self):
		print('fixing fx_street article dates')
		for iteration in tqdm(range(self.n_fixes)):
			guid = self.get_guid() 
			link = self.get_link(guid)
			
			the_date = None 
			#get date
			try:
				fxs = FXStreet(link)
				the_date_str = fxs.get_date_str()
				the_date = datetime.datetime.strptime(the_date_str,"%Y-%m-%dT%H:%M:%SZ")
			except Exception as e:
				print(link)
				print(e)
				#pdb.set_trace() #continue
			
			if the_date is None:
				self.note_reject(guid)
			else:
				self.update_date(guid,the_date)
				
			self.remove_guid(guid)
			
			
class DuplicateFix(NewsDataFix):
	
	pass
		
	

	
sql['find_neutral_article_guids'] = '''
SELECT guid FROM news_article_old na --WHERE idlink IS NULL --OR COALESCE(CARDINALITY(instruments),0) = 0
'''

sql['get_by_guids'] = '''
WITH article_guids AS (
	SELECT UNNEST(%(guids)s) AS guid 
)
SELECT na.* FROM news_article_old na
JOIN article_guids ag ON ag.guid = na.guid;
'''

sql['create_news_articles'] = """
INSERT INTO news_article (
	link,
	title,
	summary,
	published_date,
	author,
	source_ref,
	full_text,
	instruments
)
VALUES %(news_articles)s
"""

sql['news_article_captured_date_transfer'] = """
UPDATE news_article 
SET captured_date = nao.captured_date 
FROM news_article_old nao 
WHERE nao.published_date = news_article.published_date AND news_article.title LIKE nao.title_head || '%'
"""


sql['guid2link'] = """
SELECT link FROM news_article WHERE guid = %(guid)s;
"""

sql['update_date'] = """
UPDATE news_article SET published_date = %(the_date)s WHERE guid = %(guid)s;
"""
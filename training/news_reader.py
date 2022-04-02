

from tqdm import tqdm
import datetime

import pdb

from models.news_reader_model import NewsReaderModel
from training.train import DataProvider, ModelComposer, ValidationMode
from utils import overrides, Database, ListFileReader, Inject
from web.scraper import Article


#this is used to get the y result for the neural net from previous data. 
class TextResultQuery:
	the_date = None
	instrument = None
	duration = 360 #lets default to 6 hours  
	
	sql_row = "(%(the_date)s::TIMESTAMP,%(instrument)s,%(duration)s::INT)"
	
	def __init__(self,the_date,instrument,duration=360):
		self.the_date = the_date
		self.instrument = instrument
		self.duration = duration
	
	def __repr__(self):
		return f"TextResultQuery({self.instrument} at {self.the_date} for {self.duration} minutes)"
		
	def to_sql_dict(self):
		return {
			'the_date':self.the_date,
			'instrument':self.instrument, 
			'duration':self.duration
		}

class NewsReaderData(DataProvider):
	
	articles = [] #the article we are interested in 
	price_actions = [] #the price action after the article 
	#truncated_article_length = 800 #can be set to anything - move to model_maker
	
	#list all the source refs and put what duration we want price action to be for each one 
	source_ref_duration_map = {	}
	
	parameters = {
		'start_date':datetime.datetime(2022,1,1),
		'end_date':datetime.datetime(2022,3,25)
	}
	
	@overrides(DataProvider)
	def _sample_instructions_list(self):
		query_x = ''
		with open('queries/load_articles.sql') as f:
			query_x = f.read()

		query_y = ''
		with open('queries/news_reader_y.sql') as f:
			query_y = f.read()

		lfr = ListFileReader()
		fx_pairs = lfr.read('fx_pairs/fx_mains.txt')
		currencies = lfr.read('fx_pairs/currencies.txt')
		cursor = Database(cache=False,commit=False)
		start_date = self.parameters.get('start_date',datetime.datetime(2020,1,1))
		end_date =  self.parameters.get('end_date',datetime.datetime(2022,3,10))

		print('Fetching articles...')
		cursor.execute(query_x,{'start_date':start_date ,'end_date':end_date}) 
		articles = [Article.from_database_row(row) for row in tqdm(cursor.fetchall())] 
		
		#max story length...? 
		
		print('Determining subjects... ')
		relevance_thing = self.model_maker.text_analyser.keyword_helper
		article_rels = zip(articles,[relevance_thing.relevant_keys(a.title + ' ' + a.summary,degree=1) for a in tqdm(articles)])

		#clear out any ambiguous 
		articles_queries = [] 
		for article, relevance in article_rels:
			rel = [k for k in relevance if k in fx_pairs]
			if len(rel) == 1: #if it has more than 1 then it talks about multiple instruments which will be confusing when sorting the sentiment
				instrument = rel[0]
				duration = self.source_ref_duration_map.get(article.source_ref,360) #might want to change the duration later per source or something
				query = TextResultQuery(article.the_date,instrument,duration)
				articles_queries.append((article,query))
		
		print('Loading price actions from database...')
		chunk_size = 250
		articles_price_actions = []
		chunks = [articles_queries[i:i+chunk_size] for i in range(0,len(articles_queries),chunk_size)]		
		for chunk in tqdm(chunks):
			sql_rows = [] 
			subarticles = []
			for article,query in chunk:
				sql_rows.append(cursor.mogrify(query.sql_row, query.to_sql_dict()).decode())
				subarticles.append(article)
			cursor.execute(query_y, {'text_result_queries':Inject(','.join(sql_rows))})
			query_results = cursor.fetchall()
			assert len(query_results) == len(subarticles)
			articles_price_actions.extend(list(zip(subarticles,query_results)))
		
		#now clean data that is missing - only select stuff that has enough candles to compare with
		articles_results = [(article,price_actions) for article,price_actions in articles_price_actions if price_actions[0]['n_candles'] > 2] 
		#need to figure out a way to normalise the Y values 
		return articles_results #return the full list of articles we will use for training  
	
	@overrides(DataProvider)
	def _generate(self,instruction_list):
		#any way to call a tqdm? :/ -NO DUH IT IS HANDLED BY TENSORFLOW :)
		articles, price_actions = zip(*instruction_list)
		
		xs = self.model_maker.preprocess_x([article.full_text for article in articles])
		ys = self.model_maker.preprocess_y(price_actions)
		
		return xs,ys

	
	


def perform_training():
	news_reader_model = NewsReaderModel()
	news_reader_model.create_model()
	news_data = NewsReaderData(news_reader_model,row_cache_label='test')
	news_data.begin_load()
	#pdb.set_trace()
	model_composer = ModelComposer(news_reader_model,news_data,weights_label='test')
	model_composer.train(epochs=30)
	model_composer.test(' ') #put some test news snippet in here


perform_training()





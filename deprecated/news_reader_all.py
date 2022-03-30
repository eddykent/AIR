
##this file will be used to create and train a news reading AI that takes a bunch of text and then tells us 
##what the percent difference and the standard dev will be, based on training. 
#Questions to think about: 
#Is it going to be source agnostic? Instrument agnostic? Author agnostic? 
import numpy as np
import tensorflow as tf
from tensorflow import keras
import spacy
from collections import namedtuple
import datetime
import uuid
from tqdm import tqdm

import pdb

from fundamental import TextAnalysis
from utils import Database, ListFileReader, Inject
from web.scraper import Article

#this is used to get the y result for the neural net from previous data. 
class TextResultQuery:
	query_id = None
	the_date = None
	instrument = None
	duration = 360 #lets default to 6 hours  
	
	sql_row = "(%(query_id)s,%(the_date)s::TIMESTAMP,%(instrument)s,%(duration)s::INT)"
	
	def __init__(self,the_date,instrument,duration=360):
		self.query_id = str(uuid.uuid4())
		self.the_date = the_date
		self.instrument = instrument
		self.duration = duration
		
	def to_sql_dict(self):
		return {
			'query_id':self.query_id,
			'the_date':self.the_date,
			'instrument':self.instrument, 
			'duration':self.duration
		}


query_x = ''
with open('queries/load_articles.sql') as f:
	query_x = f.read()

query_y = ''
with open('queries/news_reader_y.sql') as f:
	query_y = f.read()


lfr = ListFileReader()
fx_pairs = lfr.read('fx_pairs/fx_mains.txt')
currencies = lfr.read('fx_pairs/currencies.txt')

nlp = spacy.load("en_core_web_lg")
text_analyser = TextAnalysis()

cursor = Database(cache=False,commit=False)

#load articles 
start_date = datetime.datetime(2000,1,1)
#end_date = datetime.datetime.now() #absolutely EVERYTHING  -recent articles can break it? 
end_date =  datetime.datetime(2022,3,10)
print('Fetching articles...')
cursor.execute(query_x,{'start_date':start_date ,'end_date':end_date}) 
articles = [Article.from_database_row(row) for row in tqdm(cursor.fetchall())] 

print('Determining subjects... ')
article_rels = zip(articles,[text_analyser.keyword_helper.relevant_keys(a.title + ' ' + a.summary,degree=1) for a in tqdm(articles)])

#clear out any ambiguous 
unambigous_articles = [] 
for article, relevance in article_rels:
	rel = [k for k in relevance if k in fx_pairs]
	if len(rel) == 1:
		unambigous_articles.append((article,rel[0]))
	
print('Fetching price actions...')
sql_rows = []
more_zippy = [] 
#i = 0
for (article, instrument) in tqdm(unambigous_articles):
	duration = 360 #6 hours but might be different per source? article.source_ref 
	trq = TextResultQuery(article.the_date,instrument,duration)
	more_zippy.append((trq.query_id,article,instrument))
	sql_rows.append(cursor.mogrify(trq.sql_row, trq.to_sql_dict()).decode())

print('Getting price actions from database...')
chunk_size = 250
sql_chunks = [sql_rows[i:i+chunk_size] for i in range(0,len(sql_rows),chunk_size)]
rates_stds_aves = {} 
for sql_chunk in tqdm(sql_chunks):
	cursor.execute(query_y, {'text_result_queries':Inject(','.join(sql_chunk))})
	for row in cursor.fetchall():
		rates_stds_aves[row[0]['query_id']] = row[0]['typical']
	
print('Building feature vectors...') 
X = []
Y = []
for (query_id,article,instrument) in tqdm(more_zippy):
	ydata = rates_stds_aves.get(query_id) #some get dropped off - find out why? 
	if ydata is None or any(ydata.get(k) is None for k in ['rate','std','average']):
		continue
	rate= ydata['rate'] #this is already normalised 
	std = ydata['std'] / ydata['average']  #divide by the average so that we can compare different stds together 
	x = text_analyser.create_feature_vector(article.full_text,nlp)
	X.append(x)
	Y.append(np.array([rate,std]))

#pad xs, normalise y channels (0th between -1 and 1 and 1st between 0 and 1)
pdb.set_trace()
word_vec_size = X[0].shape[1]
maxt = max([text.shape[0] for text in X])
pad_lens = [maxt - text.shape[0] for text in X]
print('Padding word sequences...')
X = np.array([np.concatenate([x,np.zeros((pad_len,word_vec_size))],axis=0)  for x,pad_len in tqdm(zip(X,pad_lens))])

rate_max = max([abs(y[0]) for y in Y])
std_max = max([y[1] for y in Y])
Y = np.array([[y[0]/rate_max,y[1]/std_max] for y in Y])


#form here we will be just about ready to start learning! :) 
pdb.set_trace()





























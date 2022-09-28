#news indicator - get sentiment from news articles & filter what goes against 
#next currency strength - 4h timescale next prediction

import numpy as np 
from tqdm import tqdm 

import pdb

from utils import overrides, Database, Inject
from filters.trade_filter import *
#from models.model_base import ModelLoader, ModelMaker 
from web.scraper import Article
from fundamental import KeywordMapHelper
from web.feed_collector import TextBias 

sql = {} 

class NewsFilter(TimelineTradeFilter):

	news_model  = None 
	
	def __init__(self,news_model):
		self.news_model = news_model  #should be a ModelLoader object
	
	@overrides(TimelineTradeFilter)
	def filter(self,trades):
		tgags = {} 
		article_dict = {} 
		
		instruments = list(set(t.instrument for t in trades))
		
		with Database(cache=False) as cursor:
			tgags = self.get_news_guids([(t.signal_id, t.the_date) for t in trades],cursor)
			aguids = list(set(g for gvals in tgags.values() for g in gvals ))
			article_dict = self.get_news_articles(aguids,cursor)
		trade_dict = {t.signal_id:t for t in trades}
		article_rels = {} 
		kwmh = KeywordMapHelper()
		for g,a in article_dict.items():
			relevant = kwmh.relevant_keys(a.title + ' ' + a.summary)
			article_rels[g] = [i for i in instruments if i in relevant]
			
			#pass #get relevance for each article (list of instruments) 
		#rels = list(set([i for ii in article_rels.values() for i in ii]))
		#pdb.set_trace() 
		
		trade2articles = {} 
		for tg,ags in tgags.items():	
			subject = trade_dict[tg].instrument
			rel_article_guids = [g for g in ags if subject in article_rels[g]]
			trade2articles[tg] = rel_article_guids
		
		trade2article = {} 
		for tg,ags in trade2articles.items():
			the_articles = sorted([article_dict[g] for g in ags],key=lambda a: a.the_date)
			trade2article[tg] = the_articles[-1] if the_articles else None 
		
		tradebias = {}
		
		articles2eval = {}
		for tg, article in tqdm(trade2article.items()):	
			if article is not None:
				articles2eval[tg] = article
		
		article_bias_dict = self.evaluate_articles(articles2eval)
		
		pdb.set_trace()
		print('test result - get latest article from the_articles (or none for empty list)') 
		
		#check result against trade direction & reject if opposing 
		return_trades = [] 
		for t in trades: 
			bias = article_bias_dict.get(t.signal_id,TextBias.MIXED)
			if bias == TextBias.BEARISH and t.direction == TradeDirection.BUY:
				continue
			if bias == TextBias.BULLISH and t.direction == TradeDirection.SELL: 
				continue
			return_trades.append(t)
		
		return return_trades
		

	def get_news_guids(self,gtp,cursor):
		sql_row = "(%(guid)s,%(the_time)s)"
		sql_rows = [cursor.mogrify(sql_row,{'guid':tg[0],'the_time':tg[1]}).decode() for tg in gtp]
		cursor.execute(sql['news_guids_from_times'],{'guid_times':Inject(','.join(sql_rows))})
		results = cursor.fetchall()
		returndict = {}
		for [g,gs] in results:
			returndict[g] = gs
		return returndict
	
	def get_news_articles(self,aguids,cursor):
		cursor.execute(sql['news_articles_from_guids'],{'guids':aguids})
		news_article_dict = {} 
		for row in cursor.fetchall():
			news_article_dict[row[0]] = Article.from_database_row(row)
		return news_article_dict
	
	def evaluate_articles(self,article_dict):
		tguids = [g for g in article_dict]
		articles = [article_dict[g] for g in tguids]
		full_texts = [a.full_text for a in articles]
		text_chunk_size = 100
		print('fetching ai results...')
		impact_weight = 0.02
		
		def t2b(val):
			if val < -impact_weight:
				return TextBias.BEARISH
			if val > impact_weight:
				return TextBias.BULLISH
			return TextBias.MIXED
		biases = []
		for full_text_block in tqdm([full_texts[i:i+text_chunk_size] for i in range(0,len(full_texts),text_chunk_size)]):
			results = self.news_model.invoke(full_text_block)
			biases.extend([t2b(r['impact']) for r in results])
		
		return {g:b for (g,b) in zip(tguids,biases)} 
			
		




#class NextCurrencyStrengthFilter(DataBasedFilter):


#class LookAheadIndicatorFilter(IndicatorFilter): #idea




sql['news_guids_from_times'] = '''
WITH interesting_times AS (
	SELECT * FROM (
		VALUES %(guid_times)s
	) AS t(guid,the_date)
),
guid_pairings AS (
	SELECT it.guid, ARRAY_AGG(na.guid) AS guids FROM interesting_times it
	LEFT JOIN news_article na ON it.the_date > na.published_date AND it.the_date < na.published_date + INTERVAL '6 hours'
	GROUP BY it.guid 
)
SELECT guid, CASE WHEN guids[1] IS NULL THEN ARRAY[]::TEXT[] ELSE guids END AS guids FROM guid_pairings
'''

sql['news_articles_from_guids'] = '''
SELECT * FROM news_article na WHERE guid = ANY(%(guids)s)
'''


































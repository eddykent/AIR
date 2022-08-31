#news indicator - get sentiment from news articles & filter what goes against 
#next currency strength - 4h timescale next prediction

import numpy as np 
from tqdm import tqdm 

import pdb

from utils import overrides
from filters.trade_filter import *

sql = {} 

class NewsFilter(TimelineTradeFilter):

	news_model  = None 
	
	def __init__(self,news_model):
		self.news_model = news_model
	
	@overrides(TimelineTradeFilter)
	def filter(self,trades):
		pass

		
	#use times to get list of news article guids 
	
	#use guids to get distinct list of articles keyed by their guid 
	
	#for each time, find all relevant news articles 
	
	#pair up trades with news article guids 
	
	#run news articles through AI to determine bullish/bearish
	
	#check result against trade direction & reject if opposing 




#class NextCurrencyStrengthFilter(DataBasedFilter):


sql['news_guids_from_times'] = '''

'''



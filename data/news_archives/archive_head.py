

import sys
import pdb
from collections import namedtuple
import datetime
import time

import zlib
import hashlib
from tqdm import tqdm

sys.path.append('../..') #everyone hates it but this is for a standalone script so *f* :) if you have a better alternate THAT KEEPS IT STANDALONE my gosh, go for it!
#check
from web.scraper import Scraper
from utils import Database, ListFileReader, TimeHandler, Configuration, Inject
#from fundamental import KeywordMapHelper, ForexSlashHelper
from data.text import NewsArticle, DirectKeywordInstrumentMap


lfr = ListFileReader()
fx_pairs = lfr.read('../../fx_pairs/fx_mains.txt')
#fsh = ForexSlashHelper(fx_pairs=fx_pairs)
#keyword_map = KeywordMapHelper(keyword_map_file='../../config/keyword_mappings.json',fsh=fsh)

dkim = DirectKeywordInstrumentMap(fx_pairs=fx_pairs)

sql = {} 

config = Configuration('../../config.ini')
cur = Database(commit=False,cache=False,config=config)
th = TimeHandler()

def rollback_month(month,year):
	if month <= 1:
		month = 12
		year = year - 1
	else:
		month = month - 1
	return (month,year)

def now_to_x_months_back(current_month,current_year, n_months):
	month = current_month 
	year = current_year
	return_list = []
	for x in range(n_months):
		return_list.append((month,year))
		(month, year) = rollback_month(month,year)
	return return_list

sql['new_links'] = """
WITH links AS (
	SELECT UNNEST(%(links)s) AS link
)
SELECT link FROM links ls WHERE NOT EXISTS (
	SELECT 1 FROM news_article na WHERE na.link = ls.link
);
"""

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

 
 
 


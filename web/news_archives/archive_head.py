

import sys
import pdb
from collections import namedtuple
import datetime

import zlib
import hashlib
from tqdm import tqdm

sys.path.append('../..') #everyone hates it but this is for a standalone script so *f* :) if you have a better alternate THAT KEEPS IT STANDALONE my gosh, go for it!
#check
from web.scraper import Article, Scraper
from utils import Database, ListFileReader, TimeHandler, Configuration, Inject
from fundamental import KeywordMapHelper, ForexSlashHelper

lfr = ListFileReader()
fx_pairs = lfr.read('../../fx_pairs/fx_mains.txt')
fsh = ForexSlashHelper(fx_pairs=fx_pairs)
keyword_map = KeywordMapHelper(keyword_map_file='../../keyword_mappings.json',fsh=fsh)

upsert_query = ''
with open('../../queries/save_articles.sql') as f:
	upsert_query = f.read()

config = Configuration('../../config.ini')
cur = Database(commit=False,cache=False,config=config)
th = TimeHandler()






 
 
 
 


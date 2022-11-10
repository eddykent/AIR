

import datetime 
import time
import asyncio


##file for running any data fetching stuff to get latest data



#data to fetch:
# candlestick data
# volume data 
# economic calendar events 
# news data

#from data.tools.csv_upsert import *
#from data.tools.dukascopy import * 

from web.crawler import SeleniumHandler, XPathNavigator 
from web.scraper import Scraper


#from web.economic_calendar.tradingeconomics import pull_calendar
# async this! pull_calendar(2) 

from utils import ListFileReader, Database

from data.tools.dukascopy import Dukascopy

url = 'https://www.dukascopy.com/swiss/english/marketwatch/historical/'

lfr = ListFileReader()
	
instruments = lfr.read('fx_pairs/fx_mains.txt') #['EUR/USD','USD/JPY','GBP/AUD']
#instruments = ['GBP/CHF','GBP/JPY','GBP/NZD','GBP/USD','NZD/CAD','NZD/CHF','NZD/JPY','NZD/USD','USD/CAD','USD/CHF','USD/JPY']
date_from = datetime.datetime(2022,11,7,0,0)
date_to = datetime.datetime(2022,11,8,18,0)
#date_to = datetime.datetime.now() 
#date_from = date_to - datetime.timedelta(days=20)

cursor = Database(commit=True,cache=False)
with SeleniumHandler() as sh:
	duk = Dukascopy(sh,cursor)
	duk.begin()
	duk.set_gets(instruments, date_from, date_to)
	duk.perform()
	





















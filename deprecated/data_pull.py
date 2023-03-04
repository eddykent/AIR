

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

from data.tools.tradingeconomics import pull_calendar

# async this! 
pull_calendar(2) 


#news data 
#candlesticks 
#volume 


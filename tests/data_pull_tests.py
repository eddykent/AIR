from datetime import datetime, timedelta

import pandas as pd 
import pdb

#rom web.proxy import ProxyList

from utils import ListFileReader

from data.tools.cursor import Database 

from web.crawler import SeleniumHandler

--fixme
from data.tools.candle_snatcher import CandleSnatcherDukascopy
from data.tools.prep import TimelineMerge 
from data.tools.holefinder import HoleFinder

#pl = ProxyList() 
#proxies = pl.get_proxies()

#from data.base import *  #base dukascopy 
def wait_for_me():
	input()

#from data.tools.candle_snatcher import CandleSnatcherDukascopy 

#from web.economic_calendar.tradingeconomics import pull_calendar

# async this! 
#pull_calendar(2) #might need last month too for stats so 2

def run_one():
	
	from data.tools.dukascopy import Dukascopy #DukascopyCandles
	from data.tools.hole_finder import HoleFinder
	from data.tools.prep import TimelineMerge
	from web.crawler import Crawler, SeleniumHandler
	
	url = 'https://www.dukascopy.com/swiss/english/marketwatch/historical/'
	
	lfr = ListFileReader()
	
	fx_pairs = lfr.read('fx_pairs/fx_mains.txt') #['EUR/USD','USD/JPY','GBP/AUD']
	#fx_pairs = ['GBP/CHF','GBP/JPY','GBP/NZD','GBP/USD','NZD/CAD','NZD/CHF','NZD/JPY','NZD/USD','USD/CAD','USD/CHF','USD/JPY']
	#date_from = datetime.datetime(2023,1,23)
	#date_to = datetime.datetime(2022,10,6,0,0)
	#date_to = datetime.datetime.now() 
	#date_from = date_to - datetime.timedelta(days=20)
	
	date_from = datetime(2023,1,1)
	date_to = datetime.now() #- datetime.timedelta(days=1)
	
	cursor = Database(commit=True,cache=False)
	with SeleniumHandler() as sh:
		duk = Dukascopy(sh,cursor)
		for fx_pair in fx_pairs:
			duk.set_gets([fx_pair], date_from, date_to,1)
			duk.perform()
		
		wait_for_me()

		


def run_test():
	

	lfr = ListFileReader()
	#the_date = datetime(2023,1,1)
	#end_date = datetime.now() #- timedelta(days=1)
	

	
	
	fx_pairs = lfr.read('fx_pairs/fx_mains.txt')
	
	#before_trades
	date_start = datetime.now() - timedelta(days=1)
	date_end = datetime.now()
	today_data_tasks = [{'instrument':fxp, 'date_from':date_start , 'date_to':date_end} for fxp in fx_pairs]
	
	#fx_pairs = ['GBP/CAD','GBP/CHF','GBP/JPY','GBP/NZD','GBP/USD','NZD/CAD','NZD/CHF','NZD/JPY','NZD/USD','USD/CAD','USD/CHF','USD/JPY']
	#fx_pairs = ['USD/CHF','USD/JPY']
	#fx_pairs = ['AUD/USD']
	
	#date_from = datetime(2019,11,1)
	#date_to = datetime(2020,1,1)
	
	
	#csd.get_instruments(fx_pairs, the_date)
	
	#holefinder = HoleFinder(fx_pairs,the_date,end_date,check_volumes=True)
	#holes = holefinder.find_holes()
	
	#tlm = TimelineMerge()
	#data_tasks = tlm.hole_finder_tasks(holes)
	pdb.set_trace()
	#weekly = [wp.start_time.to_pydatetime() for wp in pd.period_range(start=the_date,end=end_date,freq='W')] + [end_date]
	
	#data_tasks = []
	
	#for date_from, date_to in zip(weekly[:-1],weekly[1:]):
	#	data_tasks += [{'instrument':fxp, 'date_from':date_from , 'date_to':date_to} for fxp in fx_pairs]
			
		
	#pdb.set_trace()
	csd = CandleSnatcherDukascopy(4) 
	csd.perform(today_data_tasks)


def csv_processor_test():
	
	from data.tools.dukascopy import DukascopyCSVProcessor
	
	cursor = Database(commit=True,cache=False) 
	instrument = 'AUD/CAD'
	directory = 'C:/Users/Ed/Downloads'
	
	handle = DukascopyCSVProcessor(directory,cursor)
	handle.acquire(instrument)









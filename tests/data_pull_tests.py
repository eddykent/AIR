from datetime import datetime, timedelta

import pandas as pd 
import pdb

from web.proxy import ProxyList

from utils import ListFileReader

from data.tools.candle_snatcher import CandleSnatcherDukascopy
from data.tools.prep import TimelineMerge 
from data.tools.hole_finder import HoleFinder

#pl = ProxyList() 
#proxies = pl.get_proxies()

#from data.base import *  #base dukascopy 


#from data.tools.candle_snatcher import CandleSnatcherDukascopy 

#from web.economic_calendar.tradingeconomics import pull_calendar

# async this! 
#pull_calendar(2) #might need last month too for stats so 2


def run_test():
	

	lfr = ListFileReader()
	the_date = datetime(2023,1,1)
	end_date = datetime.now() - timedelta(days=1)
	
	fx_pairs = lfr.read('fx_pairs/fx_mains.txt')
	#fx_pairs = ['GBP/CAD','GBP/CHF','GBP/JPY','GBP/NZD','GBP/USD','NZD/CAD','NZD/CHF','NZD/JPY','NZD/USD','USD/CAD','USD/CHF','USD/JPY']
	#fx_pairs = ['USD/CHF','USD/JPY']
	#fx_pairs = ['AUD/USD']
	
	#date_from = datetime(2019,11,1)
	#date_to = datetime(2020,1,1)
	
	
	#csd.get_instruments(fx_pairs, the_date)
	
	holefinder = HoleFinder(fx_pairs,the_date,end_date,check_volumes=True)
	holes = holefinder.find_holes()
	
	tlm = TimelineMerge()
	data_tasks = tlm.hole_finder_tasks(holes)
	pdb.set_trace()
	#weekly = [wp.start_time.to_pydatetime() for wp in pd.period_range(start=the_date,end=end_date,freq='W')] + [end_date]
	
	#data_tasks = []
	
	#for date_from, date_to in zip(weekly[:-1],weekly[1:]):
	#	data_tasks += [{'instrument':fxp, 'date_from':date_from , 'date_to':date_to} for fxp in fx_pairs]
			
		
	#pdb.set_trace()
	csd = CandleSnatcherDukascopy(1) 
	csd.perform(data_tasks)












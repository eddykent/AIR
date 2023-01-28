from datetime import datetime


from web.proxy import ProxyList

from utils import ListFileReader

from data.tools.candle_snatcher import CandleSnatcherDukascopy

#pl = ProxyList() 
#proxies = pl.get_proxies()

#from data.base import *  #base dukascopy 


#from data.tools.candle_snatcher import CandleSnatcherDukascopy 

from web.economic_calendar.tradingeconomics import pull_calendar

# async this! 
pull_calendar(1) 


def run_test():
	csd = CandleSnatcherDukascopy() 

	lfr = ListFileReader()
	the_date = datetime(2023,1,18)

	fx_pairs = lfr.read('fx_pairs/fx_mains.txt')
	#fx_pairs = ['GBP/CAD','GBP/CHF','GBP/JPY','GBP/NZD','GBP/USD','NZD/CAD','NZD/CHF','NZD/JPY','NZD/USD','USD/CAD','USD/CHF','USD/JPY']
	#fx_pairs = ['USD/CHF','USD/JPY']
	#fx_pairs = ['NZD/USD']
	
	#date_from = datetime(2019,11,1)
	#date_to = datetime(2020,1,1)
	
	#csd.perform(fx_pairs, date_from, date_to)
	csd.perform(fx_pairs, the_date)



import time 
import datetime


from utils import ListFileReader, Database

#with SeleniumHandler() as sh:
#sh = SeleniumHandler()  #will need to fix error with webdriver-manager to auto-detect chrome version somehow (report in install_instructions.md)
#sh.start()
#time.sleep(3)
#sh.finish()


def wait_for_me():
	input()


def client_sentiment():
	
	from web.crawler import Crawler, SeleniumHandler
	from web.client_sentiment_indicators import Dukascopy
	from utils import ListFileReader

	#url = 'forexclientsentiment.com/client-sentiment'
	url = 'https://www.dukascopy.com/swiss/english/marketwatch/sentiment/'
	lfr = ListFileReader()
	fx_pairs = lfr.read('fx_pairs/fx_mains.txt') + lfr.read('fx_pairs/currencies.txt')

	with SeleniumHandler(hidden=True) as sh:
		fcsc = Dukascopy(sh,fx_pairs)
		client_sentiment = fcsc.get_client_sentiment_info()
		#wait_for_me()

	print(client_sentiment)

def get_volumes():

	from data.tools.dukascopy import DukascopyVolumes #DukascopyCandles
	from web.crawler import Crawler, SeleniumHandler
	
	url = 'https://www.dukascopy.com/swiss/english/marketwatch/historical/'
	
	lfr = ListFileReader()
	
	instruments = lfr.read('fx_pairs/fx_mains.txt') #['EUR/USD','USD/JPY','GBP/AUD']
	#instruments = ['GBP/CHF','GBP/JPY','GBP/NZD','GBP/USD','NZD/CAD','NZD/CHF','NZD/JPY','NZD/USD','USD/CAD','USD/CHF','USD/JPY']
	date_from = datetime.datetime(2022,8,31,0,0)
	date_to = datetime.datetime(2022,10,6,0,0)
	#date_to = datetime.datetime.now() 
	#date_from = date_to - datetime.timedelta(days=20)
	
	cursor = Database(commit=True,cache=False)
	with SeleniumHandler() as sh:
		duk = DukascopyVolumes(sh,cursor)
		duk.set_gets(instruments, date_from, date_to)
		duk.perform()
		wait_for_me()


#get_volumes()














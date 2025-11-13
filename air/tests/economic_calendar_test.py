
import datetime
import pickle
import pdb

from data.capture.calendars import *

from web.crawler import SeleniumHandler



events = []

def run_test():
	cc = CalendarCollector()
	date_from = datetime.datetime.now() - datetime.timedelta(days=60)
	date_to = datetime.datetime.now()
	events = cc.get_events(date_from, date_to)
	
	with open('data/pickles/eventslist.pkl','wb') as f:
		pickle.dump(events,f)
	#events = []
	#with open('data/pickles/eventslist.pkl','rb') as f:
	#	events = pickle.load(f)
	#pdb.set_trace()
	cc.put_to_database(events) 
	

def run_one():


	month = datetime.datetime(2023,6,4)

	events = []
	with SeleniumHandler(hidden=False) as sh:
		calendar = TradingEconomics(selenium_handler=sh)
		events = calendar.get_events(month)
		
	#calendar = FXCO()
	#events = calendar.get_events(month)
	
	#pdb.set_trace()
	#print('database?')
	
	cc = CalendarCollector()
	cc.put_to_database(events) 
	#calendar = TradingEconomics()
	#events.extend(calendar.get_events(month))
	
	#pdb.set_trace()
	
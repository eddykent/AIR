

import datetime

##class for reading websites and getting the current state (eg forex client sentiment, common trades in forexfactory etc)
##data could  be logged in the database - use journalling for this 
#
#1) grab all useful data from websites (multi processing)
#2) use for influencing trades if needed (use in snapshot filters) 
#3) log to database for backtests later to gauge usefulness of the data in journal  
from web.scraper import Scraper
from data.tools import ProcessPool, ProcessWorker





class ForexFactory(Scraper):	
	
	def scrape(self):
		return {}



class MarketSnapshotWorker(ProcessWorker):
	
	def perform_task(self, snapshot_key):
		
		pass
		
		


class MarketSnapshot:
	

	def get_snapshot(self)
		workers = [///]
		
		toget = []
		
		process_pool = ProcessPool(workers)
		snapshot = process_pool.perform(toget)
		





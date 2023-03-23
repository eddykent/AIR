

import pdb

#from data.tools.marketsnapshot import MarketSnapshot
from data.capture.snapshot import *

from web.crawler import SeleniumHandler



snapshot = {}

def run_test():
	mss = MarketSnapshot()
	this_snap = mss.get_snapshot()
	snapshot.update(this_snap)
	mss.put_to_database(this_snap)
	

def run_one():
	global snapshot
	with SeleniumHandler(hidden=False) as sh:
		snap = EToro(selenium_handler=sh)
		snapshot.update(snap.crawl())
	
	#snap = DailyFXSR()  #ActionForexBias
	#snapshot.update(snap.scrape())
	
	#pdb.set_trace()
	
	
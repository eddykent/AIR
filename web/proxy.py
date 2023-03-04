
from collections import namedtuple

import pdb

from web.scraper import Scraper

url = 'https://free-proxy-list.net/'

ProxyInfo  = namedtuple('ProxyInfo','ip port cc country anon https google last_checked')

class ProxyList(Scraper):
	
	def __init__(self):
		super().__init__(url)
	
	def get_proxies(self):
		return self.scrape()
	
	def scrape(self):
		pdb.set_trace()
		self.html 
		trs = self.html.xpath('//div[contains(@class,"fpl-list")]//tbody//tr')
		proxies = [] 
		for tr in trs:
			tds = tr.xpath('//td/text()')
			if len(tds) >= 8:
				proxies.append(ProxyInfo(*tds[:8]))
		return proxies

class AssociateAccounts:	
	
	#get from a config or W/E any associated info that can be used with the proxy IP 
	#For example, if we are using a GB proxy then we probably want to use a GB email 
	# if we are using a US one, we might want Alpha vantage key to also be from a US 
	# IP to spoof them etc. 
	pass
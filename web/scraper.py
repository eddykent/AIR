
import requests_html
import datetime
import time
import re
import zlib

import json

from enum import Enum
from collections import namedtuple


import pdb

import logging 
log = logging.getLogger(__name__)


##format of a scraper object - a simple class that 'has a' html parsed inside it 
##client_sentiment_scraper objects inherit this
class Scraper:
	
	source = ''
	html = None
	#session = None
	proxy = None 
		
	def __init__(self,source=None,proxy=None,render=False):
		self.proxy = proxy
		if source: #delay the scrape if we dont know yet and this tool is being used iteratively :) 
			self.change_link(source,render)
		
		
	
	##function to override to get stuff from a website that we want
	def scrape(self):
		raise NotImplementedError('This method must be overridden')
	
	def change_link(self,link,render=False):
		self.source = link
		session = requests_html.HTMLSession()
		if self.proxy: 
			print(f"proxy = {self.proxy}")
			session.proxies.update({'http':self.proxy})
		log.debug(f"Performing get to {link}")
		response = session.get(self.source)
		self.html = response.html
		if render:
			self.html.render() #render the html from js first


	
















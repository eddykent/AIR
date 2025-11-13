
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
	session = None
	response = None
	headers = {} 
		
	def __init__(self,source=None,proxy=None,headers={}):
		self.proxy = proxy
		if source: #delay the scrape if we dont know yet and this tool is being used iteratively :) 
			self.change_link(source)
		
		
	
	##function to override to get stuff from a website that we want
	def scrape(self):
		raise NotImplementedError('This method must be overridden')
	
	def change_link(self,link):
		self.source = link
		self.session = requests_html.HTMLSession()
		if self.proxy: 
			print(f"proxy = {self.proxy}")
			session.proxies.update({'http':self.proxy})
		log.debug(f"Performing get to {link}")
		if self.headers:
			self.response = self.session.get(self.source,headers=self.headers)
		else:
			self.response = self.session.get(self.source)
		self.html = self.response.html

	def render(self,**kwargs):
		self.response.html.render(**kwargs) #render the html from js first
		self.html = self.response.html
	
	
















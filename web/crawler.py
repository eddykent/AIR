

from selenium import webdriver
from selenium.webdriver import ChromeOptions
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions
from selenium.common.exceptions import TimeoutException, ElementClickInterceptedException

from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webelement import WebElement

from webdriver_manager.chrome import ChromeDriverManager


import os 
import time

from utils import Configuration, TimeHandler


#crawler is a special case of scraper that uses selenium to get information. This is required for some websites 
#that we get news/info from since their front end has been obfuscated in some way. There's no escaping selenium ;)

#expose selenium first so it can be used in other apps across the base 
class SeleniumHandler:
	
	browser = None #main selenium handle constructed in this class 
	
	chrome_options = None
	
	screenshot_dir = ''
	downloads_dir = ''
	#WINDOW_SIZE = "1920,1080"
	
	def __init__(self,hidden=False,chrome_options=None):
		config = Configuration()
		self.downloads_dir = config.get('webdriver','downloads')
		self.screenshot_dir = config.get('webdriver','screenshots')
		
		if not chrome_options:
			chrome_options = ChromeOptions()
		#location = config.get('chrome_driver','location') #handled with ChromeDriverManager
		prefs = {"download.default_directory":self.downloads_dir}
		chrome_options.add_experimental_option("prefs",prefs)
		if hidden:
			chrome_options.add_argument('--headless')
		
		self.chrome_options = chrome_options
		
			
	
	#allow for use with with
	def __enter__(self):
		self.start()
		return self
	
	def __exit__(self, exc_type, exc_val, exc_tb):
		self.finish()
	
	def start(self):
		self.browser = webdriver.Chrome(\
			service=Service(ChromeDriverManager().install()),\
			chrome_options=self.chrome_options\
		)
		self.browser.implicitly_wait(1) #surely nothing will load longer than 1 seconds or we will use a longer wait using perform_wait
	
	def finish(self):
		self.browser.close() 
	
	#might be useful oneday! 
	def screenshot(self): 
		timestamp = TimeHandle.timestamp()
		#get number for fast screenshotting 
		number = 0
		stringnumber = str(number) if number > 9 else ('0'+str(number))  ##no more than 99 per second as that is just silly :) 
		timefilename = timestamp+'#'+stringnumber
		self.browser.get_screenshot_as_file(os.path.join(self.screenshot_dir,timefilename,'.png'))
		return timefilename
	
	#wrappers for ease of use (from the root node only - once they are called we lose the support of this class)
	def get(self,url):
		return self.browser.get(url)
		
	def switch_to_frame(self,iframe):
		return self.browser.switch_to.frame(iframe) 
	
	#handy method for waiting for elements to be present
	def perform_wait(self,by,query_str,expire=10):
		try:
			return WebDriverWait(self.browser,expire).until(
				expected_conditions.presence_of_element_located((by,query_str))
			)
		except TimeoutException as e:  #if element doesnt exist return None
			return None
	
	#for doing sub-elements of an element
	#def perform_wait_on(self,element,by,query_str,expire=5):
	#	try:
	#		return WebDriverWait(element,expire).until(   #not sure if can do on sub element :( - could do a query_string construction 
	#			expected_conditions.presence_of_element_located((by,query_str))
	#		)
	#	except TimeoutException as e:  #if element doesnt exist return None
	#		return None
	
	def find_element(self,by,query_str):
		return self.browser.find_element(by,query_str)
	
	def find_elements(self,by,query_str):
		return self.browser.find_elements(by,query_str)
	
	#performs a click by js instead of by selenium to prevent ElementClickInterceptedException
	def click_on(self,element):
		self.browser.execute_script("arguments[0].click();", element)

#wrapper for SeleniumHandler and used as base for any crawlers
class Crawler:

	#get from initialisation - we don't want to run 20 copies of selenium
	browser = None
	source = ''
	
	def __init__(self,selenium_handle,source):
		self.source = source
		self.browser = selenium_handle.browser
		self.goto(self.source)
	
	def goto(self,url): #handle any other protos? 
		if not url.startswith('http'):
			url = 'http://' + url 
		self.browser.get(url)

	def loading_wait(self):
		return True  #some advanced method to determine if page has finished loading and we can begin crawling? - perhaps not needed!
		
		
	def crawl(self):
		raise NotImplementedError('This method must be overridden')

	
	



from selenium import webdriver
from selenium.webdriver import ChromeOptions
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions
from selenium.common.exceptions import TimeoutException, ElementClickInterceptedException, ElementNotInteractableException

from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.by import By
from selenium.webdriver.common.proxy import Proxy, ProxyType
from selenium.webdriver.remote.webelement import WebElement

from webdriver_manager.chrome import ChromeDriverManager
#from webdriver_manager.utils import ChromeType

import os 
import re
import time

import pdb

from utils import Configuration, TimeHandler


#crawler is a special case of scraper that uses selenium to get information. This is required for some websites 
#that we get news/info from since their front end has been obfuscated in some way. There's no escaping selenium ;)

#expose selenium first so it can be used in other apps across the base. Handle construction & teardown in this class
class SeleniumHandler:
	
	browser = None #main selenium handle constructed in this class 
	
	chrome_options = None
	
	config = None
	#WINDOW_SIZE = "1920,1080"
	capabilities = None
	
	def __init__(self,hidden=False,chrome_options=None,proxy=None,config=None):
		if config is None:
			self.config = Configuration()
		else:
			self.config = config
		
		if not chrome_options:
			chrome_options = ChromeOptions()
		#location = config.get('chrome_driver','location') #handled with ChromeDriverManager
		downloads_dir = self.config.get('webdriver','downloads')
		prefs = {"download.default_directory":downloads_dir}
		chrome_options.add_experimental_option("prefs",prefs)
		if hidden:
			chrome_options.add_argument('--headless')
			chrome_options.add_argument('--window-size=1920,1080')
			#chrome_options.add_argument("--disable-web-security")
			#chrome_options.add_argument("--disable-site-isolation-trials")
		
		self.capabilities = webdriver.DesiredCapabilities.CHROME
		if proxy:
			prox = Proxy()
			prox.proxy_type = ProxyType.MANUAL
			prox.http_proxy = proxy
			prox.socks_proxy = proxy
			prox.ssl_proxy = proxy
			prox.socks_version = 5

			prox.add_to_capabilities(self.capabilities)
			
			#chrome_options.add_argument('--proxy-server=%s' % proxy)
		
		self.chrome_options = chrome_options
				
	
	#allows for use with context managers 
	def __enter__(self):
		self.start()
		return self
	
	def __exit__(self, exc_type, exc_val, exc_tb):
		self.finish()
	
	def start(self):
		self.browser = webdriver.Chrome(\
			service=Service(ChromeDriverManager().install()),\
			chrome_options=self.chrome_options,\
			desired_capabilities=self.capabilities\
		)
		#self.browser.implicitly_wait(0.5) #surely nothing will load longer than 0.5 seconds or we will use a longer wait using perform_wait
	
	def finish(self):
		self.browser.close() 
	


#wrapper for SeleniumHandler and used as base for any crawlers
class Crawler:

	#get from initialisation - we don't want to run 20 copies of selenium
	browser = None
	source = ''
	config = None
	
	def __init__(self,selenium_handle,source,config=None):
		self.source = source
		self.browser = selenium_handle.browser
		#self.config = selenium_handle.config
		if config is None:
			config = selenium_handle.config
		self.config = config
		self.goto(self.source)

	
	def get(self,url):
		return self.browser.get(url)
	
	def page_source(self):
		return self.browser.page_source
	
	def goto(self,url): #handle any other protos? 
		if not url.startswith('http'):
			url = 'http://' + url 
		return self.get(url)
		
	def switch_to_frame(self,iframe):
		return self.browser.switch_to.frame(iframe) 
	
	#handy method for waiting for elements to be present
	def perform_wait(self,by,query_str,expire): #warn if more than 1 found! 
		try:
			return WebDriverWait(self.browser,expire).until(
				expected_conditions.presence_of_element_located((by,query_str))
			)
		except TimeoutException as e:  #if element doesnt exist return None
			return None
	
	def perform_wait_nonexist(self,by,query_str,expire):
		try:
			WebDriverWait(self.browser,expire).until_not(
				expected_conditions.presence_of_element_located((by, query_str))
			)
			return True
		except TimeoutException as e:
				return False
	
	def perform_wait_text(self,by,query_str,expire):
		#try:
		#	return WebDriverWait(self.browser,expire).until(
		#		expected_conditions.text_to_be_present_in_element_value((by,query_str),' ')
		#	)
		#except TimeoutException as e:  #if element doesnt exist return None
		#	return None
		some_text = ''
		start_time = time.time()
		while not some_text:
			time_waited = time.time() - start_time
			if time_waited > 1.0:
				break
			time.sleep(0.01)
			some_element = self.perform_wait(by,query_str,expire) #wait for animation 
			some_text = some_element.text
		return some_text
	
	def perform_wait_multi(self,by,query_str,expire):
		self.perform_wait(by,query_str,expire) #as usual
		return self.find_elements(by,query_str) #but now return a multi 
		
	
	def screenshot(self): 
		timestamp = TimeHandle.timestamp()
		#get number for fast screenshotting 
		number = 0
		stringnumber = str(number) if number > 9 else ('0'+str(number))  ##no more than 99 per second as that is just silly :) 
		timefilename = timestamp+'#'+stringnumber
		screenshot_dir = self.config.get('webdriver','screenshots')
		self.browser.get_screenshot_as_file(os.path.join(screenshot_dir,timefilename,'.png'))
		return timefilename
	
	def switch_to_frame(self,iframe):
		return self.browser.switch_to.frame(iframe) 
	
	def find_element(self,by,query_str):
		return self.browser.find_element(by,query_str)
	
	def find_elements(self,by,query_str):
		return self.browser.find_elements(by,query_str)
	
	#performs a click by js instead of by selenium to prevent ElementClickInterceptedException
	def click_on(self,element):
		self.browser.execute_script("arguments[0].click();", element)
	
	
	def process_website_row(self, by, row_element, key_renames):
		result_dict = {}
		#if by == 'label':	#other methods of parsing the row could go here 
		#else:
		for (key, new_key) in key_renames.items():
			result_dict[new_key] = None
			elem = row_element.find_element(by,key) #work out how to wait here? 
			if elem:
				result_dict[new_key] = elem.text.strip()
		return result_dict
	
	def process_website_rows(self, by, row_elements, key_renames):
		return [self.process_website_row(by,row_elem,key_renames) for row_elem in row_elements]
	
	def safefloat(self,fpstr):
		if type(fpstr) in [int,float]:
			return fpstr #already a number
		try:
			return float(re.sub('[^0-9.]','',fpstr)) #take out commas
		except ValueError as e:
			#warning!
			if fpstr == '-' or fpstr == '':
				return None #means blank so leave it as that
			else:
				pdb.set_trace()
				print('unable to parse float')
	
	def safeint(self,intstr):
		fp = self.safefloat(intstr)
		return int(fp) if fp is not None else None
	
	def process_row_floating_points(self,row_dict,float_keys):
		for fk in float_keys:
			row_dict[fk] = self.safefloat(row_dict.get(fk))
		return row_dict
	
	def process_row_ints(self,row_dict,int_keys):
		for ik in int_keys:
			row_dict[ik] = self.safeint(row_dict.get(ik))
		return row_dict
	
	def crawl(self):
		raise NotImplementedError('This method must be overridden')
	
	def poll_interaction(self, interaction_function, poll_length_seconds):
		start = time.time()
		while time.time() - start < poll_length_seconds:
			try:
				interaction_function()
				return 
			except ElementNotInteractableException:
				time.sleep(0.2) #keep trying every 5th of a second
		raise ElementNotInteractableException(f"element not interactable, even after {time.time() - start} seconds.")
			
			

#wrapper class for crawler that is powered by xpath to crawl a webpage and find elements. Always start from the root nod
class XPathNavigator(Crawler):
	
	@staticmethod
	def __to_xpath(*_xpath_dicts):
		xpath_strings = []
		for _xpath_dict in _xpath_dicts:
			xpath_template = ''
			if 'tag' in _xpath_dict:
				xpath_template += '{tag}'#this particular tag
			else:
				xpath_template += '*' #all tags
			
			#check attributes - remove tag as it is not an attribute 
			attribute_keys = [k for k in _xpath_dict.keys() if k != 'tag']
			attributes_template = ''
			if attribute_keys:
				attribute_templates = []
				for k in attribute_keys:	
					if k.startswith('sub'):
						#check for a contains - useful for selecting things with css class lists 
						lexi = k[3:] #remove the inital sub to get the attribute name
						if lexi[-1].isdigit() and not lexi.startswith('data'): #the key might have a number on the end (eg subclass1 subclass2 etc)
							#but for data-something we probably want to keep the number. 
							lexi = lexi[:-1] #remove last digit
							#dont bother supporting full numbers yet - 0 to 9 is fine!
						attribute_templates.append("contains(@"+lexi+","+"'{"+k+"}')")
					else:
						attribute_templates.append("@"+k+"="+"'{"+k+"}'")
				attributes_template = '['+' and '.join(attribute_templates)+']'
			xpath_template += attributes_template
			xpath_strings.append(xpath_template.format(**_xpath_dict)) #paste the actual contents of the dictionary into the template
		return '//' + '//'.join(xpath_strings)

	@staticmethod
	def __process_arg_to_xpath(xpath_arg):
		query_str = ''
		if type(xpath_arg) == list:
			query_str = XPathNavigator.__to_xpath(*xpath_arg) #build xpath string from parent
		else:
			query_str = XPathNavigator.__to_xpath(xpath_arg)
		return query_str
	
	#wrappers for readability 
	def get_element(self,xpath_arg,expire=10): 
		return self.perform_wait(By.XPATH, XPathNavigator.__process_arg_to_xpath(xpath_arg), expire)
	
	def get_multiple_elements(self,xpath_arg,expire=10):
		return self.perform_wait_multi(By.XPATH, XPathNavigator.__process_arg_to_xpath(xpath_arg), expire)
		
	def wait_nonexistant(self,xpath_arg,expire):
		return self.perform_wait_nonexist(By.XPATH,XPathNavigator.__process_arg_to_xpath(xpath_arg), expire)
	
	def get_attribute(self,element,attribute_key):
		return element.get_attribute(attribute_key)
	
	def get_text(self,element):
		return element.text.strip()
	
	#select return element from a parent element, based on another conditional element in the parent using a predicate
	def get_element_junctional(self,xpath_parent,xpath_return,xpath_condition,predicate,expire=2):
		parent_rows = self.get_multiple_elements(xpath_parent,expire)
		for row in parent_rows:
			#pdb.set_trace()
			condition_xpath = '.'+XPathNavigator.__process_arg_to_xpath(xpath_condition)
			return_xpath = '.'+XPathNavigator.__process_arg_to_xpath(xpath_return)
			condition_element = row.find_element(By.XPATH, condition_xpath)
			return_element = row.find_element(By.XPATH, return_xpath)
			if condition_element is None or return_element is None:
				continue
			if predicate(condition_element) is True:
				return return_element
		return None
	
	def wait_for_text(self,xpath_arg,expire=2):
		return self.perform_wait_text(By.XPATH,XPathNavigator.__process_arg_to_xpath(xpath_arg), expire)
		
	def type_keys_on(self,element,string):
		element.send_keys(string)
	
	#type_keys doesnt work with integer/float fields so well. this method handles that nicely. 
	def type_number_on(self,element,numeric,sf=3):
		#first delete the current value
		
		new_value = self.safefloat(numeric) if type(numeric) == str else numeric
		assert type(new_value) in [float,int]
		
		current_val = self.get_attribute(element,'value')
		n = len(current_val)
		for i in range(n):
			element.send_keys(Keys.BACKSPACE)
		
		#add value up to decimal point 
		new_val0 = float(new_value)
		new_val1 = str(int(new_value))
		element.send_keys(new_val1)
		
		number_pieces = ('{:.'+str(sf)+'f}').format(new_value).split('.')
		
		if new_val0 != int(new_val0) and len(number_pieces) > 1:
			#we have something fractional. 
			element.send_keys('.') #try sending it a decimal point
			if self.get_attribute(element,'value').endswith('.'):
				#decimal worked! Add rest of quantity
				new_val2 = number_pieces[1]
				element.send_keys(new_val2)

	def has_class(self,element,class_name):
		class_list_str = self.get_attribute(element,'class')
		class_list = class_list_str.split(' ')
		return class_name in class_list

	#try js or selenium click - perhaps have handler here to do the click in either using js as fallback 
	def click_on(self,element):
		self.browser.execute_script("arguments[0].click();", element)

	def press_enter_on(self,element):
		element.send_keys(Keys.ENTER)
		



























from web.crawler import SeleniumHandler, By

#this is a web crawler script for downloading economic calendar information from a website called
#tradingeconomics. The data is captured and stored in the database. 

class TradingEconomics(XPathNavigator):	
	
	url = 'https://tradingeconomics.com/calendar#'
	
	def __init__(self,selenium_handler):
		super.__init__(selenium_handler,self.url)
	
	def by_id(self,id):
		return self.browser.find_element(By.ID,id)
	
	def setup(self):	
		#click the buttons to get the correct countries etc 
		timedropdown = self.by_id('DropDownListTimezone')
		button = {'tag':'button','onclick':'toggleMainCountrySelection();'}
		self.click_on(timedropdown)
		for utc in timedropdown.find_elements(By.TAGNAME,'option'):
			if utc.get_attribute('value') == '0':
				self.click_on(utc)
				break
		#select all countries
		self.browser.execute_script("calendarSelecting(this, event, 'World', true);");
		#countries_button = self.get_element(button)
		#self.click_on(countries_button)
		
	def gotomonth(self,datetime):
		pass
	
	#def read_lines(self,)
		
		
		
		
		
		
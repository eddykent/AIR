
import datetime
import sys
from tqdm import tqdm

import pdb
import time


from web.crawler import SeleniumHandler, By, XPathNavigator, Keys
from requests_html import HTML 
from utils import Database, Inject

from fundamental import CalendarEvent

#this is a web crawler script for downloading economic calendar information from a website called
#tradingeconomics. The data is captured and stored in the database. 

class TradingEconomics(XPathNavigator):	
	
	url = 'https://tradingeconomics.com/calendar#'
	
	country_map = {  #only list what we are interested in here. 
		'AU':'Australia',
		'JP':'Japan',
		'US':'USA',
		'EU':'European Union',
		'EA':'European Area',
		'ES':'Spain',
		'IT':'Italy',
		#'ZA':'South Africa',
		'HK':'Hong Kong',
		'NZ':'New Zealand',
		'NO':'Norway',
		#'SE':'Sweden', 
		'DK':'Denmark',
		'FI':'Finland',
		'DE':'Germany',
		'CA':'Canada',
		#'KR':'South Korea',
		#'SG':'Singapore',
		#'CN':'China',
		#'RU':'Russia',
		'CH':'Switzerland',
		'FR':'France',
		'GB':'United Kingdom',
		'IE':'Ireland',
		#'BR':'Brazil',
		#'PH':'Philippines',
		#'IN':'India',
		#'TH':'Thailand',
		#'TR':'Turkey',
		'BE':'Belgium',
		#'MX':'Mexico',
		#'PL':'Poland',		
	}
	
	sql_file = 'queries/economic_calendar_upsert.sql'
	sql_row = "(%(the_date)s,%(impact)s,%(country)s,%(description)s,%(actual)s,%(previous)s,%(consensus)s,%(forecast)s)"
	
	def __init__(self,selenium_handler):
		super().__init__(selenium_handler,self.url)
	
	def by_id(self,id):
		return self.browser.find_element(By.ID,id)
	
	def setup(self):	
		#click the buttons to get the correct countries etc 
		#click ONLY the relevant countries instead? eg switzerland
		
		_major_countries_button = {'tag':'span','subonclick1':'calendarSelecting(this, event','subonclick2':'G20'}
		
		_countries_list = {'tag':'span','id':'te-c-all'}
		_switzer = {'tag':'li','subclass':'te-c-option-che'}
		_belgium = {'tag':'li','subclass':'te-c-option-bel'}
		_denmark = {'tag':'li','subclass':'te-c-option-dnk'}
		_finland = {'tag':'li','subclass':'te-c-option-fin'}
		_ireland = {'tag':'li','subclass':'te-c-option-irl'}
		_netherl = {'tag':'li','subclass':'te-c-option-nld'}
		_new_zea = {'tag':'li','subclass':'te-c-option-nzl'}
		_norway = {'tag':'li','subclass':'te-c-option-nor'}
		_portugal = {'tag':'li','subclass':'te-c-option-prt'}
		_singapo = {'tag':'li','subclass':'te-c-option-sgp'}
		_sweden = {'tag':'li','subclass':'te-c-option-swe'}
		
		
		#add more when needed?
		#_all_countries_button = {'tag':'span','subonclick1':'calendarSelecting(this, event','subonclick2':'World'}
		
		timedropdown = self.by_id('DropDownListTimezone')
		#self.click_on(timedropdown)
		timedropdown.click()
		
		utc = timedropdown.find_element(By.XPATH,"./option[@value='0']")
		#self.click_on(utc)
		utc.click()
		
		#select main countries
		self.browser.execute_script("toggleMainCountrySelection();"); #perhaps check it is showing first!
		
		#all_countries_button = self.get_element(_all_countries_button)
		#self.click_on(all_countries_button)
		
		major_countries_button = self.get_element(_major_countries_button)
		self.click_on(major_countries_button)
		
		#missing countries! lets click them:
		missing_countries = [_switzer,_belgium,_denmark,_finland,_ireland,_netherl,_new_zea,_norway,_portugal,_singapo,_sweden]
		for _m in missing_countries:
			print(_m)
			elem = self.get_element([_countries_list,_m])
			elem.click()
		
		self.browser.execute_script("saveSelectionAndGO();");
		
		
		
	def gotomonth(self,month):
		_dates_dd = {'tag':'a','data-target':'#datesDiv'}
		_submit_container = {'tag':'div','id':'datesDiv'}
		_submit = {'tag':'button'}
		
		def __next_month(_month):
			year = _month.year
			month = _month.month
			new_month = month + 1
			if new_month == 13:
				new_month = 1
				year = year + 1
			return datetime.datetime(year,new_month,1)
		
		date_btn = self.get_element(_dates_dd)
		
		self.click_on(date_btn)
		
		time.sleep(0.5)
		start_date_field = self.by_id('startDate')
		end_date_field = self.by_id('endDate')
		
		
		next_month = __next_month(month)
		start_str = str(month.year) + '-' + str(month.month)
		end_str = str(next_month.year) + '-' + str(next_month.month)
		
		start_date_field.clear()
		end_date_field.clear()
		
		self.type_keys_on(start_date_field,start_str)
		self.type_keys_on(end_date_field,end_str)
		
		submit_btn = self.get_element([_submit_container,_submit])
		self.click_on(submit_btn)
		
	
		
	
	def read_events(self,month):
		table = self.by_id('calendar')
		table_heads = table.find_elements(By.XPATH,"./thead[@class='table-header']") #has the date!
		table_bodies = table.find_elements(By.XPATH,"./tbody") #has the data!
		
		assert len(table_heads) == len(table_bodies),f" {len(table_heads)} table heads yet {len(table_bodies)} table bodies for {month}"
		
		calendar_events = []
		
		calendar_parts = list(zip(table_heads,table_bodies))
		print(f"Reading {month}...")
		for head,body in tqdm(calendar_parts):
			date_str = self.get_text(head.find_element(By.XPATH,"./tr/th[@colspan='3']" ))
			year,month,day = self.__handle_date(date_str)
			for tr in tqdm(body.find_elements(By.TAG_NAME,'tr'), leave=False): #filter for repeats? 
				tds = tr.find_elements(By.TAG_NAME,'td')
				if len(tds) < 7:
					continue
					
				country = self.country_map.get(self.get_text(tds[1]))  
				time_str = self.get_text(tds[0])
				if country and time_str:
					impact_span = tds[0].find_element(By.TAG_NAME,'span') #holds rating
					impact_class = impact_span.get_attribute('class')
					impact = 1
					if impact_class.endswith('2'):
						impact = 2
					if impact_class.endswith('3'):
						impact = 3
						
					description = self.get_text(tds[2])
					actual = self.get_text(tds[3])
					previous = self.get_text(tds[4])
					consensus = self.get_text(tds[5])
					forecast = self.get_text(tds[6])
				
					hour,minute = self.__handle_time(time_str)
					try:
						the_date = datetime.datetime(year,month,day,hour,minute)
					except:
						print('funny time?')
						pdb.set_trace()
					event = CalendarEvent(the_date,impact,country,description,actual,previous,consensus,forecast)
					calendar_events.append(event)
		return list(set(calendar_events))
	
	#use the requests inbuilt html parser on the snapshot of the page source instead of seleniums parse
	def scrape_events(self,month):
		time.sleep(2) #wait seconds for page to load
		html = HTML(html=self.page_source())
		
		table_heads = html.xpath("//table[@id='calendar']/thead[@class='table-header']")
		table_bodies = html.xpath("//table[@id='calendar']/tbody") #finds a million otherwise!
		
		assert len(table_heads) == len(table_bodies),f" {len(table_heads)} table heads yet {len(table_bodies)} table bodies for {month}"
		
		calendar_events = []
		calendar_parts = list(zip(table_heads,table_bodies))
		print(f"Reading {month}...")
		for head,body in tqdm(calendar_parts):
			date_str = head.xpath(".//tr//th[@colspan='3']",first=True).text
			year,month,day = self.__handle_date(date_str)
			for tr in tqdm(body.find('tr'), leave=False): #filter for repeats? 
				td_items = tr.find('td.calendar-item')
				impact_td = tr.find('td',first=True)
				description_elem = tr.find('a.calendar-event',first=True)
				if not description_elem:
					continue
				if len(td_items) < 5:
					continue
				country = self.country_map.get(td_items[0].text)  
				time_str = impact_td.text
				if country and time_str:
					impact_span = impact_td.find('span',first=True) #holds rating
					impact_class = impact_span.attrs.get('class',('',))[0]
					impact = 1
					if impact_class.endswith('2'):
						impact = 2
					if impact_class.endswith('3'):
						impact = 3
						
					description = description_elem.text
					actual = td_items[1].text
					previous = td_items[2].text
					consensus = td_items[3].text
					forecast = td_items[4].text
					
					hour,minute = self.__handle_time(time_str)
					try:
						the_date = datetime.datetime(year,month,day,hour,minute)
					except:
						print('funny time?')
					#pdb.set_trace()
					event = CalendarEvent(the_date,impact,country,description,actual,previous,consensus,forecast)
					calendar_events.append(event)
		return list(set(calendar_events))
				
	
	def load_months(self,months):
		self.setup()
		for month in months: 
			self.gotomonth(month)
			events = self.scrape_events(month) 
			
			with Database(cache=False,commit=True) as cursor:
				with open(self.sql_file,'r') as f:
					query = f.read()
					sql_rows = [cursor.mogrify(self.sql_row,dict(event._asdict())).decode() for event in events]
					cursor.execute(query,{'calendar_events':Inject(','.join(sql_rows))})
			
	
	@staticmethod
	def __handle_date(date_str):
		month_strings = {
			'january':1,
			'february':2,
			'march':3,
			'april':4,
			'may':5,
			'june':6,
			'july':7,
			'august':8,
			'september':9,
			'october':10,
			'november':11,
			'december':12
		}
		bits = date_str.split(' ')
		#if len(bits) > 3:
		dow,m_str,day,year = bits[:4]
		m = month_strings.get(m_str.lower(),0)
		assert m > 0, f"Unknown month '{m_str}'"
		d = int(day)
		y = int(year)
		return y,m,d
	
	@staticmethod
	def __handle_time(time_str):
		timebits = time_str.split(' ')[0].split(':')
		try:
			hour = int(timebits[0])
			minute = int(timebits[1])
		except:
			pdb.set_trace()
		if time_str.endswith('PM') and hour < 12:
			hour += 12
		if time_str.endswith('AM') and hour == 12:
			hour = 0
		return hour, minute

#export ? 
def pull_calendar(n_months_back):
	the_date = datetime.datetime.now() 

	def __prev_month(_month):
		year = _month.year
		month = _month.month
		new_month = month - 1
		if new_month == 0:
			new_month = 12
			year = year - 1
		return datetime.datetime(year,new_month,1)
	
	def _next_month(_month):
		year = _month.year
		month = _month.month
		new_month = month + 1
		if new_month == 13:
			new_month = 1
			year = year + 1
		return datetime.datetime(year,new_month,1)	

	this_month = _next_month(datetime.datetime(the_date.year,the_date.month,1))
	all_months = [this_month]
	current_month = this_month
	for i in range(n_months_back):
		current_month = __prev_month(current_month)
		all_months.append(current_month)

	with SeleniumHandler() as sh:
		te = TradingEconomics(sh)
		te.load_months(all_months)

#pull_calendar(2)














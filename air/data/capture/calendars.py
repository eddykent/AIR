
import datetime
import calendar
import sys
from tqdm import tqdm

from requests_html import HTML
import lxml
import pandas as pd

import re

import logging 
log = logging.getLogger(__name__)

import pdb
import time

import random

from air.web.scraper import Scraper
from air.web.crawler import SeleniumHandler, Crawler, By, XPathNavigator, Keys

from air.data.tools.processpool import ProcessWorker, ProcessPool


from air.data.tools.cursor import Database, Inject


from air.utils import overrides, ListFileReader, CountryCurrencyMap


#this file has web crawler scripts and scrapers for downloading economic calendar information by month
#data is captured and stored in the database. 

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

def country_merge(country_str):
	if country_str == 'United States':
		country_str = 'USA'
	if country_str == 'Euro Area':
		country_str = 'European Area'
	if country_str not in country_map.values():
		log.warning(f"{country_str} is not on the country map.") #log all to reduce errors at once 
		return None
		
	return country_str 

ccm = CountryCurrencyMap()

def calendar_ref(link):
	bits = re.split('//|/|\?',link)
	servername = bits[1]
	return servername.lower().replace('www.','') 


def safe_float(string):
	try:	
		return float(re.sub('[^0-9.\-+]','',string))
	except ValueError as ve:
		pdb.set_trace()
		log.warning(f"'{string}' was not able to be converted to float. Returning None")
		#log.warning(''.join(traceback.format_tb(ve.__traceback__))) #cant get where it was called from :(
		return None
		
		
def safe_int(string):
	try:	
		return int(float(re.sub('[^0-9.\-+]','',string)))
	except ValueError as ve:
		pdb.set_trace()
		log.warning(f"'{string}' was not able to be converted to int. Returning None")
		#log.warning(''.join(traceback.format_tb(ve.__traceback__)))
		return None

class CalendarReader:
	
	use_selenium = False
	
	def get_events(self, month):
		raise NotImplementedError('This method must be overridden')
	
	
	
	@staticmethod #get next month from current month
	def next_month(_month):
		year = _month.year
		month = _month.month
		new_month = month + 1
		if new_month == 13:
			new_month = 1
			year = year + 1
		return datetime.datetime(year,new_month,1)


class TradingEconomics(XPathNavigator,CalendarReader):	
	
	url = 'https://tradingeconomics.com/calendar'
	use_selenium = True
		
	def __init__(self,selenium_handler):
		super().__init__(selenium_handler,self.url)
		self.setup()
	
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
		bits = [x.strip() for x in date_str.split(' ')]
		bits = [b for b in bits if b]
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
		
		timedropdown = self.browser.find_element(By.ID,'DropDownListTimezone')
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
		
		
	def goto_month(self,month):
		_dates_dd = {'tag':'a','data-target':'#datesDiv'}
		_submit_container = {'tag':'div','id':'datesDiv'}
		_submit = {'tag':'button'}
		
		date_btn = self.get_element(_dates_dd)
		self.click_on(date_btn)
		
		time.sleep(0.5)
		start_date_field = self.browser.find_element(By.ID,'startDate')
		end_date_field = self.browser.find_element(By.ID,'endDate')
		
		
		next_month = CalendarReader.next_month(month)
		start_str = str(month.year) + '-' + str(month.month)
		end_str = str(next_month.year) + '-' + str(next_month.month)
		
		start_date_field.clear()
		end_date_field.clear()
		
		self.type_keys_on(start_date_field,start_str)
		self.type_keys_on(end_date_field,end_str)
		
		submit_btn = self.get_element([_submit_container,_submit])
		self.click_on(submit_btn)
		
	#@staticmethod 
	#def process_value_elem(value_elem):
		
	
	
	#use the requests inbuilt html parser on the snapshot of the page source instead of seleniums parse
	@overrides(CalendarReader)
	def	get_events(self,month):
		self.goto_month(month) #naviget to correct month 
		
		time.sleep(1) #wait seconds for page to load?
		
		html = lxml.etree.HTML(self.browser.page_source)
		
		table_heads = html.xpath("//table[@id='calendar']/thead[@class='table-header']")
		table_bodies = html.xpath("//table[@id='calendar']/tbody") #finds a million otherwise!
		
		assert len(table_heads) == len(table_bodies),f" {len(table_heads)} table heads yet {len(table_bodies)} table bodies for {month}"
		
		calendar_events = []
		calendar_parts = list(zip(table_heads,table_bodies))
		print(f"Reading {month}...")
		for head,body in tqdm(calendar_parts):
			
			date_str = head.xpath(".//tr//th[@colspan='3']")[0].text
			year,month,day = self.__handle_date(date_str)
			
			#pdb.set_trace()
			for tr in tqdm(body.cssselect('tr'), leave=False): #filter for repeats? 
				
				td_items = tr.cssselect('td.calendar-item')
				impact_td = tr.cssselect('td')[0]
				description_elem = tr.cssselect('a.calendar-event')
				
				if not description_elem:
					continue
				
				if len(td_items) < 5:
					continue
				
				country = country_map.get('\n'.join(td_items[0].itertext()).strip())  
				time_str = '\n'.join(impact_td.itertext()).strip()
				
				if country and time_str:
					impact_span = impact_td.cssselect('span')[0] #holds rating
					impact_class = impact_span.attrib.get('class',('',))[0]
					impact = 1
					if impact_class.endswith('2'):
						impact = 2
					if impact_class.endswith('3'):
						impact = 3
						
					description = '\n'.join(description_elem[0].itertext()).strip()
					actual = '\n'.join(td_items[1].itertext()).replace('®','').strip()
					previous = '\n'.join(td_items[2].itertext()).replace('®','').strip()
					consensus = '\n'.join(td_items[3].itertext()).replace('®','').strip() 
					forecast = '\n'.join(td_items[4].itertext()).replace('®','').strip()
					
					hour,minute = self.__handle_time(time_str)
					try:
						the_date = datetime.datetime(year,month,day,hour,minute)
					except:
						print('funny time?')
					#pdb.set_trace()
					event = {
						'the_date':the_date,
						'impact':impact,
						'source_ref':calendar_ref(self.url),
						'country':country, 
						'currency':ccm.country_currency_map.get(country,'?'),
						'description':description,
						'actual':actual,
						'previous':previous,
						'consensus':consensus,
						'forecast':forecast
					}
					calendar_events.append(event)
				
		return calendar_events
				
#class TradingEconomicsAPI(CalendarReader):  #need API key (email them!)
#	
#	url = 'https://tradingeconomics.com/calendar'
#	
#	@overrides(CalendarReader)
#	def	get_events(self,month):
#		#use their python package!
		

class DailyFXEconomicCalendarDay(Scraper):
	
	impacts = {
		'low':1,
		'medium':2,
		'high':3
	}
	
	@staticmethod
	def process_value_elem(value_elem):
		if value_elem:
			if value_elem[0].text:
				value = value_elem[0].text.replace('®','').strip()
				if value:
					return value 
		return None
		
		
	@overrides(Scraper)	
	def scrape(self):
		self.render() #ensure js finished loading
		html = lxml.etree.HTML(self.html.html)
		table_rows = html.cssselect("table.dfx-economicCalendarExpandableTable tr.dfx-expandableTable__row")
		
		source_ref = calendar_ref(self.source.split('#')[0])
		
		calendar_events = []
		
		#pdb.set_trace()
		
		current_datetime = None 
		current_country = None
		for table_row in table_rows: #check: runs down the list from top to bottom of page
			
			time_elems = table_row.cssselect("span.dfx-economicCalendarRow__time")
			if time_elems:
				timestr = time_elems[0].attrib.get('data-time')
				if timestr:
					current_datetime = datetime.datetime.strptime(timestr, "%Y-%m-%dT%H:%M:%S.%fZ") 
			
			country_elems = table_row.cssselect("span.dfx-economicCalendarRow__country")
			if country_elems:
				current_country = country_elems[0].text
			
			current_country = country_merge(current_country)
			
			if not current_country:  #check!
				continue
			
			impact_elem = table_row.cssselect("span.dfx-economicCalendarRow__importance")
			impact = self.impacts.get(impact_elem[0].text.lower()) if impact_elem else None
			
			description_elem = table_row.cssselect("div.dfx-economicCalendarRow__title") 
			actual_elem = table_row.cssselect("div.jsdfx-economicCalendarRow__actual")
			forecast_elem = table_row.cssselect("div.jsdfx-economicCalendarRow__forecast")
			previous_elem = table_row.cssselect("div.jsdfx-economicCalendarRow__previous")
			
			description = ' '.join(description_elem[0].itertext()).strip() if description_elem else None
			
			event = {
				'the_date':current_datetime,
				'impact':impact,
				'source_ref':source_ref,
				'country':current_country, 
				'currency':ccm.country_currency_map.get(current_country.lower(),'?'),
				'description':description,
				'actual':self.process_value_elem(actual_elem),
				'previous':self.process_value_elem(previous_elem),
				'consensus':None,
				'forecast':self.process_value_elem(forecast_elem)
			}
			
			
			#print(event)
			#pdb.set_trace()
			
			calendar_events.append(event)
			
		return calendar_events
		
	

class DailyFXMonthly(CalendarReader):
	
	url = 'https://www.dailyfx.com/economic-calendar'
	

	@overrides(CalendarReader)
	def get_events(self,month):
		
		n_days = calendar.monthrange(month.year,month.month)[1]
		days = [datetime.datetime(month.year, month.month, day) for day in range(1, n_days+1)]
		
		calendar_events = []
		
		for day in tqdm(days):
			
			if day > datetime.datetime.now() + datetime.timedelta(days=10):
				continue #skip later dates since they don't exist yet for dailyfx
			
			scraper = DailyFXEconomicCalendarDay(self.url + '#' + day.strftime("%Y-%m-%d"))
			events = scraper.scrape()
			if not events:
				time.sleep(0.5 + random.random()) #dont spam them
			calendar_events.extend(events)
		
		
		return calendar_events


#https://www.fxempire.com/tools/economic-calendar
class FXEmpire(CalendarReader, XPathNavigator):
	
	url = 'https://www.fxempire.com/tools/economic-calendar'
	
	
	impacts = {'low':1,'medium':2,'high':3}
	
	def __init__(self,selenium_handler):
		super().__init__(selenium_handler,self.url)	
		self.setup()
	
	def setup(self):
		press_ok = self.get_element([{'tag':'button','id':'onetrust-accept-btn-handler'}])
		#time.sleep(1)
		press_ok.click() 
		
		#press_cancel = self.browser.find_element(By.XPATH,"//button[@id='onesignal-slidedown-allow-button']")
		
		
	def	goto_month(self,month):
	
		dropdown = self.get_element([{'tag':'div','data-cy':'economic-calendar-date-dropdown'}])  #".//div[@data-cy='economic-calendar-date-dropdown']"
		dropdown.click()
		#wait
		time.sleep(0.1)
		dropdown_buttons = self.get_multiple_elements([{'tag':'span','data-cy':'dropdown-time-frame'}])  #".//span[@data-cy='dropdown-time-frame']"
		for ddb in dropdown_buttons:
			if ddb.text.lower().strip() == 'custom range':
				ddb.click()
		
		#pdb.set_trace()
		#print('find date fields')
		month_pick = self.get_element([{'tag':'span','class':'rdrMonthPicker'}])
		month_pick.click()
		
		month_to_click = self.get_element([{'tag':'span','class':'rdrMonthPicker'},{'tag':'option','value':str(month.month-1)}])
		month_to_click.click()
		
		year_pick = self.get_element([{'tag':'span','class':'rdrYearPicker'}])
		year_pick.click()
		
		year_to_click = self.get_element([{'tag':'span','class':'rdrYearPicker'},{'tag':'option','value':str(month.year)}])
		year_to_click.click()		
		
		self.get_element([{'tag':'button','subclass1':'rdrDayStartOfMonth'}]).click()
		self.get_element([{'tag':'button','subclass1':'rdrDayEndOfMonth'}]).click()
		
		self.get_element([{'tag':'span','data-cy':'date-range-apply-button'}]).click()
		#pdb.set_trace()
		
		self.scroll_lazy_load()
		time.sleep(1) 
		
		
		

	@overrides(CalendarReader)
	def get_events(self,month):
		self.goto_month(month)
		
		##now perform scrape 
		html = lxml.etree.HTML(self.browser.page_source)
		day_tables = html.xpath("//table[@data-cy='main-economic-calendar-table']")
		
		source_ref = calendar_ref(self.url)
		
		calendar_events = []
		#pdb.set_trace()
		for day_table in day_tables:
			the_date = None
			try:
				the_date_str = day_table.cssselect("table thead")[0].attrib['id']
				the_date_str = re.sub('\d+(st|nd|rd|th)', lambda m: m.group()[:-2].zfill(2), the_date_str)
				the_date = datetime.datetime.strptime(the_date_str, "%A, %B %d %Y")
			except Exception as e:
				log.warning(f"Unable to parse date - {str(e)}")
				the_date = None
			if not the_date:
				continue
			event_containers = day_table.cssselect("tbody tr.Tr-svvh77-0")
			for event_container in event_containers:
				tds = event_container.cssselect("td")
				if len(tds) < 7:
					continue
				time_comp = (0,0)
				timebits = ''.join(tds[0].itertext()).split(':')
				if len(timebits) >= 2:
					time_comp = (safe_int(timebits[0]),safe_int(timebits[1]))
				country_bits = tds[1].xpath(".//div/span/div/@class")
				country = country_bits[0].replace('-',' ').title() if country_bits else None				
				country = country_merge(country)
				
				if not country:
					continue 
				
				currency_bits = tds[1].xpath(".//div/span/text()")
				currency = currency_bits[0] if currency_bits else None
				if not currency:
					currency = ccm.country_currency_map.get(country.lower())
		
				description = ' '.join(tds[2].itertext())
				#pdb.set_trace()
				impact_str = tds[3].xpath("./div/span/span/text()")[0].lower().strip()
				impact = self.impacts.get(impact_str)
				
				event = {
					'the_date':datetime.datetime(the_date.year,the_date.month,the_date.day,time_comp[0],time_comp[1]),
					'impact':impact,
					'source_ref':source_ref,
					'country':country, 
					'currency':currency,
					'description':description,
					'actual':' '.join(tds[4].itertext()),
					'previous':' '.join(tds[6].itertext()),
					'consensus':' '.join(tds[5].itertext()),
					'forecast':None
				}
				
				calendar_events.append(event)
		
		return calendar_events
		

class FXCO(CalendarReader, Crawler):
	
	url = 'https://www.fx.co/en/forex-calendar/'
	
	def __init__(self,selenium_handler):
		super().__init__(selenium_handler,None)
	
	def goto_month(self,month):
		month_start = datetime.datetime(month.year,month.month,1)
		month_end_day = calendar.monthrange(month.year,month.month)[1]
		month_end = datetime.datetime(month.year,month.month,month_end_day)
		
		link = self.url + month_start.strftime("%Y-%m-%d") + '/' + month_end.strftime("%Y-%m-%d")
		
		self.get(link)
		self.scroll_lazy_load(20)
		
			
	@overrides(Crawler)
	def crawl(self):
		calendar_items = [] 
		
		html = lxml.etree.HTML(self.browser.page_source)
		
		source_ref = calendar_ref(self.url)
		
		#pdb.set_trace()
		calendar_rows = html.xpath("//div[@class='block-content']/div")
		the_date = None
		for calendar_row in calendar_rows:
			
			if calendar_row.attrib.get('class') == 'block-forex-calendar__date-row':
				the_date = datetime.datetime.strptime(calendar_row.text,"%A, %d %B, %Y")
				continue
			
			if not the_date:
				continue
			
			bits = calendar_row.xpath("./div/div/text()") #time, actual, forecast, previous
			desc_l = calendar_row.xpath(".//div[@class='block-forex-calendar__title']/div/text()") #description
			country_l = calendar_row.xpath(".//div[@class='block-forex-calendar__title']/div/img/@src")
			
			country = None
			description = None
			impact = 0
			
			impact_elem = calendar_row.xpath('./div/div/@class')
			if impact_elem:
				if 'low' in impact_elem[0]:
					impact = 1
				if 'medium' in impact_elem[0]:
					impact = 2
				if 'high' in impact_elem[0]:
					impact = 3
			
			if country_l:
				country = country_l[0].split('/')[-1].replace('.svg','').replace('-',' ').title()
				country = country_merge(country)
			
			if desc_l:
				description = desc_l[0].strip()
				
			if not country or not description:
				continue
			
			time_comp = (0,0)
			(actual,forecast,previous) = (None,None,None)
			
			if len(bits) >= 4:
				[timestr,actual,forecast,previous] = bits[:4]
				timebits = timestr.split(':')
				if len(timebits) >= 2:
					time_comp = (safe_int(timebits[0]),safe_int(timebits[1]))
			event = {
				'the_date':datetime.datetime(the_date.year,the_date.month,the_date.day,time_comp[0],time_comp[1]),
				'impact':impact,
				'source_ref':source_ref,
				'country':country, 
				'currency':ccm.country_currency_map.get(country.lower(),'?'),
				'description':description,
				'actual':actual,
				'previous':previous,
				'consensus':None,
				'forecast':forecast
			}
			calendar_items.append(event)
		
		return calendar_items
	
	@overrides(CalendarReader)
	def get_events(self,month):
		self.goto_month(month)
		return self.crawl()
		


#class FXStreet
#class ForexFactory
	
	
calendars = {
	'te':TradingEconomics,
	'dfx':DailyFXMonthly,
	'fxempire':FXEmpire,
	'fxco':FXCO,
	#any other?
}

class CalendarWorker(ProcessWorker):
	
	@overrides(ProcessWorker)
	def perform_task(self, calendar_task):
		result = {'category':'NONE'} 
		
		calendar_key, month = calendar_task
		
		try:
			calendarreader = calendars.get(calendar_key)
			if calendarreader.use_selenium:
				with SeleniumHandler(hidden=True) as sh:
					calendarreaderobj = calendarreader(selenium_handler=sh)
					result = calendarreaderobj.get_events(month) 
			else:
				calendarreaderobj = calendarreader()
				result = calendarreaderobj.get_events(month) 
					
					
		except Exception as e:
			log.warning(f"Task {calendar_task} failed with {e}")
		
		return result
		

class CalendarCollector:

	n_workers = min(len(calendars.keys()),5) #max 5
	sql_file = 'queries/economic_calendar_upsert.sql'
	sql_row = "(%(the_date)s,%(source_ref)s,%(impact)s,%(country)s,%(currency)s,%(description)s,%(actual)s,%(previous)s,%(consensus)s,%(forecast)s)"
	
	db_chunk_size = 100
	progress_bar = True
	
	def get_events(self,date_from,date_to):
	
		months = pd.period_range(start=date_from,end=date_to,freq='M')
		months = [month.to_timestamp().to_pydatetime() for month in months]
		#pdb.set_trace()
		
		calendar_tasks = [(calendar_key,month) for calendar_key in calendars.keys() for month in months]
		
		process_pool = ProcessPool([CalendarWorker(i) for i in range(self.n_workers)])
		eventss = process_pool.perform(calendar_tasks)
		
		events = [event for events in eventss for event in events]
		
		return events

	
	def put_to_database(self,events):
		
		sql_query = None
		
		with open(self.sql_file,'r') as f:
			sql_query = f.read()
			
		with Database(cache=False,commit=True) as cursor:
		
			event_chunks = [events[i:i+self.db_chunk_size] for i in range(0,len(events),self.db_chunk_size)]
			event_chunks = tqdm(event_chunks) if self.progress_bar else event_chunks
			
			for event_chunk in event_chunks:
				sql_rows = [cursor.mogrify(self.sql_row,event).decode() for event in event_chunk]
				cursor.execute(sql_query,{'calendar_events':Inject(','.join(sql_rows))})
			























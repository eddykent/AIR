

import datetime
import re

import json 
import traceback
import time

import lxml
from bs4 import BeautifulSoup

import pdb 

#snapshots are just dicts so dump them as json into the database with a timestamp
from psycopg2.extras import Json
from psycopg2.extensions import register_adapter


register_adapter(dict, Json) #for dumping into the db 

import logging 
log = logging.getLogger(__name__)

##class for reading websites and getting the current state (eg forex client sentiment, common trades in forexfactory etc)
##data could  be logged in the database - use journalling for this 
#
#1) grab all useful data from websites (multi processing)
#2) use for influencing trades if needed (use in snapshot filters) 
#3) log to database for backtests later to gauge usefulness of the data in journal  
from air.configuration import Configuration
from air.data.tools.cursor import Database

from air.web.scraper import Scraper
from air.web.crawler import Crawler, By, SeleniumHandler
from air.data.tools.processpool import ProcessPool, ProcessWorker

from air.utils import overrides

categories = ['client_sentiment','currency_strength','signals','analysis','macroscopic'] #others?

#tradingview
#weather

#add utility categories
categories += ['NONE','ERROR']

#koyfin, weather, forexfactory, client_sentiment, currency_strength, 


#def extract_text(elems):
#	if 

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


class SnapshotScraper(Scraper): 
	
	URL = '' #now we have a constant URL 
	category = None #we also have to give some idea of what we are getting 
	
	@overrides(Scraper)
	def __init__(self, **kwargs): #proxy?  
		assert self.URL, 'URL needs to be set!'
		assert self.category, 'category needs to be set!'
		super().__init__(**kwargs, source=self.URL) #wipe source
	
	def _result_base(self):
		return {'category':self.category,'url':self.URL,'data':None}

class SnapshotCrawler(Crawler):
	
	URL = '' #now we have a constant URL
	category = None #we also have to give some idea of what we are getting 
	
	@overrides(Crawler)
	def __init__(self, selenium_handler, **kwargs):
		assert self.URL, 'URL needs to be set!'
		assert self.category, 'category needs to be set!'
		super().__init__(selenium_handler,**kwargs, source=self.URL) #wipe source
	
	def _result_base(self):
		return {'category':self.category,'url':self.URL,'data':None}

#create specific scrapers for each website we want to scrape now 

####CLIENT SENTIMENT
class ForexClientSentiment(SnapshotScraper):	
	
	URL = 'https://forexclientsentiment.com/client-sentiment'
	category = 'client_sentiment'	
	
	@staticmethod
	def __decode_number(num_str):
		num_str = num_str.replace('%','')
		return float(num_str)
	
	@staticmethod
	def _safe_int(int_str):
		try:
			return int(int_str)
		except:
			return 0 #log?
	
	def scrape(self):
		self.render()
		
		result = self._result_base()
		
		sentiment_boxes = self.html.xpath("//a[@class='sentiment']")
		client_sentiments = [] 
		for sb in sentiment_boxes:
			instrument_box = sb.xpath('//h3')
			instrument = instrument_box[0].text if len(instrument_box) else None
			
			long_box = sb.xpath(".//*[@class='sentiment--values--numbers--long']") 
			short_box = sb.xpath(".//*[@class='sentiment--values--numbers--short']")
			if not (long_box and short_box):
				#warning?
				continue
			
			long_val = long_box[0].text
			short_val = short_box[0].text
			
			longf = self.__decode_number(long_val)
			shortf = self.__decode_number(short_val)
			
			bias_level = 0
			bias_box = sb.xpath(".//div[contains(@class,'contrarian-indicator')]")
			if bias_box:
				classes = list(bias_box[0].attrs['class'])
				this_class = [c for c in classes if c.startswith('indicator__down__') or c.startswith('indicator__up__')]
				if this_class:
					this_class = this_class[0]
					bias_direction = 1 if 'up' in this_class else -1 if 'down' in this_class else 0
					bias_magnitude = self._safe_int(this_class[-1:])
					bias_level = bias_magnitude * bias_direction
			
			client_sentiments.append({'instrument':instrument,'sentiment':{'long':{'percentage':longf}, 'short':{'percentage':shortf}, 'bias':bias_level}})
		
		result['data'] = client_sentiments
		return result


class MyFXBook(SnapshotScraper):
	
	URL = 'https://www.myfxbook.com/community/outlook'
	category = 'client_sentiment'
	
	def scrape(self):
		#return self.from_outlook_symbol_rows()
		return self.from_popovers()
		
	def from_outlook_symbol_rows(self): #remove? -keep for backup? 
		
		result = self._result_base()
		client_sentiments = []
		
		outlook_symbol_rows =  self.html.xpath("//tr[@class='outlook-symbol-row']")
		
		for tr in outlook_symbol_rows:
			
			instrument = tr.attrs['symbolname'] #fx has no slashes here :/ (eg EURCAD)
			result_row = {} 
			progress_bars = tr.xpath(".//div[contains(@class,'progress-bar')]")
			for progress_bar in progress_bars:
				#pdb.set_trace()
				class_tup = progress_bar.attrs['class']
				style_str = progress_bar.attrs['style']
				percentage = safe_int(style_str)

				if 'progress-bar-danger' in class_tup:
					result_row['short'] = {'percentage':percentage}
				elif 'progress-bar-success' in class_tup:
					result_row['long'] = {'percentage':percentage}
				else:
					result_row['popularity'] = percentage
			client_sentiments.append({'instrument':instrument,'sentiment':result_row})
		result['data'] = client_sentiments
		return result
	
	def from_popovers(self):
	
		result = self._result_base()
		client_sentiments = []
		
		outlook_symbol_rows =  self.html.xpath("//tr[@class='outlook-symbol-row']")
		
		for tr in outlook_symbol_rows:
			
			instrument = tr.attrs['symbolname']
			result_row = {}
			
			popover = tr.xpath(".//div[contains(@id,'outlookSymbolPopover')]")
			popover = popover[0] #if popover else None #then skip
			
			popularity = popover.xpath(".//div[contains(@class,'text-center')]")
			result_row['popularity'] = int(popularity[0].text[:3].replace('%','')) #incase of 100%!
			
			longshorts = popover.xpath(".//table/tbody/tr")
			for ls in longshorts:
				#pdb.set_trace()
				rowbits = [t for t in ls.text.split('\n') if t != instrument]
				if len(rowbits) >= 4:	
					pc = int(rowbits[1].replace('%',''))
					volume = safe_float(rowbits[2])
					positions = safe_int(rowbits[3])
					
					rowval = {
						'percentage':pc,
						'volume':volume,
						'positions':positions
					}
					
					rowvalkey = rowbits[0].strip().lower()
					if rowvalkey in ['long','short']:
						result_row[rowvalkey] = rowval
			client_sentiments.append({'instrument':instrument,'sentiment':result_row})
		result['data'] = client_sentiments
		return result 


class DailyFX(SnapshotScraper):
	
	URL = 'https://www.dailyfx.com/sentiment-report'
	category = 'client_sentiment'
	
	biases = { #change this as desired 
		'BULLISH':2,
		'BEARISH':-2,
		'MIXED':0
	}
	
	def scrape(self):
		
		client_sentiments = {}
		result = self._result_base()
		
		table_rows =  self.html.xpath("//article/table/tbody/tr")
		for tr in table_rows:
			#instrument, bias, long, short, change long daily, change long weekly, change short daily, change short weekly, volume change daily, volume change weekly 
			rowbits = tr.text.split('\n')
			
			if len(rowbits) >= 10:
				[instrument, bias_str, longpc, shortpc, clongd, clongw, cshortd, cshortw, ovd, ovw] = rowbits[:10] #unpack 
				client_sentiments[instrument] = {
					'short':{
						'percent':safe_float(shortpc),
						'percent_change_daily':safe_float(cshortd),
						'percent_change_weekly':safe_float(cshortw)
					},
					'long':{
						'percent':safe_float(longpc),
						'percent_change_daily':safe_float(clongd),
						'percent_change_weekly':safe_float(clongw)
					},
					'open_interest':{
						'percent_change_daily':safe_float(ovd),
						'percent_change_weekly':safe_float(ovw)
					},
					'bias':self.biases.get(bias_str.strip().upper())
				}
				
		result['data'] = [{'instrument':instrument,'sentiment':sentiment} for (instrument,sentiment) in client_sentiments.items()]
		return result				
		
class Dukascopy(SnapshotCrawler):
	
	URL = 'https://www.dukascopy.com/swiss/english/marketwatch/sentiment/'
	category = 'client_sentiment'
	
	#change when their site changes
	row_identifier = 'F-qb-Ab'
	instrument_select_identifier = 'F-qb-Qb-c'
	iframe_identifier = 'realtime_sentiment_index'
	
	@staticmethod
	def process_text_lines(text_lines):		
		sentiments = {}
		for text_line in text_lines:
			linebits = text_line.split('\n')
			if len(linebits) >= 3:
				instrument = linebits[0]
				longpc = safe_float(linebits[1])
				shortpc = safe_float(linebits[-1])
				sentiments[instrument] = {
					'sentiment':{
						'long':{'percentage':longpc},
						'short':{'percentage':shortpc}
					}
				}
		
		return sentiments
		
		
	def crawl(self):
		
		result = self._result_base()
		
		the_iframe = self.browser.find_element(By.XPATH,"//iframe[contains(@src,'"+self.iframe_identifier+"')]")
		self.browser.switch_to.frame(the_iframe)
		select_buttons = self.browser.find_elements(By.XPATH,"//*[contains(@class,'"+self.instrument_select_identifier+"')]")	
		instrument_button = [s for s in select_buttons if s.text == 'INSTRUMENTS'][0]
		currencies_button = [s for s in select_buttons if s.text == 'CURRENCIES'][0]
		
		instrument_button.click() #go to instruments first  --might need to do a wait or something
		
		all_pairs_rows = self.browser.find_elements(By.XPATH,"//*[contains(@class,'"+self.row_identifier+"')]") 
		pairs = self.process_text_lines([pr.text for pr in all_pairs_rows])
		
		currencies_button.click() #now get currencies 
		
		all_currencies_rows = self.browser.find_elements(By.XPATH,"//*[contains(@class,'"+self.row_identifier+"')]")
		currencies = self.process_text_lines([cr.text for cr in all_currencies_rows])
		
		all_data = {**pairs,**currencies}
		
		result['data'] = [{'instrument':instrument, 'sentiment':sentiment} for (instrument, sentiment) in all_data.items()]
		return result


class FXCOSentiment(SnapshotCrawler):
	
	URL = 'https://www.fx.co/en'
	category = 'currency_strength'
	
	def crawl(self):
		
		result = self._result_base()
		currency_strengths = []
		
		
		time.sleep(5)# wait for all widgets to load
		#self.get_elemen()
		
		html = lxml.etree.HTML(self.browser.page_source)
		
		position_boxes = html.cssselect("a.widget-trader-position__cells")
		for position_box in position_boxes:
			instrument = position_box.cssselect("div.widget-trader-position__valute-name")[0].text.strip()
			prog_green_str = position_box.cssselect("div.widget-trader-position__progressbar_green")[0].attrib.get('title')
			prog_red_str = position_box.cssselect("div.widget-trader-position__progressbar_red")[0].attrib.get('title')
			
			currency_strengths.append({
				'instrument':instrument,
				'sentiment':{
					'long':safe_float(prog_green_str),
					'short':safe_float(prog_red_str)
				}
			})
		
		result['data'] = currency_strengths
		return result
		
		


####CURRENCY STRENGTH
class CurrencyStrengthMeter(SnapshotScraper):
	
	URL = 'https://currencystrengthmeter.org/'
	category = 'currency_strength'
	
	
	def scrape(self):
		
		result = self._result_base()
		currency_strengths = []
		
		str_containers = self.html.xpath("//div[@class='str-container']")
		for container in str_containers:
			currency = container.xpath(".//p[@class='title']/text()")
			currency = currency[0].strip() if len(currency) else container.text().strip()
			the_level = container.xpath(".//div[@class='bar-cont']/div[@class='level']")
			strength = safe_float(the_level[0].attrs['style'])
			currency_strengths.append({'currency':currency, 'strength': {'all':{'percentage':strength}}})
			
		result['data'] = currency_strengths
		return result


class LiveCharts(SnapshotScraper):

	URL = 'https://www.livecharts.co.uk/currency-strength.php'
	category = 'currency_strength'
	
	def scrape(self):
		
		result = self._result_base()
		currency_strengths = []

		soup = BeautifulSoup(self.html.html, 'html.parser') #use beautiful soup for their bs duplicate id issues
		#containers = self.html.xpath("//div[@id='rate-outercontainer']/")
		#for xx in containers:
		for container in soup.find_all('div',id='rate-outercontainer'):
			currency = container.find('div',id='map-innercontainer-symbol').text
			weakness = len(container.find_all('div',style='background-image:none')) #get all non-displaying bars
			strength = int(((6 - weakness) / 6.0) * 100 )
			
			currency_strengths.append({'currency':currency,'strength':{'all': { 'percentage' :strength, 'stack':(6 - weakness)}}})
			
		result['data'] = currency_strengths
		return result

#abandoned :( - they have a blocker that stops page from finishing to load
#class BabyPips(SnapshotCrawler):   
#	
#	URL = 'https://marketmilk.babypips.com/currency-strength'
#	category = 'currency_strength'
#	
#	def startup(self):
#		pdb.set_trace()
#		button_class = "mm-NDx6rCywGZF5G9BR mm-wFChdwU6VSAn6M6Y mm-ekFv2pOD93xgmxUi mm-gVTNEDCmRsLIIu4H"
#		btns = self.browser.find_elements(By.XPATH,f"//div[contains(@class,'{button_class}')]")
#		
#	
#	def change_setting(self,period):
#		dropdownbtns = self.browser.find_elements(By.XPATH,"//div[contains(@class,'mm-grrDiU5N+3gLiXkI')]")
#		
#	
#	def crawl(self):
#		result = self._result_base()
#		currency_strengths = {}
#		
#		self.startup()
#		self.change_setting('30m')

class FXBlue(SnapshotCrawler):
	
	URL = 'https://www.fxblue.com/market-data/currency-strength'
	category = 'currency_strength'
	
	def crawl(self):
		result = self._result_base()
		currency_strengths = []
		
		time.sleep(2)
		soup = BeautifulSoup(self.browser.page_source,'html.parser')
		
		titles = soup.select("#HeadlineContainer .HeadlineBlockContainer .HeadlineTitle")
		values = soup.select("#HeadlineContainer .HeadlineBlockContainer .HeadlineValue")
		
		for (currency,value) in zip([t.text for t in titles],[safe_float(v.text) for v in values]):
			currency_strengths.append({'currency': currency,'strength':{'all': {'value':value}}})
		
		result['data'] = currency_strengths
		return result

#https://www.actionforex.com/markets/currency-heat-map/


###COPY TRADING 
class ForexFactoryUsers(Crawler):	#class for getting the user data
	
	def get_profile(self):
		
		profile = {} 
		
		member_info_cols = self.browser.find_elements(By.XPATH,".//*[contains(@class,'memberinfo__column')]")
		
		for mic in member_info_cols:
			bits = mic.text.split('\n')
			
			if 'status' in bits[0].lower():
				profile['status'] = bits[1].strip()
			
			if 'joined forex factory' in bits[0].lower():
				profile['member_since'] = bits[1].strip()
			
			if 'trading from' in bits[0].lower():
				profile['country'] = bits[1].replace('(map)','').strip()
			
			if 'trading involvement' in bits[0].lower():
				profile['involvement'] = bits[1].strip()
			
			if 'trading since' in bits[0].lower():
				profile['trading_since'] = bits[1].strip()
		
		return profile
		
	def get_acounts(self):
		
		accounts = self.browser.find_elements(By.XPATH,".//div[contains(@id,'explorer_shell') and contains(@class,'trade_explorer')]")
		
		account_details = []
		
		for account in accounts:
			
			live_trades = [] 
			pending_orders = []
			recent_trades = []
			performance = {} 
			
			xpath_quest_for_live = ".//ul[contains(@class,'explorer_info__trader') and contains(@class,'right')]/li"
			type = 'Live' if 'live' in [li.text.lower().strip() for li in account.find_elements(By.XPATH,xpath_quest_for_live)] else 'Demo'
			
			#performances = all time frames?
		
			performance_tables = account.find_elements(By.XPATH,".//div[@class='explorer_overview__performance']//table")
			performance_table = performance_tables[0] if len(performance_tables) >= 2 else None ##changes with screen size :/ 
			if performance_table:
				
				table_bits = [[td.text.strip() for td in tr.find_elements(By.XPATH,".//td")] for tr in performance_table.find_elements(By.XPATH,".//tr")] 
				today_row = [td for td in table_bits[0] if td]
				all_time_row = [td for td in table_bits[-1] if td]
				
				if len(today_row) > 2 and today_row[1]:
					performance['today'] = safe_float(today_row[1])
				
				if len(all_time_row) > 2 and all_time_row[1]:
					performance['all_time'] = safe_float(all_time_row[1])
							
			
			trade_tables = account.find_elements(By.XPATH,".//div[@class='explorer_overview__trades']//table[contains(@class,'--processed')]")
			for table in trade_tables:
				
				table_start_text = table.text[:50].lower()
				table_type = None
				if 'latest closed trades' in table_start_text:
					table_type = 'recent_trades'
				if 'pending orders' in table_start_text:
					table_type = 'pending_orders'
				if 'open trades' in table_start_text:
					table_type = 'live_trades'
				
				
				table_bits = [[td.text.strip() for td in tr.find_elements(By.XPATH,".//td")] for tr in table.find_elements(By.XPATH,".//tr")]
				
				these_trades = []
				for trade_row in table_bits:
					trade_row_bits = [td for td in trade_row if td]
					
					if not trade_row_bits:
						continue
						
					first3  = trade_row_bits[0].split(' ')
								
					if len(first3) < 3:
						continue 
						
					[instrument,direction,open] = first3[:3]
					open_val = safe_float(open)
					
					trade = {
						'instrument':instrument,
						'direction':direction.upper(),
						'open_price':open_val
					}
					
					if table_type == 'recent_trades':
						trade['close_price'] = safe_float(trade_row_bits[1])
						trade['time_ago'] = trade_row_bits[2] 
						recent_trades.append(trade)
					
					if table_type == 'pending_orders':
						pending_orders.append(trade)
					
					if table_type == 'live_trades':
						trade['current_price'] = safe_float(trade_row_bits[1])
						tpslprice = trade_row_bits[-1].split(' ')[0]
						tpsl = safe_float(tpslprice) if tpslprice and tpslprice.lower() != 'na' else None
						if tpsl is not None:
							trade['tpsl'] = tpsl 
						live_trades.append(trade)
			
			
				
			account_detail = {
				'live_trades':live_trades, 
				'recent_trades':recent_trades, 
				'pending_orders':pending_orders,
				'performance': performance
			} 
			account_details.append(account_detail)
				
			
		return {'accounts':account_details}
		
	
	def crawl(self):
		#print('get relevant user details and their open (and closed?) trades')
		
		#first, get status and when joined ff  --profile
		profile = self.get_profile()
		accounts = self.get_acounts() 
		
		return {**profile, **accounts}

class ForexFactory(SnapshotCrawler):
	
	URL = 'https://www.forexfactory.com/trades'
	category = 'copy_trading'
	
	
	def process_trades(self,trades):
		return_data = [] 
		for trade in trades:
			#pdb.set_trace()
			bits = [t for t in trade.split() if t not in ['<']] #remove bits here 
			if len(bits) >= 10:
				[instrument,direction,price,action1,action2,_,time_val,time_mag,ago,user] = bits[:10]
				
				try:	
					recent_trade = {
						'instrument':instrument,
						'direction':direction,
						'price':price,
						'action':action1 + ' ' + action2,
						'ago':safe_int(time_val),
						'ago_note':time_mag,
						'user':user
					}
					return_data.append(recent_trade)
				except Exception as e:
					#pdb.set_trace()
					print('err occ')
		return return_data
			
	def process_positions(self,positions):
		return_data = {} 
		for position in positions:
			bits = position.split('\n')
			if len(bits) > 3:
				[instrument, long_str, short_str] = bits[:3]
				long_bits = long_str.split()
				short_bits = short_str.split()
				
				#pdb.set_trace()
				long_percent = safe_float(long_bits[0])
				long_traders = safe_int(long_bits[1])
				short_percent = safe_float(short_bits[2])
				short_traders = safe_int(short_bits[0])
				
				return_data[instrument] = {
					'long':{
						'percent':long_percent,
						'traders':long_traders
					},
					'short':{
						'percent':short_percent,
						'traders':short_traders
					}
				}
		return return_data
		
	def process_users_trades(self,top_performers):
		#this is the hard bit.. 
		return_list = [] 
		for top_performer in top_performers:
			ranks = top_performer.find_elements(By.XPATH,".//td[contains(@class,'rank')]")
			preturns = top_performer.find_elements(By.XPATH,".//td[contains(@class,'return')]")
			usernames = top_performer.find_elements(By.XPATH,".//td[contains(@class,'trader')]")
			links = top_performer.find_elements(By.XPATH,".//td[contains(@class,'trader')]//a")
			
			trader_info = {
				'rank':safe_int(ranks[0].text),
				'return':safe_float(preturns[0].text),
				'user':usernames[0].text,
				'link':links[0].get_attribute('href')
			} 
			return_list.append(trader_info)		
		
		#consider multithread
		for trader_info in return_list:
			link = trader_info['link'] 
			
			hidden = self.selenium_handler.hiddenn  #why not use same selenium_handler?
			with SeleniumHandler(hidden=hidden) as sh:  
				ffum = ForexFactoryUsers(sh,link)
				trader_info['details'] = ffum.crawl()	
			
		return return_list
	
	def crawl(self):
		result = self._result_base()
		#html = lxml.etree.HTML(self.browser.page_source)
		ctd = {}
		
		#html.xpath(".//")
		trade_rows = self.browser.find_elements(By.XPATH,"//tr[contains(@class,'trades_activity__row')]")
		ctd['recent_trades'] = self.process_trades([e.text for e in trade_rows])
		
		positions_rows =  self.browser.find_elements(By.XPATH,"//table[@class='trades_position']")
		ctd['positions'] = self.process_positions([e.text for e in positions_rows])
		
		top_performer_rows = self.browser.find_elements(By.XPATH,"//tr[contains(@class,'trades_leaderboard__row')]")
		ctd['traders'] = self.process_users_trades(top_performer_rows)
		
		result['data'] = ctd
		return result
	




##etoro copy trading facilities
class EToroUserStats(Crawler):
	
	def get_performance_monthly(self,html):
		performancebits = html.cssselect("div.performance-chart-info")
		performance_monthly = [] 
		for pbr in performance_bits[:2]:
			month_values = list(mvs.strip() for mvs in pbr.itertext())
			month_values.reverse()
			year = int(month_values[0])
			months = list(range(1,13))
			for m,mv in zip(month_values[1:-1], months):
				if not mv:
					continue
				the_date = datetime.datetime(year,m,1)
				value = safe_float(mv)
				performance_monthly.append({'month':the_date,'return':value})
		return performance_monthly
			
	
	def get_trade_stats(self,html):
		trading_summary = html.cssselect("div.performance-trads-details-list")
		n_trades = html.cssselect("div.performance-num")
		avg_profit = html.xpath("//span[@automation-id='cd-user-stats-performance-trading-average-profit']")
		avg_loss = html.xpath("//span[@automation-id='cd-user-stats-performance-trading-average-loss']")
		
		stats = {} 
		if n_trades:
			stats['n_trades'] = safe_int(n_trades[0].text)
		if avg_profit:
			stats['average_profit'] = safe_float(''.join(avg_profit[0].itertext()))
		if avg_loss:
			stats['average_loss'] = safe_float(''.join(avg_loss[0].itertext()))
		
		if trading_summary:
			summaries = []
			markets = trading_summary[0].cssselect('div.details')
			for market in markets:
				[name, valstr] = list(market.itertext())[:2]
				summaries.append({'name':name.lower(),'percent': safe_float(valstr)})
			stats['markets'] = summaries
		return stats
				
	def get_frequent_traded(self,html):
		frequently_traded = [] 
		trade_rows = html.cssselect(".performance-trads-frequently .top-trade-row")
		for trade_row in trade_rows:
			instrument = trade_row.xpath(".//span[@class='user-nickname']/text()")
			instrument = instrument[0] if instrument else None
			
			if not instrument:
				continue
			
			trade_stat = {'instrument':instrument} 
			percent_traded = trade_row.xpath(".//div[@class='top-trade-topic']/text()")
			trade_stat['percent_traded'] = safe_float(percent_traded[0]) if percent_traded else None
			
			avg_profit = trade_row.xpath(".//span[@class='positive']/text()")
			trade_stat['average_profit'] = safe_float(avg_profit[0]) if avg_profit else None
			
			avg_loss = trade_row.xpath(".//span[@class='negative']/text()")
			trade_stat['average_loss'] = safe_float(avg_loss[0]) if avg_loss else None
			
			profitable = trade_row.xpath(".//span[@class='top-trade-profit-procent']/text()")
			trade_stat['profitable'] = safe_float(profitable[0]) if profitable else None
			
			frequently_traded.append(trade_stat)
		
		return frequent_traded

	
	def get_additional_stats(self,html):
		
		additionals = html.xpath("//*[@class='stats-user-additiona-wrapp']//div[@class='top-trade-colum']//span[@class='top-trade-profit-procent']/text()")
		additional = {}
		if len(additionals) >= 4:
			tpw,hts,ass,pws = additionals[:4]
			additional['trades_per_week'] = safe_float(tpw)
			additional['profitable_weeks'] = safe_float(pws)
			additional['average_holding_time'] = hts.lower() #consider parsing
			additional['trading_since'] = datetime.datetime.strptime(ass,"%m/%d/%y")
			
		return additional
		
	
	def crawl(self):	
		time.sleep(5)
		html = lxml.etree.HTML(self.browser.page_source)	
		pdb.set_trace()
		stats = {}
		print('get user details')
		
		stats['performance_monthly'] = self.get_performance_monthly(html)
		stats['trading_profile'] = self.get_trade_stats(html)
		stats['frequent_traded'] = self.get_frequent_traded(html)
		stats['averages'] = self.get_additional_stats(html)
		return stats
		
		
#grab trades 
#class EToroUserPortfolio(SnapshotCrawler):


class EToro(SnapshotCrawler):
	
	URL = 'https://www.etoro.com/discover/people/results?copyblock=false&period=LastTwoYears&hasavatar=true&verified=true&isfund=false&tradesmin=5&dailyddmin=-5&weeklyddmin=-15&profitablemonthspctmin=50&lastactivitymax=30&sort=-copiers&page=1&pagesize=20&instrumentid=-1&gainmin=10&gainmax=50'
	category = 'copy_trading'
	
	def crawl(self):
		
		time.sleep(10)
		html = lxml.etree.HTML(self.browser.page_source)
	
		result = self._result_base()
		table_rows = html.xpath(".//div[contains(@class,'et-table-body') and @automation-id='table-list']/div[contains(@class,'et-table-row')]")
		
		traders = [] 
		for table_row in table_rows:
			#pdb.set_trace() 
			username_l = table_row.xpath(".//div[@class='user-nickname']/text()")
			link_l = table_row.xpath(".//a[contains(@class,'et-table-user-info')]/@href")
			country_l = table_row.xpath(".//span[@automation-id='discover-people-results-list-item-country']/text()")
			body_items = table_row.xpath(".//div[@class='et-table-body-slot']/div[contains(@class,'et-table-cell')]//span/text()")
			risk_score_l = table_row.xpath(".//div[@class='et-table-body-slot']/div[contains(@class,'et-table-cell')]//span[@automation-id='discover-people-results-list-item-risk-score']/@class")
			
			trader_details = {}
			if link_l:
				stats_link = "https://www.etoro.com" + link_l[0]
				portfolio_link = '/'.join(stats_link.split('/')[:-1]) + '/portfolio'
				trader_details['stats_link'] = stats_link
				trader_details['portfolio_link'] = portfolio_link
			trader_details['username'] = username_l[0].strip() if username_l else None
			trader_details['country'] = country_l[0].strip() if country_l else None 
			ret,copiers,wdd = (None,None,None)
			if len(body_items) >= 4:
				ret, copiers, _, wdd = body_items[:4]
				trader_details['return'] = safe_float(ret)
				trader_details['copiers'] = safe_int(copiers)
				trader_details['weekly_drawdown'] = safe_float(wdd)
			trader_details['risk_score'] = safe_int(re.sub('[^0-9]','',risk_score_l[0]))
			
			hidden = self.selenium_handler.hidden
			if 'stats_link' in trader_details:
				with SeleniumHandler(hidden=hidden) as sh:  #why not use same selenium_handler after all traders grabbed?
					etus = EToroUserStats(sh,trader_details['stats_link'])
					trader_details['statistics'] = etus.crawl()	
			
			if 'portfolio_link' in trader_details:
				with SeleniumHandler(hidden=hidden) as sh:  
					etup = EToroUserPortfolio(sh,trader_details['portfolio_link'])
					trader_details['portfolio'] = etup.crawl()	
						
			traders.append(trader_details)
			
		#get top 10 links 
		result['data'] = {'traders':traders}
		
		
		
		
		

###SIGNALS 
class FXCO(SnapshotScraper):
	
	URL = 'https://www.fx.co/en/signals/'
	category = 'signals'

	def scrape(self):
	
		self.render()
		result = self._result_base()
		signals = []
		signal_blocks = self.html.xpath("//div[@class='block-signals__item']")
		for signal_block in signal_blocks:
			
			instrument = signal_block.xpath("//span[@class='block-signals__info_id']/text()")[0]
			period = signal_block.xpath("//span[@class='block-signals__info_period']/text()")[0]
			tpstr = signal_block.xpath("//span[@class='block-signals__info_tp']/text()")[0]
			slstr = signal_block.xpath("//span[@class='block-signals__info_sl']/text()")[0]
			prstr = signal_block.xpath("//span[@class='block-signals__info_price']/text()")[0] #entry?
			
			timestampstr = signal_block.xpath("//div[@class='block-signals__date']/span/@data-timestamp")[0] 
			description = signal_block.xpath("//div[@class='block-signals__comment-link']/text()")[0].strip()
			
			the_date = datetime.datetime.utcfromtimestamp(safe_int(timestampstr))
			#jsontimestamp = the_date.strftime("%Y-%m-%dT%H:%M:%S")
			
			tpval = safe_float(tpstr)
			slval = safe_float(slstr)
			direction = 'BUY' if tpval > slval else 'SELL' if tpval < slval else 'VOID'
			
			signal = {
				'instrument':instrument,
				'period':period,
				'direction':direction,
				'take_profit':tpval,
				'stop_loss':slval,
				'entry':safe_float(prstr),
				'the_date':the_date, #handle in json library
				'description':description
			}
			
			signals.append(signal)
		
		result['data'] = signals
		return result
	
class LiveForexSignals(SnapshotCrawler): 
	
	URL = 'https://live-forex-signals.com/en/'
	category = 'signals'
	
	
	def log_in(self, credentials = {}):
		self.browser.get('https://live-forex-signals.com/en/login/')
		
		username_field = self.browser.find_element(By.XPATH,"//input[@name='user_name']")
		password_field = self.browser.find_element(By.XPATH,"//input[@name='user_password']")
		
		if not credentials:
			config = Configuration()
			credentials = {
				'username':config.get('liveforexsignals','username'),
				'password':config.get('liveforexsignals','password')
			}
		
		username_field.send_keys(credentials['username'])
		password_field.send_keys(credentials['password'])
		
		login_btn = self.browser.find_element(By.XPATH,"//button[@type='submit']")
		login_btn.click()
		
	
	def crawl(self):
		
		
		result = self._result_base()
		signals = []
		
		self.log_in()
		
		
		#pdb.set_trace() 
		#signal_blocks = self.html.xpath("//div[contains(@class,'signal-card')]")
		html = lxml.etree.HTML(self.browser.page_source)
		signal_blocks = html.xpath("//div[contains(@class,'signal-card')]")
		
		#pdb.set_trace()
		for signal_block_container in signal_blocks:
			
			signal_block_class = signal_block_container.attrib['class']
			
			if 'filled' in signal_block_class or 'delay' in signal_block_class:
				continue 
				
			signal_block = signal_block_container.xpath(".//div[@class='card-body']")[0]
			signal = {} 
			
			
			signal['instrument'] = signal_block.xpath(".//div[@class='signal-title']/text()")[0].replace('signal','').strip()
			signal['direction'] = 'BUY' if 'buy' in signal_block_class else 'SELL' if 'sell' in signal_block_class else 'VOID'
			
			
			signal_rows = signal_block.xpath(".//div[contains(@class,'signal-row')]")
			for signal_row in signal_rows:
				title = signal_row.xpath(".//div[contains(@class,'signal-title')]/text()")
				value = signal_row.xpath(".//div[contains(@class,'signal-value')]/text()[last()]")
				
				if not title or not value:
					continue 
					
				title = title[0]
				value = value[0]
				
				if 'buy at' in title.lower() or 'sell at' in title.lower():
					signal['entry'] = safe_float(value) 
				if 'take profit' in title.lower():
					signal['take_profit'] = safe_float(value) 
				if 'stop loss' in title.lower():
					signal['stop_loss'] = safe_float(value) 
				if 'from' in title.lower():
					timestampscript = signal_row.xpath(".//div[contains(@class,'signal-value')]/script/text()")[0] #check
					signal['the_date'] = datetime.datetime.utcfromtimestamp(safe_int(timestampscript))
				
			signals.append(signal)
		
		result['data'] = signals
		return result
		
		
class ForexSignals10Pips(SnapshotScraper):
	
	URL = 'https://www.forexsignals10pips.com/'
	category = 'signals'

	def scrape(self):
		#pdb.set_trace()
		result = self._result_base()
		signals = []
		links = self.html.xpath("//a[contains(@href,'signal') and not(contains(@href,'signals'))]/@href")
		for link in links:
			time.sleep(1.5) #don't spam them
			self.change_link(self.URL + '/' + link)			
			signal_rows = self.html.xpath("//div[contains(@class,'portfolio-item')]//tr")
			signal = {} 
			
			
			for signal_row in signal_rows:
				
				tds = signal_row.xpath(".//td")
				(property, value) = (tds[0].text.lower().strip(), tds[1].text.strip()) if len(tds) > 1 else (None,None)
				
				if not property or not value:
					continue 
				
				if property == 'pair':
					signal['instrument'] = value
				
				if property == 'action':
					signal['direction'] = value
				
				if property == 'price':
					signal['entry'] = safe_float(value)
				 
				if 'stop loss' in property:
					signal['stop_loss'] = safe_float(value.split('(')[0]) #don't get pips value

				if 'take profit' in property:
					signal['take_profit'] = safe_float(value.split('(')[0]) #don't get pips value
					
				if 'creation date' in property: 
					signal['the_date'] = datetime.datetime.strptime(value, "%d-%m-%Y %H:%M:%S")
				
			signals.append(signal)
		
		result['data'] = signals
		return result	
	
class FXLeaders(SnapshotScraper): 
	
	URL = 'https://www.fxleaders.com/forex-signals/'
	category = 'signals'
	
	def scrape(self):
		#pdb.set_trace()
		self.render()
		signal_containers = self.html.xpath(".//div[contains(@class,'fxml-sig-cntr')]")
		
		result = self._result_base()
		signals = []
		
		for signal_container in signal_containers:
			blocks = signal_container.xpath("./div/div") #get the next divs down 
			if len(blocks) < 2:
				continue
			
			#fiddly - might beak in future
			title_div, details_div = blocks[:2]
			instrument_str, direction_str = title_div.text.split('\n')[:2]
			entrystr, slstr, tpstr = details_div.xpath("./div/div/div/div")[1].text.split('\n')[:3]
			
			#pdb.set_trace()
			
			if 'premium' in tpstr.lower() or 'premium' in slstr.lower():
				continue
			
			signal = {
				'instrument':instrument_str.split('(')[0].strip(),
				'direction':direction_str.upper(),
				'entry':None, #unknown
				'take_profit':safe_float(tpstr),
				'stop_loss':safe_float(slstr),
				'the_date':None #unknown, so just use the snapshot time and ensure that it is new by checking other recent snapshots 
			}
			
			
			if 'premium' not in entrystr.lower():	
				signal['entry'] = safe_float(entrystr)
			
			signals.append(signal)
			
		result['data'] = signals
		return result	


###ANALYSIS (with bias)
class DailyFXSR(SnapshotScraper):
	
	URL = 'https://www.dailyfx.com/support-resistance'
	category = 'analysis'
	
	@staticmethod
	def extract_text(elems):
		return '\n'.join(''.join(elem.itertext()) for elem in elems).strip()
			
	
	def scrape(self):
		sr_levels = [] 
		
		self.render()
		result = self._result_base()
		
		html = lxml.etree.HTML(self.html.html)
		sr_boxes = html.cssselect("div.dfx-supportResistanceBlock")
		for sr_box in sr_boxes:
			pair_box = sr_box.cssselect("a.dfx-supportResistanceBlock__pair")
			trend_box = sr_box.cssselect("div.dfx-supportResistanceBlock__trend svg") #svg.dfx-signalIcon--up 
			
			levels = []
			level_boxes = sr_box.cssselect("div.dfx-supportResistanceBlock__valueRow")
			
			for level_box in level_boxes:
				name_box = level_box.cssselect("span.dfx-supportResistanceBlock__valueName")
				value_box = level_box.cssselect("span.dfx-supportResistanceBlock__valueLevel")
				strength_box = level_box.cssselect("div.dfx-supportResistanceBlock__valueLevelStrength div")
				
				name = self.extract_text(name_box)
				value_str = self.extract_text(value_box)
				value = safe_float(value_str) if value_str else None
				
				strength = None				
				class_string = strength_box[0].attrib.get('class')
				if '--strong' in class_string:
					strength = 3
				if '--moderate' in class_string:
					strength = 2
				if '--weak' in class_string:
					strength = 1
					
				level = {
					'name':name,
					'value':value,
					'strength':strength
				}
				levels.append(level)
			
			bias = None
			if trend_box:
				class_string = trend_box[0].attrib.get('class')
				if '--up' in class_string:
					bias = 'bullish'
				if '--down' in class_string:
					bias = 'bearish'
				
			pair = self.extract_text(pair_box)
			
			
			sr_level = {
				#'timeframe':'unknown',
				'instrument':pair,
				'details':{
					'bias':bias,
					'levels':levels
				}
			}
			sr_levels.append(sr_level)
		
		result['data'] = sr_levels
		return result		
			

class FXStreetSR(SnapshotCrawler):
	
	URL = 'https://www.fxstreet.com/technical-analysis/support-resistance'
	category = 'analysis'
	
	def crawl(self):
		
		#pdb.set_trace()
		
		time.sleep(5)# wait for page to load 
		result = self._result_base()
		pplevels = []
		
		
		html = lxml.etree.HTML(self.browser.page_source)
		level_elems = html.xpath(".//div[@fxs_name='pivotpoints']")
		symbol_texts = html.xpath(".//div[@class='tt_symbolTitle' and not(@data-type='indicator')]//span[@class='tt_symbolText']/text()")
		
		
		
		for instrument, levels_elem in zip(symbol_texts, level_elems):
			lis = [safe_float(t) for t in levels_elem.xpath(".//li[@class='fxs_pivotPoints_list_item']/span/text()") if t.strip()]
			lins = levels_elem.xpath(".//li[@class='fxs_pivotPoints_list_item']//abbr/text()")
			levels = {k:v for k,v in zip(lins,lis)}
			pplevels.append({'instrument':instrument,'details':{'levels':levels}})
		
		result['data'] = pplevels
		return result

class ActionForexBias(SnapshotScraper):
	
	URL = "https://www.actionforex.com/markets/action-bias/"
	category = 'analysis' #macroscopic?
	
	bias_map = {
		'pos':'bullish',
		'neu':'mixed',
		'neg':'bearish'
	}
	
	def scrape(self):
		
		bias_values = []
		self.render()
		result = self._result_base()
		html = lxml.etree.HTML(self.html.html)
		bias_rows = html.xpath(".//div[@class='bias-main']/div[@class='bias-row']")
		
		for bias_row in bias_rows:
			instrument_l = bias_row.xpath("./div[@class='bias-pair-name']/a/text()")
			bias_strs = bias_row.xpath("./div[@class='bias-pair']/div/@class")
			biases = [self.bias_map[b] for b in bias_strs]
			if instrument_l and len(biases) >= 4:
				bias_value = {
					'instrument':instrument_l[0],
					'hour':biases[0],
					'6hour':biases[1],
					'day':biases[2],
					'week':biases[3]
				}
				bias_values.append(bias_value)
			
		result['data'] = bias_values
		return result
		
		


#MACROSCOPIC (things like interest rates and fear and greed index)
class FXStreetPolls(SnapshotCrawler):
	
	URL = 'https://www.fxstreet.com/rates-charts/forecast'
	category = 'macroscopic' #despite it called forecast, this is a poll and over high time frame, so it is macro
	
	def crawl(self):
		sr_levels = [] 
		
		result = self._result_base()
		
		time.sleep(3) #wait until finished loading
		
		html = lxml.etree.HTML(self.browser.page_source)
		table_rows = html.xpath("//section//table/tbody/tr")
		
		biases = []
		
		for table_row in table_rows:
			instrument_l = table_row.xpath("./td/abbr/@title")
			instrument = instrument_l[0].strip() if instrument_l else None
			
			if not instrument:
				continue
			
			forecast_timeframes = table_row.xpath("./td/div[contains(@class,'forecast_timeframe')]")
			for forecast_timeframe in forecast_timeframes:
				timeframe = 'unknown'
				class_str = forecast_timeframe.attrib.get('class','')
				if 'avg_1w' in class_str:
					timeframe = 'week'
				if 'avg_1m' in class_str:
					timeframe = 'month'
				if 'avg_1q' in class_str:
					timeframe = 'quater'
				
				bias_elems = forecast_timeframe.cssselect("div.forecast_avg_result") 
				bias = 'mixed'
				if bias_elems:
					if 'result_bullish' in bias_elems[0].attrib.get('class'):
						bias = 'bullish'
					if 'result_bearish' in bias_elems[0].attrib.get('class'):
						bias = 'bearish'
				
				tooltip_elems = forecast_timeframe.cssselect("table.c3-tooltip tr td.value")
				#pdb.set_trace()
				#[bullish,bearish,mixed] = [safe_float(t.text) for t in tooltip_elems[:3]] #tooltip doesnt exist for all elems - only active
				
				bias_info = {
					'timeframe':timeframe,
					'instrument':instrument,
					'details':{
						'bias':bias,
						#'bullish':bullish,
						#'bearish':bearish,
						#'mixed':mixed
					}
				}
				biases.append(bias_info)
		
		result['data'] = biases
		return result
		
class ForexFactoryCBR(SnapshotCrawler):
	
	URL = 'https://www.forexfactory.com/news'
	category = 'macroscopic'
	
	def crawl(self):
		result = self._result_base()
		
		time.sleep(5) #wait until finished loading
		
		html = lxml.etree.HTML(self.browser.page_source)
		rates = []
		interest_rate_rows = html.xpath("//ul[@class='rate_details bankrates__rates']/li[@class='bankrate__rate']")
		
		for interest_rate_row in interest_rate_rows:
			currency_l = interest_rate_row.xpath(".//span[@class='internal']/text()")
			rate_l = interest_rate_row.xpath(".//span[@class='rate']/text()")
			if currency_l and rate_l:
				currency = currency_l[0]
				rate = safe_float(rate_l[0])
				rates.append({'currency':currency,'central_bank_rate':rate})
			
		result['data'] = rates
		return result



class ActionForexCBR(SnapshotScraper):
	
	URL = 'https://www.actionforex.com/central-banks/'
	category = 'macroscopic'
	
	bank_currency_map = { 
		'boe':'GBP',
		'fed':'USD',
		'ecb':'EUR',
		'boj':'JPY',
		'snb':'CHF',
		'boc':'CAD',
		'rba':'AUD',
		'rbnz':'NZD'
	}
	
	def scrape(self):	
		
		cbrates = []
		
		self.render() #render page first
		result = self._result_base()
		
		html = lxml.etree.HTML(self.html.html)
		table_rows = html.xpath(".//table[@class='cb-sum']/tbody/tr")
		
		for table_row in table_rows:
			tds = table_row.xpath("./td/text()")
			if len(tds) > 2:
				bank = tds[0].strip().lower()
				perc = safe_float(tds[1].strip())
				currency = self.bank_currency_map.get(bank)
				if currency:
					cbrates.append({'currency':currency, 'central_bank_rate':perc})
		
		result['data'] = cbrates
		return result
		


#FEAR & GREED INDEX 
class CNNFearAndGreed(SnapshotCrawler):
	
	URL = 'https://edition.cnn.com/markets/fear-and-greed'
	category = 'macroscopic'
	
	def crawl(self):
		
		result = self._result_base()
		
		time.sleep(5)
		html = lxml.etree.HTML(self.browser.page_source)

		fgi = html.xpath("//span[@class='market-fng-gauge__dial-number-value']/text()")
		#pdb.set_trace()
		if fgi:
			result['data'] = {'fear_and_greed_index':safe_float(fgi[0])}
		
		return result

#weather? 
	
##TRADING VIEW --forecasts
##fx.co - forecasts (patterns ?)



##BROKER DETAILS? - perhaps not here.. 



#this bit is the cool bit - get all the data from multiple websites at the same time :) 

snapshot_elements = { #keys are human readable (get merged by server later)
	'client sentiment forexclientsentiment.com':ForexClientSentiment,
	'client sentiment myfxbook.com':MyFXBook,
	'client sentiment dailyfx.com':DailyFX,
	'client sentiment dukascopy.com':Dukascopy,
	'client sentiment fx.co':FXCOSentiment,
	#'client sentiment actionforex.com':
	'currency strength currencystrengthmeter.com':CurrencyStrengthMeter,
	'currency strength livecharts.com':LiveCharts,
	'currency strength fxblue.com':FXBlue,
	'copy trades forexfactory.com':ForexFactory,
	#'copy trades etoro':Etoro, #TODO
	'signals fx.co':FXCO,
	'signals live-forex-signals.com':LiveForexSignals,
	'signals forexsignals10pips.com':ForexSignals10Pips,	
	'signals fxleaders.com':FXLeaders,
	'analysis dailyfx.com':DailyFXSR,
	'analysis fxstreet.com':FXStreetSR,
	'analysis actionforex.com':ActionForexBias,
	#'forecasts tradingview.com':TradingView #TODO if needed
	'macroscopic fxstreet.com':FXStreetPolls,
	'macroscopic forexfactory.com':ForexFactoryCBR,
	'macroscopic actionforex.com':ActionForexCBR,
	'macroscopic fear and greed':CNNFearAndGreed
	#any others?
	
}

class MarketSnapshotWorker(ProcessWorker):
	
	def perform_task(self, snapshot_key):
		
		result = {'category':'NONE'} 
		result['key'] = snapshot_key
		
		try:
			snapshotter = snapshot_elements.get(snapshot_key)
			if snapshotter:
				result['url'] = snapshotter.URL
				
				if issubclass(snapshotter,SnapshotScraper):
					snapshotobj = snapshotter()
					result = snapshotobj.scrape() 
					
				if issubclass(snapshotter,SnapshotCrawler):
					with SeleniumHandler(hidden=True) as sh:
						snapshotobj = snapshotter(selenium_handler=sh)
						result = snapshotobj.crawl() 
			else:
				result['url'] = 'N/A'
				
		except Exception as e:
			log.warning(f"Task {snapshot_key} failed with {e}")
			result['category'] = 'ERROR'
			result['data'] = {'message':str(e), 'traceback':str(e.__traceback__)} 
		
		return (snapshot_key, result)
		

class MarketSnapshot:
	
	n_workers = min(len(snapshot_elements.keys()),5) #max 5
	
	@staticmethod
	def _snapshot_ref(link):
		bits = re.split('//|/|\?',link)
		servername = bits[1]
		return servername.lower().replace('www.','') 
	
	def get_snapshot(self):
		
		process_pool = ProcessPool([MarketSnapshotWorker(i) for i in range(self.n_workers)])
		snapshot_results = process_pool.perform(snapshot_elements.keys())
		
		#pdb.set_trace()
		#now group all together (avoiding any dict that has an 'error' value) 
		##snapshot = { ssk:ssv for (ssk,ssv) in snapshot_results if ssv['category'] != 'ERROR'}
		snapshot = {}
		for (k, snapshot_result) in snapshot_results: #remove element key
			try:
				snapshot_ref = self._snapshot_ref(snapshot_result['url'])
				if snapshot_ref not in snapshot:
					snapshot[snapshot_ref] = {} 
				snapshot[snapshot_ref][snapshot_result['category']] = snapshot_result
			except Exception as e:
				pdb.set_trace()
				print('error!')
		return snapshot
	
	def put_to_database(self,snapshot):
		with Database(cache=False) as cur:
			cur.execute("INSERT INTO market_snapshot_dump(snapshot) VALUES (%(snapshot)s);",{'snapshot':json.dumps(snapshot,default=str)})
			cur.con.commit() 














from collections import namedtuple
from enum import Enum
import re

import pdb

from web.scraper import Scraper
from web.crawler import Crawler, By
from web.feed_collector import TextBias as Bias #although used for text, the mechanism is the same for reporting the bias
from utils import ListFileReader

##useful? painful? can refactor out if annoying
ClientSentimentInfo = namedtuple('ClientSentimentInfo','source_ref instrument timeframe bias net_long net_short error') 
##add additional info such as changes and popularity/io etc? -perhaps this info is just volume? 


#consider combining together into multi-inheritance 
class ClientSentimentScraper(Scraper):

	instruments = ['all fx pairs we want to check for, including stem branches']
	tollerance = 30 #percentage 
	
	def __init__(self,source,instruments):
		super().__init__(source)
		self.instruments = instruments + [pair.replace('/','') for pair in instruments] #add the non-slash versions too 
	
	#override in classes below
	def scrape(self):
		raise NotImplementedError('This method must be overridden')
	
		
	#this is what is called to get ClientSentimentInfo tuples
	def get_client_sentiment_info(self):
		scraped_data = self.scrape()
		#do something with the data?
		#client_sentiment = [csi for csi in scraped_data]
		keep_these = [csi for csi in scraped_data if csi.bias != Bias.MIXED]
		
		#find slightly bullish and slightly bearish setups!
		##do some kind of analysis on these to get a better "slight" consensus 
		analyse_these = [csi for csi in scraped_data if csi.bias == Bias.MIXED and not csi.error] #we can't do anything about the errors :( 
		
		#simple analysis - see if netshort/netlong is below our tollerance 
		analysed_these = []
		for csi in analyse_these:
			new_bias = Bias.MIXED
			if csi.net_long == csi.net_short:
				new_bias = Bias.MIXED #catches 0 0 error when we couldnt read the numbers
			elif csi.net_long < self.tollerance:
				new_bias = Bias.SLIGHT_BULLISH
			elif csi.net_short < self.tollerance:
				new_bias = Bias.SLIGHT_BEARISH
			else:
				new_bias = Bias.MIXED #sucks - no real significant info for this pair
			analysed_these.append(ClientSentimentInfo(csi.source_ref,csi.instrument,csi.timeframe,new_bias,csi.net_long,csi.net_short,False))
			
		return keep_these + analysed_these 

#use for pulling stuff from harder websites 
class ClientSentimentCrawler(Crawler):
	
	instruments = ['all fx pairs we want to check for, including stem branches']
	tollerance = 30 #percentage 
	
	def __init__(self,selenium_handle,source,instruments):
		
		super().__init__(selenium_handle,source)
		self.instruments = instruments + [pair.replace('/','') for pair in instruments] #add the non-slash versions too 
	
	def get_client_sentiment_info(self):
		crawled_data = self.crawl()
		keep_these = [csi for csi in crawled_data if csi.bias != Bias.MIXED]
		
		#find slightly bullish and slightly bearish setups!
		##do some kind of analysis on these to get a better "slight" consensus 
		analyse_these = [csi for csi in crawled_data if csi.bias == Bias.MIXED and not csi.error] #we can't do anything about the errors :( 
		
		#simple analysis - see if netshort/netlong is below our tollerance 
		analysed_these = []
		for csi in analyse_these:
			new_bias = Bias.MIXED
			if csi.net_long == csi.net_short:
				new_bias = Bias.MIXED #catches 0 0 error when we couldnt read the numbers
			elif csi.net_long < self.tollerance:
				new_bias = Bias.SLIGHT_BULLISH
			elif csi.net_short < self.tollerance:
				new_bias = Bias.SLIGHT_BEARISH
			else:
				new_bias = Bias.MIXED #sucks - no real significant info for this pair
			analysed_these.append(ClientSentimentInfo(csi.source_ref,csi.instrument,csi.timeframe,new_bias,csi.net_long,csi.net_short,False))
		return keep_these + analysed_these
		
#class ClientCurrencySentiment(Scraper):
#
#	instruments = ['AUD','GBP']
#	tollerance = 30 #percentage 
#	
#	def __init__(self,source,instruments):
#		super().__init__(source)
#		self.instruments = instruments	
#	
#	def scrape(self):
#		#able to use directly?

class DailyFX(ClientSentimentScraper):
	
	def scrape(self):
		tables = self.html.find('table')
		info = []
		assert len(tables) == 1, 'More than 1 table found.'
		#soft error instead?
		table = tables[0]
		trows = table.find('tr')
		for trow in trows:
			tds = trow.find('td')
			if tds[0].text in self.instruments:
				instrument = tds[0].text
				timeframe = 240 #always in minutes but this is 4h
				bias = tds[1].text.upper()
				netlong = tds[2].text
				netshort = tds[3].text	
				parse_error = False
				try:
					netlong = float(netlong.replace('%',''))
					netshort = float(netshort.replace('%',''))
				except ValueError:
					parse_error = True
				src_bias = Bias.BULLISH if bias == 'BULLISH' else Bias.BEARISH if bias == 'BEARISH' else Bias.MIXED
				info.append(ClientSentimentInfo('dailyfx',instrument,timeframe,src_bias,netlong,netshort,parse_error))
		return info	
		

class MyFXBook(ClientSentimentScraper):
	
	#params for calculating the bias. 
	trader_ratio_threshold = 10
	limits = 30
	
	def scrape(self):
		table = self.html.xpath("//*[@id='outlookSymbolsTable']")
		info = []
		timeframe = 60 #not sure!
		if not table:
			return [] #log!
		table = table[0]
		for tr in table.xpath("//tr[@class='outlook-symbol-row']"):
			tds = tr.find('td')
			if not tds or tds[0].text.upper() not in self.instruments:
				continue
			instrument = tds[0].text.upper()
			bearbullbar = tds[1].xpath("//@style")
			netshort = bearbullbar[0]
			netlong = bearbullbar[1]
			parse_error = False
			try:
				netshort = float(re.findall('\d+',bearbullbar[0])[0])
				netlong = float(re.findall('\d+',bearbullbar[1])[0])
			except (ValueError, IndexError) as e:
				parse_error = True
			src_bias = Bias.MIXED #todo - perhaps if there are more than 15% traders and it is over 80% or under 20% then set the bias?
			if not parse_error:
				try:
					pop = tds[7].text.split('\n')
					if pop:
						ratio = float(re.findall('\d+',pop[-1])[0])
						if ratio > self.trader_ratio_threshold:
							if netshort < self.limits: #contrarian
								src_bias = Bias.BEARISH
							if netlong < self.limits:
								src_bias = Bias.BULLISH
				except (ValueError, IndexError) as e:
					parse_error = True
			instrument = instrument[:3] + '/' + instrument[3:] #add the slash back 
			info.append(ClientSentimentInfo('myfxbook',instrument,timeframe,src_bias,netlong,netshort,parse_error))
		return info

#use crawlers for harder websites
class ForexClientSentiment(ClientSentimentCrawler):
	
	@staticmethod
	def __decode_number(num_str):
		num_str = num_str.replace('%','')
		return float(num_str)

	def crawl(self):
		info = []
		#log a warning here
		timeframe = 1440 #from the chart on the website we can probably conclude it is daily - but might want to report 4h as we saw it change!
		#timeframe can be used to indicate how recent the signal is/how long it will be reported for
		sentiment_boxes = self.browser.find_elements(By.XPATH,"//a[@class='sentiment']")
		
		for box in sentiment_boxes:
			inst = box.find_elements(By.TAG_NAME,'h3')
			
			if not inst:
				continue
			instrument = inst[0].text
			if instrument not in self.instruments:
				continue
			parse_error = False
			bias = box.find_elements(By.TAG_NAME,'fxcs-contrarian-indicator')
			if bias:
				bias = bias[0].text.upper()
			else:
				parse_error = True
				bias = 'Mixed'
				
			long_box = box.find_elements(By.XPATH,".//*[@class='sentiment--values--numbers--long']") 
			short_box = box.find_elements(By.XPATH,".//*[@class='sentiment--values--numbers--short']")
			if not (long_box and short_box):
				continue
			
			netlong = long_box[0].text
			netshort = short_box[0].text
			
			try:
				netlong = self.__decode_number(netlong)
				netshort = self.__decode_number(netshort)
			except ValueError:
				#parse_error = True 
				#lets hack this through since these guys don't want us reading their numbers! but don't mind their sentiment! 
				netlong = None
				netshort = None
				parse_error = True
				
			src_bias = Bias.BULLISH if bias == 'BULLISH' else Bias.BEARISH if bias == 'BEARISH' else Bias.MIXED
			info.append(ClientSentimentInfo('forexclientsentiment',instrument,timeframe,src_bias,netlong,netshort,parse_error))
		return info


#use selenium to get currency pairs and/or currency sentiments from Dukascopy
class Dukascopy(ClientSentimentCrawler):

	def crawl(self):
		
		pdb.set_trace()
		
		self.browser
		pass
		
	





#bit of a hack to determine if we want the pairs or the currencies... 
#lfr = ListFileReader ()
#currencies = lfr.read('fx_pairs/currencies.txt')
#if set(self.instruments) == set(currencies):
#	return self.__scrape_currencies()
#else:
#	return self.__scrape_usual()


##any more sentiment indicators here
#TODO: special case, sentiment on currencies:
#https://www.dukascopy.com/swiss/english/marketwatch/sentiment/
















import datetime
import time
import os
import pdb
import tqdm

import numpy as np
import pandas as pd

import logging 
log = logging.getLogger(__name__)


from web.crawler import SeleniumHandler, Crawler, XPathNavigator, By, TimeoutException #perhaps just crawler for specialist stuff?
from utils import Database, Inject, Configuration, ListFileReader, TimeHandler

import debugging.functs as dbf

class DukascopyCSVProcessor:
	
	upsert_row = "(%(the_date.Bid)s, %(from_currency)s, %(to_currency)s, %(Open.Bid)s, %(High.Bid)s, %(Low.Bid)s, %(Close.Bid)s, %(Volume.Bid)s, %(Open.Ask)s, %(High.Ask)s, %(Low.Ask)s, %(Close.Ask)s, %(Volume.Ask)s)"
	
	upsert_batch = """
DROP TABLE IF EXISTS upsert_data;
WITH data(the_date, from_currency, to_currency, bid_open, bid_high, bid_low, bid_close, bid_volume, ask_open, ask_high, ask_low, ask_close, ask_volume) AS (
	VALUES %(allrows)s
)
SELECT * INTO TEMPORARY TABLE upsert_data FROM data;

DELETE FROM raw_fx_candles_15m rfc USING upsert_data ud
WHERE ud.the_date = rfc.the_date 
AND ud.from_currency = rfc.from_currency 
AND ud.to_currency = rfc.to_currency;

INSERT INTO raw_fx_candles_15m(the_date, from_currency, to_currency, full_name, bid_open, bid_high, bid_low, bid_close, bid_volume, ask_open, ask_high, ask_low, ask_close, ask_volume)
SELECT the_date, from_currency, to_currency, from_currency || '/' || to_currency AS full_name, bid_open, bid_high, bid_low, bid_close, bid_volume, ask_open, ask_high, ask_low, ask_close, ask_volume
FROM upsert_data; 

UPDATE raw_fx_candles_15m SET note = 'calculated'
WHERE the_date >= CURRENT_DATE::TIMESTAMP; --hacky! Could do with an additional column above for this for general case 
	"""
	
	cursor = None
	directory = None
	file_download_timeout = 5#seconds 
	file_age_limit = 14400#1 day
	
	end_volume_fix_n = 3
	db_batch_size = 250
	
	#consider this_date 
	the_date = None 
	
	
	def __init__(self, directory, cursor, the_date=datetime.datetime.now()): #probably never need to specify this? 
		self.directory = directory
		self.cursor = cursor
		self.the_date = datetime.datetime(the_date.year,the_date.month,the_date.day) #drop HMS 
	
	def acquire(self, instrument):
		
		bid_filename, ask_filename = self._find_filenames(instrument)
		
		bid_loc = os.path.join(self.directory,bid_filename)
		ask_loc = os.path.join(self.directory,ask_filename)
		
		bid_df = pd.read_csv(bid_loc)
		ask_df = pd.read_csv(ask_loc)
		
		bid_df['the_date'] = pd.to_datetime(bid_df['Gmt time'],format='%d.%m.%Y %H:%M:%S.%f').astype('datetime64[s]')
		ask_df['the_date'] = pd.to_datetime(ask_df['Gmt time'],format='%d.%m.%Y %H:%M:%S.%f').astype('datetime64[s]')
		
		bid_df = self._fix_end_volumes(bid_df,self.the_date)
		ask_df = self._fix_end_volumes(ask_df,self.the_date) 
		
		full_df, errors = self._join_bid_ask(bid_df,ask_df)
		#self.validate(full_df)#might not be needed here
		
		self._put_to_database(full_df, instrument)
		
		#cleanup as we now have in db 
		if not errors and False: 
			os.unlink(bid_loc) #we can safely delete
			os.unlink(ask_loc)
		else:
			log.warning(f"Missing dates for '{instrument}' - BID:{len(errors.get('bid',[]))}, ASK:{len(errors.get('ask',[]))}")
			pdb.set_trace()
		
	#only investigate the directory to get the relevant (fully qualified?) filenames 
	def _find_filenames(self, instrument):
		
		def suitable_file_name(fn):
			fnl = fn.lower()
			instrument_noslash = instrument.replace('/','').lower()
			return fnl.endswith('.csv') and ('bid' in fnl or 'ask' in fnl) and (instrument_noslash in fnl or instrument.lower() in fnl)
		
		start_time = time.time() #consider global
		
		bid_file = None
		ask_file = None
		
		while bid_file is None or ask_file is None:
			dir_files = [filename for filename in os.listdir(self.directory) if suitable_file_name(filename)]
			dir_paths = [(base_name,os.path.join(self.directory,base_name)) for base_name in dir_files]
			latest_files = [(fn,fp,os.path.getctime(fp)) for (fn,fp) in dir_paths if os.path.getctime(fp) > start_time - self.file_age_limit]
			
			latest_files.sort(key=lambda x: x[2],reverse=True)
			
			latest_bid_files = [fn for (fn,fp,ft) in latest_files if 'bid' in fn.lower()]
			latest_ask_files = [fn for (fn,fp,ft) in latest_files if 'ask' in fn.lower()]
			
			if latest_bid_files:
				bid_file = latest_bid_files[0]
			
			if latest_ask_files:
				ask_file = latest_ask_files[0]
			
			if bid_file and ask_file: 
				break
			
			if time.time() > start_time + self.file_download_timeout:
				which = [] 
				if bid_file is None:
					which.append('bid')
				if ask_file is None:
					which.append('ask')
				raise OSError(f"Failed to find {' and '.join(which)} file(s) for '{instrument}'.")
			
			time.sleep(1) # don't hammer the OS! 
		
		return bid_file, ask_file
	
	#for volume values that are later than this morning at 12am, they only count dukascopy so lets scale up according to prev results 
	def _fix_end_volumes(self,the_df,this_date):
		the_df['VolumeScaled'] = the_df['Volume']
		todays = the_df[the_df['the_date'] >= this_date].head(self.end_volume_fix_n)
		n_rows = len(todays)
		if not n_rows : #nothing to scale - there were no new rows today! (are you reading at midnight?)
			return the_df
			
		yesterdays = the_df[the_df['the_date'] < this_date].tail(n_rows)
		scale_factor = yesterdays['Volume'].sum() / todays['Volume'].sum() 
		
		#use indexer to set values 
		the_df.loc[the_df['the_date'] >= this_date,'VolumeScaled'] *= scale_factor
		
		return the_df
	
	#create new dataframe with bid_open, ask_open etc and datetimes, joining on datetimes
	def _join_bid_ask(self,bid_df,ask_df):	 
		bid_df = bid_df.set_index('the_date',drop=False)
		ask_df = ask_df.set_index('the_date',drop=False)
		full_df = bid_df.join(ask_df,lsuffix='.Bid',rsuffix='.Ask',how='inner')	
		
		errors = {}
		if len(bid_df) > len(full_df):
			errors['bid'] = list(set(bid_df['the_date']) - set(full_df['the_date.Bid']))
			
		if len(ask_df) > len(full_df):
			errors['ask'] = list(set(ask_df['the_date']) - set(full_df['the_date.Ask']))
			
		return full_df, errors
	
	#in batches, dump the full dataframe into the database 
	def _put_to_database(self, full_df, instrument):
		full_df['from_currency'], full_df['to_currency'] = instrument.split('/')[:2] #comment out if not fx
		#full_df['full_name'] = instrument
		def to_sql_string(row):
			return self.cursor.mogrify(self.upsert_row,row).decode()
		
		dbf.stopwatch('covert to sql')
		sql_rows_full = list(full_df.apply(to_sql_string,axis=1)) #slowish but works )
		dbf.stopwatch('covert to sql')	
		
		sql_batches = [sql_rows_full[i:i+self.db_batch_size] for i in range(0,len(sql_rows_full),self.db_batch_size)]
		for sql_rows in tqdm.tqdm(sql_batches):
			if sql_rows:
				self.cursor.execute(self.upsert_batch, {'allrows':Inject(','.join(sql_rows))})
				self.cursor.con.commit()

#class for getting either candles or volumes from the dukascopy dataset reader
class Dukascopy(Crawler): #change to Crawler?
	
	chart_resolution = 15 #stay at 15 since we will store all data at this resolution
	iframe_identifier = 'historical_data_feed'
	
	began = False
	
	cursor = None
	credentials = None
	url = 'https://www.dukascopy.com/swiss/english/marketwatch/historical/'
	
	downloads_folder = 'C:/Users/Ed/Downloads' #change as necessary
	
	default_settings = {
		'chart_resolution':15,
		'filter_flats':'All',
		'day_start_time':'UTC',
		'time_zone':'GMT',
		'volume':'Millions'
	}
	
	instruments = [] 
	from_date = datetime.datetime(2021,11,22)
	to_date = datetime.datetime.now()
	
	resolution_map = {
		5: {'number':5,'unit':'Minute'},
		10: {'number':10,'unit':'Minute'},
		15: {'number':15,'unit':'Minute'},
		30: {'number':30,'unit':'Minute'},
		60: {'number':1,'unit':'Hour'},
		240: {'number':4,'unit':'Hour'},
		1440: {'number':1,'unit':'Day'}
	}
	
	month_map = {
		'January':1,
		'February':2,
		'March':3,
		'April':4,
		'May':5,
		'June':6,
		'July':7,
		'August':8,
		'September':9,
		'October':10,
		'November':11,
		'December':12		
	}
	
	csv_handle = None
	
	def __init__(self,selenium_handle,cursor='',credentials=None):  #make it break with an empty string because None means debug 
		super().__init__(selenium_handle,self.url)
		if cursor is None or cursor.commit:
			self.cursor = cursor
		else:
			raise ValueError('Cursor must be a utils.Database object with commit = True, or None')
		self.credentials = credentials
		
	
	def set_gets(self,instruments,from_date,to_date):
		self.instruments = instruments
		self.from_date = from_date
		self.to_date = to_date
		
	def begin(self):		
		if self.began:
			return
			
		self.csv_handle = DukascopyCSVProcessor(self.downloads_folder, self.cursor) 
		
		the_iframe = self.browser.find_element(By.XPATH,"//iframe[contains(@src,'"+self.iframe_identifier+"')]")
		self.browser.switch_to.frame(the_iframe)
		self.began = True
		#log in! 
	
	def search_instrument(self,instrument):
		log.info("Waiting for element with 'All instruments'")
		#print("waiting for element 'All instruments'")
		self.perform_wait(By.XPATH,"//div/ul/li[contains(text(),'All instruments')]",2)
		all_instruments = self.browser.find_element(By.XPATH,"//div/ul/li[contains(text(),'All instruments')]")
		all_instruments.click()  #or self.click_on(all_instruments)
		
		#speed up by finding forex and lcicking it 
		forex_btn = self.browser.find_element(By.XPATH,"//div/ul/li[contains(text(),'Forex')]")
		forex_btn.click()
		
		#first attempt to find instrument using xpath here 
		instrument_row = None
		try:
			instrument_row = self.browser.find_element(By.XPATH,"//div[@class='d-qh-eh-eh-p']/ul/li[@data-instrument='"+instrument+"']")
		except:
			##on the case where we failed to find the instrument, do exhaustive search here
			#now find in the big list anything that resembles instrument 		
			print('getting all instrument rows')
			all_instrument_rows = self.browser.find_elements(By.XPATH,"//div[@class='d-qh-eh-eh-p']/ul/li")
			log.debug('search all_instrument_rows')
			#print('searching rows')		
			
			search_rows = [ir for ir in all_instrument_rows if ir.get_attribute('data-instrument') == instrument] #consider adding a mapping here
			if search_rows:
				instrument_row = search_rows[0]
		
		if instrument_row is None:
			log.warning(f"Unable to find {instrument}")
			return False			
		
		instrument_row.click()
		return True
		
	def input_settings(self,settings={}):
		
		settings = self.default_settings if not settings else settings 
		
		chart_res = Dukascopy.resolution_map[settings['chart_resolution']]
		candle_unit = chart_res['unit']
		candle_num = chart_res['number']
		
		candle_panel = self.browser.find_element(By.XPATH,"//div[contains(@class,'d-wh-vg-yh-p')]/label[contains(text(),'Candlestick')]/..")
		number_bit = candle_panel.find_element(By.ID,':j') #might change - keep eye on this - log!
		unit_bit = candle_panel.find_element(By.ID,':k')
		
		unit_bit.click() #opens units 
		unit_click = self.browser.find_element(By.XPATH, "//div[contains(@class,'a-L')]/div[contains(@class,'a-L-l') and contains(text(),'"+candle_unit+"')]")
		unit_click.click() 
		
		number_bit.click() #opens numbers 
		number_click = self.browser.find_element(By.XPATH, "//div[contains(@class,'a-L')]/div[contains(@class,'a-L-l') and contains(text(),'"+str(candle_num)+"')]")
		number_click.click()
		
		self.handle_from_date_select(self.from_date)
		self.handle_to_date_select(self.to_date)
		
		self.handle_filter_flats(settings['filter_flats'])		
		
		self.handle_day_start_time(settings['day_start_time'])
		
		self.handle_volume_switch(settings['volume'])
		
		if settings['time_zone'].upper() == 'GMT':
			self.press_gmt()
		if settings['time_zone'].upper() == 'LOCAL':	
			self.press_local()
	
	
	def press_bid(self):
		bid_button = self.browser.find_element(By.XPATH,"//div[contains(@class,'a-ab-v-y-x') and contains(text(),'BID')]")
		bid_button.click()
	
	def press_ask(self):
		ask_button = self.browser.find_element(By.XPATH,"//div[contains(@class,'a-ab-v-y-x') and contains(text(),'ASK')]")
		ask_button.click()
		
	def press_gmt(self):
		gmt_button = self.browser.find_element(By.XPATH,"//div[contains(@class,'a-ab-v-y-x') and contains(text(),'GMT')]")
		gmt_button.click()
	
	def press_local(self):
		local_button = self.browser.find_element(By.XPATH,"//div[contains(@class,'a-ab-v-y-x') and contains(text(),'Local')]")
		local_button.click()
		
	def handle_login(self):  #prompts up when pressing download sometimes 
		#test if it is visible - if not, we are already signed in 
		modal = [modal for modal in self.browser.find_elements(By.XPATH,"//div[@class='d-oh-i-ph-Rh-l']") if 'Log in' in modal.text and modal.is_displayed()]
		if modal:
			user = None
			passwd = None
			if self.credentials:
				user = self.credentials['username']
				passwd = self.credentials['password']
			else:
				cfg = Configuration()
				user = cfg.get('dukascopy','username')
				passwd = cfg.get('dukascopy','password')
			
			
			username_field = self.perform_wait(By.XPATH,"//input[@class='d-e-Xg' and @type='text' and contains(@placeholder,'Nickname or email')]",1)
			password_field = self.perform_wait(By.XPATH,"//input[@class='d-e-Xg' and @type='password']",1)

			login_btn = self.browser.find_element(By.XPATH,"//div[@class='d-ng-l-pg-ld-pg-ld-p']/div[contains(@class,'a-b-c') and contains(text(),'Sign in')]")
			
			
			click_username = lambda: username_field.click()
			self.poll_interaction(click_username,2) 
			username_field.send_keys(user)
			
			click_password = lambda: password_field.click()
			self.poll_interaction(click_password,2)
			password_field.send_keys(passwd)
			
			login_btn.click()
		
	
	def handle_day_start_time(self,dst):
		dst_panel =  self.browser.find_element(By.XPATH,"//div[contains(@class,'d-wh-vg-xh')]/label[contains(text(),'Day start time')]/..")
		dst_btn = dst_panel.find_element(By.XPATH,"./div[contains(@class,'a-b-c')]")
		dst_btn.click() 
		
		setting2id = {
			'eet':':c',
			'utc':':d'
		}
		
		the_id = setting2id[dst.lower()]
		
		click_btn = self.browser.find_element(By.ID,the_id)
		click_btn.click() 	
		
	
	def handle_volume_switch(self,vol):
		volume_btn = self.browser.find_element(By.ID,':2z')
		volume_btn.click()
		
		setting2id = {
			'units':':e',
			'thousands':':f',
			'millions':':g'
		}
		
		the_id = setting2id[vol.lower()]
		
		click_btn = self.browser.find_element(By.ID,the_id)
		click_btn.click() 	
		
	
	def handle_filter_flats(self,ff):
		ff_panel = self.browser.find_element(By.XPATH,"//div[contains(@class,'d-wh-vg-xh')]/label[contains(text(),'Filter flats')]/..")
		ff_btn = ff_panel.find_element(By.XPATH,"./div[contains(@class,'a-b-c')]")
		ff_btn.click() 
		
		setting2id = {
			'all':':9',
			'weekends':':a',
			'disable':':b'
		}
		
		the_id = setting2id[ff.lower()]
		
		click_btn = self.browser.find_element(By.ID,the_id)
		click_btn.click() 	
	
	def handle_from_date_select(self,the_date):
		from_panel = self.perform_wait(By.XPATH,"//div[contains(@class,'d-wh-vg-xh')]/label[contains(text(),'From date')]/..",1) 
		from_btn = from_panel.find_element(By.XPATH,"./div")
		from_btn.click()
		self.enter_date(the_date)
		
		
	def handle_to_date_select(self,the_date):
		to_panel = self.perform_wait(By.XPATH,"//div[contains(@class,'d-wh-vg-xh')]/label[contains(text(),'To date')]/..",1)  	
		to_btn = to_panel.find_element(By.XPATH,"./div")
		to_btn.click()
		self.enter_date(the_date)
	
	def enter_date(self,the_date):
		date_picker_popup = self.browser.find_element(By.XPATH,"//div[contains(@class,'a-popupdatepicker') and contains(@style,'visible')]") #ensure it is the visible elem?
		desired_year = the_date.year
		desired_month = the_date.month
		desired_day = the_date.day
		
		get_current_year_button =  lambda: date_picker_popup.find_element(By.XPATH,".//button[contains(@class,'d-Ch-fi-ni')]") #we need to call it each time we click 
		prev_year_button = date_picker_popup.find_element(By.XPATH,".//button[contains(@class,'d-Ch-fi-previousYear')]")
		next_year_button = date_picker_popup.find_element(By.XPATH,".//button[contains(@class,'d-Ch-fi-nextYear')]")
	
		get_current_month_button =  lambda: date_picker_popup.find_element(By.XPATH,".//button[contains(@class,'d-Ch-fi-mi')]")
		prev_month_button = date_picker_popup.find_element(By.XPATH,".//button[contains(@class,'d-Ch-fi-previousMonth')]")
		next_month_button = date_picker_popup.find_element(By.XPATH,".//button[contains(@class,'d-Ch-fi-nextMonth')]")
		
		year_btn = get_current_year_button() 
		current_year = int(year_btn.text) 
		
		maxrep = 100
		rep = 0
		while current_year > desired_year and rep < maxrep:
			prev_year_button.click() 
			year_btn = get_current_year_button() 
			current_year = int(year_btn.text) 
			rep += 1
		
		rep = 0 
		while current_year < desired_year and rep < maxrep:
			next_year_button.click() 
			year_btn = get_current_year_button() 
			current_year = int(year_btn.text) 
			rep += 1 
		
		month_btn = get_current_month_button()
		month_str = month_btn.text.strip().lower()
		
		def get_month_from_str(mstr):
			for ms,mi in Dukascopy.month_map.items():
				if ms.lower() == mstr.lower():
					return mi
			return -1
		
		rep = 0	
		current_month = get_month_from_str(month_str)
		while current_month > desired_month and rep < maxrep and current_month != -1:
			prev_month_button.click() 
			month_btn = get_current_month_button()
			month_str = month_btn.text.strip().lower()
			current_month = get_month_from_str(month_str)
		
		assert current_month != -1, f"Unable to find month {month_str}"
		
		rep = 0 
		while current_month < desired_month and rep < maxrep and current_month != -1:
			next_month_button.click() 
			month_btn = get_current_month_button()
			month_str = month_btn.text.strip().lower()
			current_month = get_month_from_str(month_str)
		
		assert current_month != -1, f"Unable to find month {month_str}"
		
		day_btns = date_picker_popup.find_elements(By.XPATH,".//td[contains(@class,'d-Ch-fi-Ch') and not(contains(@class,'d-Ch-fi-oi-mi'))]")
		for day_btn in day_btns: 
			if day_btn.text == str(desired_day):	
				day_btn.click()
				break 
	
	def press_reset(self):
		reset = self.browser.find_element(By.XPATH,"//div[contains(@class,'a-b-c') and contains(text(), 'Reset')]")
		reset.click()
	
	def press_download(self):
		download_btn = self.browser.find_element(By.XPATH,"//div[contains(@class,'a-b-c') and @role='button' and contains(text(),'Download')]")
		download_btn.click()
		self.handle_login() #does nothing if the modal is not displayed
		
	def long_poll_click_save_csv(self,expire=3600): #60 min expire 
		start = time.time() 
		get_button = lambda: self.browser.find_element(By.XPATH,"//div[@class='d-Wh-Xh-Zh-p']//div[contains(@class,'a-b-c') and contains(text(),'Save as .csv')]")
		get_info = lambda: self.browser.find_element(By.XPATH,"//p[@class='d-Wh-Xh-Yh']")
		
		while time.time() - start < expire:
			try:
				btn = get_button() 
				info = get_info()
				if btn and btn.is_displayed():
					btn.click()
					self.press_reset()
					return info.text
			except Exception as e:
				print(e)
			time.sleep(1) 
		raise TimeoutException('Download took too long.')

	def get_full_data(self,instrument):
		#print('searching for instrument')
		if self.search_instrument(instrument):	
			#print('found instrument')
			self.input_settings() 
			#print('input settings')
			self.press_bid() 
			self.press_download() 
			got_bid_str = self.long_poll_click_save_csv()
			
			self.press_ask()
			self.press_download() 
			got_ask_str = self.long_poll_click_save_csv()
			
			self.csv_handle.acquire(instrument) #use csv handle to load & save csvs to db
		
	
	def perform(self):
		self.begin() #incase 
		for instrument in self.instruments:
			print(f"Getting {instrument}...\n") 
			#data_frame = self.get_full_data(instrument)
			#data = self.fix_end_volumes(data)
			#self.upload_to_database(data_frame,instrument)
			self.get_full_data(instrument)
	



	

	#move to DukascopyCSVProcessor
	def fetch_file_data_and_delete(self,instrument):
		expire = 14400 #half an hour ago ?
		t1 = time.time()
		#settings = DukascopyData.default_settings if not settings else settings 
		
			
		#perform wait on os ? 
		tries = 0
		max_tries = 3
		latest_bid = None 
		latest_ask = None 
		while tries < max_tries: #try a few times since files might be still open in the browser file handle
			dir_files = [filename for filename in os.listdir(self.downloads_folder) if suitable_file_name(filename)]
			bid_files = [filename for filename in dir_files if 'bid' in filename.lower()]
			ask_files = [filename for filename in dir_files if 'ask' in filename.lower()]
			
			bid_file_paths = [os.path.join(self.downloads_folder,base_name) for base_name in bid_files]
			ask_file_paths = [os.path.join(self.downloads_folder,base_name) for base_name in ask_files]
			
			latest_bid_file_paths = [(file_path,os.path.getctime(file_path)) for file_path in bid_file_paths if os.path.getctime(file_path) > t1 - expire]
			latest_bid_file_paths.sort(key=lambda x: x[1],reverse=True)
			latest_bid_file_paths = [x[0] for x in latest_bid_file_paths]
			
			latest_ask_file_paths = [(file_path,os.path.getctime(file_path)) for file_path in ask_file_paths if os.path.getctime(file_path) > t1 - expire]
			latest_ask_file_paths.sort(key=lambda x: x[1],reverse=True)
			latest_ask_file_paths = [x[0] for x in latest_ask_file_paths]
			
			if not latest_ask_file_paths or not latest_bid_file_paths:
				time.sleep(0.5) #wait half a second (might have to be longer for bigger downloads) 
				tries += 1
				if tries == max_tries:
					#this could be caused when the files were not downloaded or your download directory is not writable
					raise OSError("Not able to get both files") 
				continue 
			
			latest_ask = latest_ask_file_paths[0]
			latest_bid = latest_bid_file_paths[0]
			break
		
		lfr = ListFileReader()
		
		ask_data = lfr.read_csv(latest_ask)
		bid_data = lfr.read_csv(latest_bid)
		
		#should only unlink if  there were no issues 
		#if not self.validate(bid_data, ask_data) 
		#	pdb.set_trace()
		#else: 
		#os.unlink(latest_bid) #delete them 
		#os.unlink(latest_ask) 
	
		all_data = {} 
		time_index = 'Gmt time' #change for other settings 
		
		def handle_date(datestr): #consider rolling back to nearest candle if found non-aligning one here 
			return TimeHandler.from_str_1(datestr)
			
		def float_conv(floatstr):
			return float(floatstr)
		
		for bid in bid_data:
			bid_datm = {'bid_open':float_conv(bid['Open']), 'bid_high':float_conv(bid['High']), 'bid_low':float_conv(bid['Low']), 'bid_close':float_conv(bid['Close']), 'bid_volume':float_conv(bid['Volume']) }
			the_date_str = bid[time_index] 
			the_date = handle_date(the_date_str)
			bid_datm['the_date'] = the_date
			all_data[the_date_str] = bid_datm 
		
		for ask in ask_data:
			ask_datm = {'ask_open':float_conv(ask['Open']), 'ask_high':float_conv(ask['High']), 'ask_low':float_conv(ask['Low']), 'ask_close':float_conv(ask['Close']), 'ask_volume':float_conv(ask['Volume']) }
			the_date_str = ask[time_index] 
			the_date = handle_date(the_date_str)			
			data_here = all_data.get(the_date_str,{})
			data_here.update(ask_datm)
			data_here['the_date'] = the_date
			all_data[the_date_str] = data_here
		
		#data_list = [(k,v) for k,v in all_data.items()] 
		data_list = list(all_data.values())
		return data_list
	
	
	#move to DukascopyCSVProcessor
	def fix_end_volumes(self,data_list,ave_n=3): #ensure it is known these are actually projected values from dukasopy and may be different when finding them again another day
		today = datetime.datetime.now(datetime.timezone.utc) 
		today_12am = datetime.datetime(today.year,today.month,today.day, 0, 0)
		
		todays_data = [d for d in data_list if d['the_date'] >= today_12am] #the current day data volume is usually incorrect & needs scaling
		historic_data = [d for d in data_list if d['the_date'] < today_12am] #historic data is usually at correct scale
		
		todays_data.sort(key=lambda d: d['the_date'])
		historic_data.sort(key=lambda d: d['the_date'])
		
		today_ave_comps = todays_data[:ave_n]
		historic_ave_comps = historic_data[-ave_n:]
		
		for td in today_ave_comps:  #any of these indicates there is a bug 
			if 'bid_volume' not in td:
				pdb.set_trace() 
				print('bid volume not found')
		
			if 'ask_volume' not in td:
				pdb.set_trace() 
				print('ask volume not found')
			
		for td in historic_ave_comps:
			if 'bid_volume' not in td:
				pdb.set_trace() 
				print('bid volume not found')
		
			if 'ask_volume' not in td:
				pdb.set_trace() 
				print('ask volume not found')
			
			
		today_ave_bid_volume = sum([td['bid_volume'] for td in today_ave_comps]) / ave_n
		today_ave_ask_volume = sum([td['ask_volume'] for td in today_ave_comps]) / ave_n  
		
		hist_ave_bid_volume = sum([td['bid_volume'] for td in historic_ave_comps]) / ave_n
		hist_ave_ask_volume = sum([td['ask_volume'] for td in historic_ave_comps]) / ave_n #ask_volume not found
		
		if today_ave_bid_volume and today_ave_ask_volume: #ensure there is some sort of reading for today
			bid_scale = hist_ave_bid_volume / today_ave_bid_volume 
			ask_scale = hist_ave_ask_volume / today_ave_ask_volume 
		
		todays_data_skip_bid_overrun = [] #happens when we pull data and one file contains later version than the other 
		missing_dates = []
		for td in todays_data:
			if 'bid_volume' not in td or 'ask_volume' not in td:
				missing_dates.append(td['the_date']) 
			td['bid_volume'] = td['bid_volume'] * bid_scale
			td['ask_volume'] = td['ask_volume'] * ask_scale
			todays_data_skip_bid_overrun.append(td)
		
		if missing_dates:
			log.warning('Missing dates when calculating volumes') #log the data?
			log.warning(missing_dates)
		
		return historic_data + todays_data_skip_bid_overrun
	#move to DukascopyCSVProcessor
	def upload_to_database(self,data,instrument,batch_size):
		raise NotImplementedError('This method must be overridden')
		

			

#class Dukascopy(DukascopyData):
#	
#
#	def upload_to_database(self,data_list, instrument, batch_size=250):
#		#do it in chunks? 
#		data_batches = [data_list[i:i+batch_size] for i in range(0,len(data_list),batch_size)]
#		from_currency,to_currency = instrument.split('/')[:2]
#		#with Database(commit=True,cache=False) as cursor:
#		if self.cursor is None: 
#			log.info('Not saving to database - cursor was None.')
#			return
#			
#		for batch in tqdm.tqdm(data_batches):
#			sql_rows = [] 
#			for tbb in batch:
#				try:
#					param = {
#						'the_date':tbb['the_date'],
#						'from_currency':from_currency, #tbb['from_currency'],
#						'to_currency':to_currency, # tbb['to_currency'],
#						'bid_open':tbb['bid_open'],
#						'bid_high':tbb['bid_high'],
#						'bid_low':tbb['bid_low'],
#						'bid_close':tbb['bid_close'],
#						'bid_volume':tbb['bid_volume'],
#						'ask_open':tbb['ask_open'],
#						'ask_high':tbb['ask_high'],
#						'ask_low':tbb['ask_low'],
#						'ask_close':tbb['ask_close'],
#						'ask_volume':tbb['ask_volume']
#					}
#					sql_rows.append(self.cursor.mogrify(self.upsert_row, param).decode())
#				except Exception as e:
#					log.warning('Issue with  '+from_currency+'/'+to_currency+' on '+str(tbb['the_date'])+' - "'+str(e)+'"')
#					
#					continue
#			if sql_rows:
#				self.cursor.execute(self.upsert_batch, {'allrows':Inject(','.join(sql_rows))})
#				self.cursor.con.commit()










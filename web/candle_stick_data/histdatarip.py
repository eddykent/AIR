# utility for reading data into the database from histdata.com 
# http://www.histdata.com/download-free-forex-historical-data/?/ascii/1-minute-bar-quotes/eurusd/2020


import psycopg2 
from selenium import webdriver
from selenium.webdriver.common.by import By
import datetime
import os
import glob
from zipfile import ZipFile
import time

import pdb

sql_batch_upsert_row = '''
(%(open)s,%(high)s,%(low)s,%(close)s,%(from)s,%(to)s,%(date)s)
'''

sql_batch_upsert = '''
WITH dat(_open,_high,_low,_close,_from,_to,_date) AS (
	VALUES %(allrows)s
)
SELECT * INTO TEMPORARY TABLE temp_data FROM dat;

UPDATE %(table)s 
SET high_price = temp_data._high, low_price = temp_data._low, open_price = temp_data._open, close_price = temp_data._close 
FROM temp_data
WHERE the_date = temp_data._date AND from_currency = temp_data._from AND to_currency = temp_data._to;

INSERT INTO %(table)s(from_currency,to_currency,full_name,open_price,high_price,low_price,close_price,the_date)
SELECT td._from, td._to, td._from || '/' || td._to, td._open, td._high, td._low, td._close, td._date 
FROM temp_data td
LEFT JOIN %(table)s e 
ON e.the_date = td._date AND e.from_currency = td._from AND e.to_currency = td._to 
WHERE e IS NULL;
DROP TABLE temp_data;
'''

class TimeHandle:
	
	histdata_timezone = 5 ## their data is in EST so we need to adjust it to GMT
	
	def handle(self,timestr):
	
		if len(timestr) == 15:
			#usual format YYYYMMDD HHMMSS
			yyyy = timestr[0:4]
			mm = timestr[4:6]
			dd = timestr[6:8]
			hh = timestr[9:11]
			nn = timestr[11:13] #minute
			ss = timestr[13:]
			
			return datetime.datetime(int(yyyy),int(mm),int(dd),int(hh),int(nn))
		else:
			pdb.set_trace()
	
	
	def handle_timezone(self,est_time):
		d = self.handle(est_time)
		d += datetime.timedelta(hours=self.histdata_timezone)
		return d
	
	def toDateTime(self,timestr):
		return self.handle_timezone(timestr)
		

class HistDataYear:

	urlhead = "http://www.histdata.com/download-free-forex-historical-data/?/ascii/1-minute-bar-quotes"
	chromedriver = "C:\Program Files (x86)\Google\Chrome\chromedriver.exe"
	download_dir = "./histdatatmp"
	timehandler = TimeHandle()
	tablename = 'exchange_value_tick'
	dbcur = None
	dbconn = None
	browser = None
	tick_length = 15 #minutes
	
	def __init__(self):
		if not os.path.isdir(self.download_dir):
			os.mkdir(self.download_dir)
		chrome_options = webdriver.ChromeOptions()
		the_download_dir = os.getcwd()+'/'+self.download_dir
		the_download_dir = the_download_dir.replace('/./','\\')
		prefs = {"download.default_directory":the_download_dir}
		chrome_options.add_experimental_option("prefs",prefs)
		self.browser = webdriver.Chrome(executable_path=self.chromedriver,chrome_options=chrome_options)
		self.dbconn = psycopg2.connect("host='localhost' user='postgres' password='0o9i8u7y' dbname='TradeData'")
		self.dbcur = self.dbconn.cursor()
		
	def __del__(self):
		self.dbcur.close()
		self.dbconn.close()
	
	def perform_selenium_for_file(self,what,year,month=None):
		what = what.replace('/','').lower()
		full_url = '/'.join([self.urlhead,what,year]) + ('/' + str(month) if month is not None else '')
		#pdb.set_trace()
		self.browser.get(full_url)
		file_link = self.browser.find_element(By.ID,'a_file')
		#handle if error - if on wrong page or something 
		file_link.click()
	
	def finished_downloading(self,what,year):
		what = what.replace('/','').upper()
		list_of_files = glob.glob(self.download_dir + '/*') # * means all if need specific format then *.csv
		thefiles = [fn for fn in list_of_files if what in fn and year in fn and fn.endswith('.csv')]
		return len(thefiles) > 0
		
	def read_file_data(self,what,year):
		what = what.replace('/','').upper()
		list_of_files = glob.glob(self.download_dir + '/*') # * means all if need specific format then *.csv
		thefiles = [fn for fn in list_of_files if what in fn and year in fn]
		assert len(thefiles) > 0
		data = ''
		with ZipFile(thefiles[0],'r') as zip_file:
			csvs = [fn for fn in zip_file.namelist() if fn.endswith('.csv')]
			assert len(csvs) == 1
			with zip_file.open(csvs[0]) as the_csv:
				data = the_csv.read()
		return data.decode()
		
	def process_into_bars(self,data,mins=15):
		lines = data.split('\n')
		datapoints = []
		for line in lines:
			if line:
				parts = line.split(';')
				(open_price,high_price,low_price,close_price) = parts[1:5]
				datapoint = [self.timehandler.toDateTime(parts[0]),
					float(open_price),
					float(high_price),
					float(low_price),
					float(close_price)
				]
				datapoints.append(datapoint)
		datapoints = sorted(datapoints,key=lambda x : x[0])
		first_date = datapoints[0][0]
		last_date = datapoints[-1][0]
		#start on the hour whatever happens
		start_date = datetime.datetime(first_date.year,first_date.month,first_date.day,first_date.hour,0)
		end_date = start_date + datetime.timedelta(minutes=mins)
		chunks = []
		chunk = []
		i = 0
		while i < len(datapoints):
			dp = datapoints[i]
			if dp[0] >= start_date and dp[0] < end_date:
				chunk.append(dp)
				i = i + 1 #next
			else:
				chunks.append(chunk) #copy?
				chunk = [] #new chunk
				#chunk.append(dp) - don't increment i 
				start_date += datetime.timedelta(minutes=mins)
				end_date += datetime.timedelta(minutes=mins)
		
		reduced_points = []
		for chunk in chunks:
			if chunk:
				the_date = chunk[0][0]
				open = chunk[0][1]
				close = chunk[-1][4]
				high = max(c[2] for c in chunk)
				low = min(c[3] for c in chunk)
				reduced_points.append([the_date,open,high,low,close])
		#pdb.set_trace()
		return reduced_points
		
	def upload_to_database(self,what,datapoints):
		what = what.upper().split('/')
		assert len(what) == 2
		sqllines = []
		for datapoint in datapoints:
			row_data = {
				'open':datapoint[1],
				'high':datapoint[2],
				'low':datapoint[3],
				'close':datapoint[4],
				'date':datapoint[0],
				'from':what[0],
				'to':what[1]
			}
			sqlrow = self.dbcur.mogrify(sql_batch_upsert_row,row_data).decode()
			sqllines.append(sqlrow)
				#pdb.set_trace()
		#pdb.set_trace()
		sqlrun = sql_batch_upsert % {'table':self.tablename,'allrows':','.join(sqllines)}
		self.dbcur.execute(sqlrun)
		self.dbconn.commit()
		
	def clear_file(self,what,year):
		what = what.replace('/','').upper()
		list_of_files = glob.glob(self.download_dir + '/*') # * means all if need specific format then *.csv
		thefiles = [fn for fn in list_of_files if what in fn and year in fn]
		assert len(thefiles) > 0
		os.remove(thefiles[0])
	
	def perform_get(self,what,year,month=None):
		self.perform_selenium_for_file(what,year,month)
		time.sleep(10)
		sleep_count = 0
		#while True:
		#	if self.finished_downloading(what,year):
		#		break
		#	time.sleep(1)
		#	sleep_count += 1
		#	if sleep_count > 5:
		#		print(">>>> failed to get "+what+" ("+year+")")
		#		return False
		data = self.read_file_data(what,year)
		data = self.process_into_bars(data,self.tick_length)
		self.upload_to_database(what,data)
		self.clear_file(what,year)
		return True
			
	
hd = HistDataYear()
#hd.perform_selenium_for_file('EUR/GBP',str(2015))
#data = hd.read_file_data('EUR/GBP',str(2019))
#hd.upload_to_database('EUR/GBP',data)
fx_mains = ['AUD/JPY',
'AUD/NZD',
'AUD/USD',
'AUD/CAD',
'AUD/CHF',
'CAD/CHF',
'CAD/JPY',
'CHF/JPY',
'EUR/AUD',
'EUR/CAD',
'EUR/CHF',
'EUR/GBP',
'EUR/JPY',
'EUR/NZD',
'EUR/USD',
'GBP/AUD',
'GBP/CAD',
'GBP/CHF',
'GBP/JPY',
'GBP/NZD',
'GBP/USD',
'NZD/CAD',
'NZD/CHF',
'NZD/JPY',
'NZD/USD',
'USD/CAD',
'USD/CHF',
'USD/JPY']

years =  [2020,2019,2018,2017,2016] #2021 when available!
#years = [2016,2015,2014,2013,2012]

for year in years:
	for fx in fx_mains:
		for month in [None]:#[1,2,3,4,5,6,7,8,9,10,11,12]:
			if not hd.perform_get(fx,str(year),month):
				pdb.set_trace()









































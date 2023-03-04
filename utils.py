# class for reading list files

import psycopg2
import psycopg2.extras
import datetime
import time
import hashlib
import pickle
import os
import sys
import re
import logging
import multiprocessing 
import json

import numpy as np

#from collections import MutableSequence


import pdb

log = logging.getLogger(__name__)

def overrides(interface_class):
    def overrider(method):
        assert (method.__name__ in dir(interface_class)), f"method {method.__name__} is not overriden by {interface_class.__name__}"
        return method
    return overrider

from deprecation import deprecated

from data.tools.cursor import Database



#turn type saftey on and off - useful for ensuring we get the correct type everywhere
class TypeSafe:
	
	__active = True
	__assert = True
	
	def __init__(self,active=True,assertions=False):
		self.__active = active
		self.__assert = assertions
	
	def has_type(self, value, the_type):
		if self.__active:
			message = f'The value has type {type(value)} which is not {the_type}'
			if type(value) != the_type:
				print(message)
			if self.__assert:
				assert type(value) == type, message
	
	def match_type(self,value1,value2):
		if self.__active:
			message = f'The first value has type {type(value1)} and the second value has type {type(value2)}, which do not match'
			if type(value1) != type(value2):
				print(message)
			if self.__assert:
				assert type(value1) == type(value2), message

#replace values in a target dictionary with those in a source dictionary if their keys match 
#turn this into a parametersettings object? Might be better since we can have load and save functionality
class DictUpdater:
	
	@staticmethod
	def update(target,source):
		for k in target:
			if k in source:
				target_type = type(target[k])
				source_type = type(source[k])
				if target_type == dict and source_type == dict:
					DictUpdater.update(target[k],source[k])
				else:
					if target_type != source_type:
						print(f'Warning, replacing key {k} value of type {target_type} with a different type of {source_type}')
					assert target_type != dict,'A dictionary is being replaced'
					assert source_type != dict,'A dictionary is being materialized'
					target[k] = source[k]
				
	#def load()
	
	#def save() 

#tool for annoying and cumbersome time/date stuff
#handle timezone, get time/data from string. make string of date/time
class TimeHandler:
	
	#histdata_timezone = 5 ## their data is in EST so we need to adjust it to GMT
	
	@staticmethod
	def from_numeric_string(timestr):
	
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
	
	#def handle_timezone(self,est_time):
	#	d = self.handle(est_time)
	#	d += datetime.timedelta(hours=self.histdata_timezone)
	#	return d
	#
	#def toDateTime(self,timestr):
	#	return self.handle_timezone(timestr)
	#
	
	@staticmethod  #date has format Day/Month/Year 
	def from_str_1(the_str,date_delimiter='.',time_delimiter=':'):
		#09.03.2022 00:52:56
		a_date,a_time = [t for t in the_str.split(' ') if t][:2]
		date_bits = [int(re.sub('[^0-9]','',a)) for a in  a_date.split(date_delimiter)]
		time_bits = [int(re.sub('[^0-9]','',a)) for a in  a_time.split(time_delimiter)]
		d,m,y = date_bits[:3]
		h,n = time_bits[:2] 
		s = 0
		#if len(time_bits) > 2:
		#	s = time_bits[2]
		return datetime.datetime(y,m,d,h,n,s)
	
	@staticmethod #date has format Year/Month/Day 
	def from_str_2(the_str,date_delimiter='-',time_delimiter=':'):
		#09.03.2022 00:52:56
		a_date,a_time = [t for t in the_str.split(' ') if t][:2]
		date_bits = [int(re.sub('[^0-9]','',a)) for a in  a_date.split(date_delimiter)]
		time_bits = [int(re.sub('[^0-9]','',a)) for a in  a_time.split(time_delimiter)]
		y,m,d = date_bits[:3]
		h,n = time_bits[:2] 
		s = 0
		if len(time_bits) > 2:
			s = time_bits[2]
		return datetime.datetime(y,m,d,h,n,s)
		
	@staticmethod
	def timestamp(the_time=None):
		if the_time is None:
			the_time = time.time()
		#get timestamp
		assert type(the_time) == int
		return datetime.datetime.utcfromtimestamp(the_time).strftime('%Y-%m-%d@%Hh%Mm%Ss')
		
	@staticmethod
	def datestamp(the_date=None):
		if the_date is None:
			the_date = datetime.datetime.now()
		#get datestamp
		assert type(the_date) == datetime.datetime
		return the_date.strftime('%Y-%m-%d@%Hh%Mm%Ss')
	
	@staticmethod
	def day_grouping(timeline): #timeline = list of datetimes earliest -> latest 
		#for a timeline of datetimes, return a group number of what day they are on 
		current_day_index = 0 
		current_dow = timeline[0].weekday() 
		day_indexs = [] 
		for dt in timeline:
			prev_dow = current_dow 
			current_dow = dt.weekday()
			if prev_dow != current_dow and current_dow <= 5: #combines fri,sat,sun for forex data
				current_day_index += 1
			day_indexs.append(current_day_index)
		return day_indexs
	
	#day_grouping_offset #use for pivot points 
		
#refactor to use typecheck? 
class TypedList:
	
	def __init__(self, type, *args): #extend to multiple types?
		self.the_type = type
		self.the_list = list()
		self.extend(list(args))
	
	def check(self, v):
		if self.the_type is None:
			raise ValueError('You should not be adding anything to this list.')
			
		if not isinstance(v, self.the_type):
			raise TypeError(f'You should only add {self.the_type} objects to this list')
	
	def __len__(self): 
		return len(self.the_list)
	
	def __bool__(self):
		return len(self.the_list) > 0
	
	def __getitem__(self, i): 
		return self.the_list[i]

	def __delitem__(self, i): 
		del self.the_list[i]
		
	def __setitem__(self, i, v):
		self.check(v)
		self.the_list[i] = v
	
	def __iter__(self):
		return self.the_list.__iter__()
		
	def __next__(self):
		return self.the_list.__next__()
	
	def __str__(self):
		return str(self.the_list)
		
	def __repr__(self):
		return self.the_list.__repr__()
	
	def append(self, v):
		self.check(v)
		self.the_list.append(v)
	
	def extend(self, vs):
		if type(vs) == TypedList:
			if vs.the_type != self.the_type:
				raise TypeError(f'You should only add {self.the_type} objects to this list')
				
			self.the_list.extend(vs.the_list)
		else:
			[self.check(v) for v in vs]
			self.the_list.extend(vs)
	
	def clear(self):
		self.the_list.clear()
	
	def __add__(self,vs):
		self.the_list.extend(vs)
		return self
	

class DisableLogger:
	def __enter__(self):
		logging.disable(logging.CRITICAL)
		
	def __exit__(self,exc_type,exc_value,exc_traceback):
		logging.disable(logging.NOTSET)
		
	
class DBDBLogHandler(logging.Handler):
	"""
	Custom log handler for inserting into the database all debug stuff. 
	"""
	
	db_error = False 
	sql_log_query = """
	INSERT INTO debug_log(created,log,level,file,line,module,process,thread,funct,message,exc_info,exc_text,stack_info) 
	VALUES (%(created)s,%(log)s,%(level)s,%(file)s,%(line)s,%(module)s,%(process)s,%(thread)s,%(funct)s,%(message)s,%(exc_info)s,%(exc_text)s,%(stack_info)s)
	RETURNING 1;"""
	sql_clear_old = "DELETE FROM debug_log WHERE created < %(clear_time)s RETURNING 1;"
	
	def __init__(self,skip_clean=False,elapse=7): 
		logging.Handler.__init__(self)
		if not skip_clean:
			clear_time = datetime.datetime.utcnow() - datetime.timedelta(days=elapse)
			try:
				with Database(cache=False,commit=True) as db:
					db.execute(self.sql_clear_old,{'clear_time':clear_time})
			except:
				self.setLevel(999999)
				log.error('Error setting up the database logger!',exc_info=True)
				self.db_error = True
	
	
	@overrides(logging.Handler)
	def emit(self,record):
		if self.db_error:
			return #skip if there was a db errror of any kind 
		
		params = {
			'created': datetime.datetime.fromtimestamp(record.created),
			'log': record.name,
			'level': record.levelname,
			'file': record.filename,
			'line': record.lineno,
			'process': record.processName ,
			'thread': record.threadName,
			'module':record.module,
			'funct': record.funcName,
			'message':record.msg,
			'exc_info':str(record.exc_info),
			'exc_text':record.exc_text,
			'stack_info':str(record.stack_info)
		}
		try:
			with Database(commit=True,cache=False) as db:
				db.execute(self.sql_log_query,params)
		except:
			self.setLevel(999999) #turn this handler off 
			log.error('Error using the database logger!',exc_info=True)
			self.db_error = True
	
#create one instance of this class to set up the logger - (from entry point)
class LogSetup:
	
	def __init__(self,skip_clean=False,file_elapse=7,db_elapse=10,use_file=True,use_stream=True,use_db=True):
		if use_stream:
			self.setup_stream()
		if use_file:
			self.setup_file(skip_clean,file_elapse)
		if use_db:
			self.setup_db(skip_clean,db_elapse)
	
	def setup_file(self,skip_clean,elapse):
		if not os.path.isdir('logs'):#create logs directory if it doesnt exist.
			os.mkdir('logs')
		#delete any old log files here
		right_now = datetime.datetime.now()
		logfilename = 'logs/'+right_now.strftime("%d-%m-%y") + '.log'
		
		file_format = "%(asctime)s(%(msecs)d) %(levelname)-8s [%(filename)s:%(lineno)s]: %(message)s"
		logfile = logging.FileHandler(logfilename,mode='a')
		logfile.setLevel(logging.WARNING)
		logfile.setFormatter(logging.Formatter(file_format))
		
		logger = logging.getLogger()
		logger.addHandler(logfile)
	
	def setup_stream(self):
		stream_format = "[%(filename)s:%(lineno)s] %(levelname)-8s:  %(message)s"
		logstream = logging.StreamHandler()#usual print 
		logstream.setLevel(logging.INFO)
		logstream.setFormatter(logging.Formatter(stream_format))
		logger = logging.getLogger()
		logger.addHandler(logstream)
	
	def setup_db(self,skip_clean,elapse):
		logdb = DBDBLogHandler(skip_clean=skip_clean,elapse=elapse)
		logdb.setLevel(logging.DEBUG)
		logger = logging.getLogger()
		logger.addHandler(logdb)
		

#allows for comments inside files that are simply a list of stuff. 
class ListFileReader:
	
	comment_tokens = ['--']
	errors=None
	not_found_none=False #when true, if the file isnt found then none is returned
	
	def __init__(self):
		pass
	
	def read(self,filename):
		the_list = []
		lines = []
		try:
			with open(filename,'r',errors=self.errors) as f:
				lines = f.read().split('\n')
			for line in lines:
				for c in self.comment_tokens:
					line = line.split(c)[0]
				result_line = line.strip()
				if result_line:
					the_list.append(result_line)
		except FileNotFoundError as fnf:
			if self.not_found_none:
				return None
			else:
				raise fnf
		return the_list
	
	def read_full_text(self,filename):
		lines = self.read(filename)
		if self.not_found_none and lines is None:
			return None 
		return '\n'.join(lines)
	
	def read_csv(self,filename):
		def read_value(v):	
			try:
				return float(v)
			except ValueError as e: #the value was not a number 
				return v 
		lines = self.read(filename)
		if self.not_found_none and lines is None:
			return None 
		heads = [l.strip() for l in lines[0].split(',')]
		result_dicts = []
		for line in lines[1:]:
			result_dicts.append({k:read_value(v) for k,v in zip(heads,[l.strip() for l in line.split(',')])})
		return result_dicts
	
	def read_json(self,filename):
		jsontext = self.read_full_text(filename)
		return json.loads(jsontext)  
	


#hold a currency pair more formally
class CurrencyPair:
	
	from_currency = None
	to_currency = None
	
	def __init__(self,pair):
		bits = pair.split('/')
		if len(bits) == 2:
			self.from_currency,self.to_currency = bits
	
	def __str__(self):  #str function doesnt take currency pair list in so need separate str function 
		if self.from_currency and self.to_currency:
			return self.from_currency + '/' + self.to_currency
		else:
			return None
	
	def is_reversed(self,currency_pair_list):	
		if self.to_currency + '/' + self.from_currency in currency_pair_list:
			return True
		return False #perhaps raise an error if the reverse is also not in the list
	
	def as_string(self,currency_pair_list):
		if self.is_reversed(currency_pair_list):
			return self.to_currency + '/' + self.from_currency 
		else:
			string_rep = str(self)
			if string_rep in currency_pair_list:
				return string_rep
			
		return 'UNKNOWN'

	
#prepares all database results that have dates into samples ready for a learning algorithm
#In other words, this does all the painful timeseries preprocessing
#in -> raw database results of the form [timestamp, n, dictionary] (both raw x and y data). 
#out-> A stitched up list of the form [timestamp, x_data, y_data]
#timestamps might not land on the second so some kind of merging needs to be done
class TimeZipper:
	
	x_sequence_lengths = [100]
	number_of_sequences = 200 
	
	#deprecated - may ressurect this feature in future 
	sequences_per_day = 1#consider if we want 2 or 4? OR EVEN 3?? 
	
	#if true, candles that overlap the current time (eg start_date << working_date << end_date) are allowed
	# otherwise, the end date of the candle is behind the working date (eg end_date <= working_date)
	overlap = False 
	
	#step_y = 0 #we may want to predict the NEXT y not the current one - so use this to push the Y sequence forward
	#this should not be handled here - we may want to use the excess Xs for predicting the next Y in PRD 
	
	def __init__(self):
		pass
		
	def subprocess_x_to_positions(self,x,root_timeline):
		
		if not root_timeline: #if we have no timeline, we should exit with no position info 
			return []
		
		root_index = 0 #start at the first time
		working_date = root_timeline[root_index] 
		x_start_positions = [] 
		for index in range(0, len(x)):
			this_start_date = x[index][0] #assume the date is ALWAYS at 0
			this_end_date = x[index-1][0] if index > 0 else working_date
			if this_start_date < working_date and (this_end_date <= working_date or self.overlap): #if this candle is fully behind the working date we are on
				#we have passed a boundary - a sequence should start from here for an X value that corresponds to 
				#the date of the current y value 
				#we cant take this_date = working_date because we dont want the candle that STARTS at this time, 
				#this information needs to be hidden from the alg to make the testing fair 
				x_start_positions.append(index)#so lets add this index, which is the latest possible one without knowing current price
				#then lets get the next time in the y-value list
				root_index += 1
				working_date = root_timeline[root_index] if root_index < len(root_timeline) else datetime.datetime(1900,1,1)
				#if  we elapse the y list, there are no more indexs to get so lets set the working date to ages ago
		
		return x_start_positions
	
	def process(self,Xs,Y):
		#y is of one timestamp per result, so we can line up everything according to ys timestamps
		#lets ensure that everything is sorted in descending order (we want recent data) 
		Y = sorted(Y,key=lambda y: y[0],reverse=True)
		Xs = [sorted(X,key=lambda x: x[0],reverse=True) for X in Xs]
		
		Y = Y[:self.number_of_sequences] #only get the number of sequences we wanted 
		
		#next pull the root timeline from Y - this gives us the end of each datapoint we want to collect
		root_timeline = [y[0] for y in Y]
		assert all(type(t) == datetime.datetime for t in root_timeline), "Some types are not datetimes in the root timeline"
		
		#for each X, we need an index to tell us where to start the sequence from so that it corresponds to the entry in the root timeline.
		corresponding_x_positions = [self.subprocess_x_to_positions(X,root_timeline) for X in Xs] 
		assert all(len(Xpos) == self.number_of_sequences for Xpos in corresponding_x_positions), "There are not enough sequences to fulfil X and Y pairings"
		
		Xss = [] #all subsequences of all Xs go in here 
		for xs_i in range(0,len(Xs)):
			x_sequence_length = self.x_sequence_lengths[xs_i]
			x_starting_positions = corresponding_x_positions[xs_i]
			x_sequence = Xs[xs_i]
			
			#each sample is a slice from the main x_sequence. Has to be back in ascending order (earliest datapoint -> latest datapoint)
			x_subsequences = [sorted(x_sequence[pxi:pxi+x_sequence_length],key=lambda x:x[0]) for pxi in x_starting_positions ]
			x_subsequences = x_subsequences[::-1] #reverse since we want samples to be in asc order earliest -> latest
			
			#x_subsequences = x_subsequences[:-self.step_y] if self.step_y > 0 else x_subsequences
			
			Xss.append(x_subsequences)
		
		#what if the candle length is bigger than Y gaps? or we have 4 sequences per day yet we have candles of size 4 
		#	example - each sequence starts at 12, 18, 0 and 6 but candles start at 12,16,20,0,4 and 8? 
		#this will now not work very well - the 'half' candle that starts at 16 (when the Y starts at 18) will be omitted!
		#The database does not deal with half-candles and we should keep it that way to prevent things getting really complicated
	
		#lastly, lets put everything back into ascending order (Xss already back in correct order)
		Y = sorted(Y, key=lambda y:y[0])
		#Y = Y[self.step_y:] if self.step_y > 0 else Y
		return Xss, Y

#consider making dynamic - based on date ranges if pips ever changes
class PipHandler:
	
	pip_map = {} #use pip map for internal ops elsewhere

	def __init__(self,pip_file="config/pip_sizes.json"):
		
		lfr = ListFileReader()
		self.pip_map = lfr.read_json(pip_file)
			
	def pips_to_movement(self, instrument, pips):
		if instrument not in self.pip_map:
			log.error(instrument + ' not recognised!')
		return self.pip_map[instrument] * pips 
	
	def movement_to_pips(self, instrument, movement):
		if instrument not in self.pip_map:
			log.error(instrument + ' not recognised!')
		return movement / self.pip_map[instrument]
	
	pips2move = pips_to_movement
	move2pips = movement_to_pips


#use this class for accessing instrument details such as leverage, base currency, exchange, interest etc 
#see if there is a way to automatically make instrument_details.csv from the broker
class InstrumentDetails:
	
	instrument_map = {} 
	
	def __init__(self,instrument_file='data/csvs/instrument_details.csv'):
		lfr = ListFileReader()
		instrument_details = lfr.read_csv(instrument_file)
		self.instrument_map = {idetail['instrument']:idetail for idetail in instrument_details} 
	

#class to handle splitting our data up into training and testing sets
#also select the actual data we want to use in the neural net (instruments and keys)
class SplitAndPrepare:
	
	validation_size = 10 
	test_size = 10
	perform_current = False #set to true when we are actually wanting to get the prediction for right now 
	features = [] #grab SELL or BUY if it is Y data, or grab ema100 or rsi from X data etc... 
	sequential = False #enabled if the dataset is being generated for a recurrent neural network 
	instruments = [] #could be fx_pairs or currencies depending on what we are preparing 
	
	def __init__(self):
		pass
	
	#should be single sequence of data with each step being a dictionary of instruments 
	def __select_instruments(self,sample):
		selected = []
		for snapshot in sample:
			subselect = []
			snapshot_date = snapshot[0]
			snapshot_count = snapshot[1]
			snapshot_data = snapshot[2] 
			if self.instruments:
				#data debug: 
				for inst in self.instruments:
					if not inst in snapshot_data:
						print('WARNING: %(inst)s is missing from the snapshot on date %(snapshot_date)s' % {'inst':inst,'snapshot_date':snapshot_date})
				subselect = [self.__select_features(snapshot_data[inst]) for inst in self.instruments]
			else:
				subselect = [self.__select_features(snapshot_data)] #preserve array dimensionality? (wrappped in [])
			selected.append(subselect)
		return selected
		
	def __select_features(self,instrument):
		return [instrument[k] for k in self.features] if self.features else [instrument] #preserve array? 
		
	def __chop(self,data,current):
		if current:
			return data[:-1], [], data[-1:] #chop top 1 off? 
		#pdb.set_trace()
		return data[:-(self.validation_size + self.test_size)], \
			data[-(self.validation_size + self.test_size):-self.test_size],\
			data[-self.test_size:]
	
	def __check_params(self):
		if not type(self.features) == list:
			print("WARNING: features should be of list type! - proceeding with singleton list" )
			self.features = [self.features]
		if not type(self.instruments) == list:
			print("WARNING: instruments should be of list type! - proceeding with singleton list" )
			self.instruments = [self.instruments]
	
	def prepare(self,samples,post_funct=None):
		this_datetime = datetime.datetime.now() - datetime.timedelta(minutes=30)
		latest_date = samples[-1][-1][0] if self.sequential else samples[-1][0]
		perform_current = latest_date > this_datetime or self.perform_current
		
		self.__check_params()
		
		prepared = []
		if self.sequential:
			prepared = [self.__select_instruments(s) for s in samples]
		else:
			prepared = self.__select_instruments(samples) 
		
		train,validate,test = self.__chop(prepared,perform_current)
		if callable(post_funct):
			train = post_funct(train)
			validate = post_funct(validate)
			test = post_funct(test)
		return np.array(train), np.array(validate), np.array(test)
		























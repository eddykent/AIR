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

from configparser import ConfigParser

import pdb
from psycopg2.extensions import AsIs as Inject

log = logging.getLogger(__name__)

def overrides(interface_class):
    def overrider(method):
        assert (method.__name__ in dir(interface_class)), f"method {method.__name__} is not overriden by {interface_class.__name__}"
        return method
    return overrider

from deprecation import deprecated


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
		
class TaskHandler:  #collect tasks and then wait for them all to finish using multiprocessing 
	pass

class AsyncHandler: #collect tasks and then wait for them all to finish using asyncio 
	pass
	
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
		lines = self.read(filename)
		if self.not_found_none and lines is None:
			return None 
		heads = lines[0].split(',')
		result_dicts = []
		for line in lines[1:]:
			result_dicts.append({k:v for k,v in zip(heads,line.split(','))})
		return result_dicts
	
	def read_json(self,filename):
		jsontext = self.read_full_text(filename)
		return json.loads(jsontext)  
	
#wrapper around SafeConfigParser to get config - particularly db connection info 
class Configuration: 

	config_ini = './config.ini'
	parser = None
	
	def __init__(self,config_ini=None):
		self.parser = ConfigParser()
		#pdb.set_trace()
		self.config_ini = config_ini if config_ini is not None else self.config_ini
		self.parser.read(self.config_ini)
		
	def get(self,section,key):
		return self.parser.get(section,key)
	
	def database_connection_string(self):
		connection_keys = ['host','user','password','dbname']
		connection_details = {key:self.get('postgres',key) for key in connection_keys}
		return ' '.join(["%(key)s='%%(%(key)s)s'" % {'key':key} for key in connection_details]) % connection_details


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

#class for recieving and caching data from the database 
class Database:
	
	con = None
	cur = None
	cache = True
	query = ''
	rows = [] 
	query_cache_dir = 'data/pickles/datacache'
	previous_query_filename = 'queries/previous_query.txt'
	commit = False
	
	default_parameters = {
		'take_profit_factor':10, #movement required (in multiples of average true range) to hit a take profit
		'stop_loss_factor':7, #movement required (in multiples of average true range) to hit a stop loss
		'spread_penalty':3, #penalty added (in multiples of average true range) that change the price at 10pm to account for crazy spread times
		'normalisation_window':200, #where to find max and min values for normalising data to between 0 and 1
		'starting_candle':2,#which 15 minute candle to start from when evaluating trading schedules (to account for computation time)
		'the_date':None,#date in which the trade will happen (and all learning is from subsequent candles before etc) 
		'hour':None, #the time in which the trade will happen 
		'candle_offset':0, #if using 4h chart, this needs to be 120 minutes (2 hours)
		'days_back':1500, #rough estimate of how much data needs to be read to get enough to generate all sequences
		'trade_length_days':1, #the length a trade is expected to last (close the trade if it elapses this time)
		'currencies':[], #list of contributing currencies for currency strength and other calculations 
		'chart_resolution':60, #use the 1h chart (15mins, 30mins, 1h and 4h available!) 
		'average_true_range_period':14,
		'relative_strength_index_period':14,
		'stochastic_oscillator_period':14,
		'stochastic_oscillator_fast_d':3,
		'stochastic_oscillator_slow_d':3,
		'macd_slow_period':23,
		'macd_fast_period':12,
		'macd_signal_period':8,
		'custom_sma_period':10, 
		'custom_ema_period':10,
		'bollinger_band_period':20,
		'bollinger_band_k':2
	}
	
	def __init__(self,commit=False,cache=True,config=None):
		cfg = Configuration() if config is None else config
		self.con = psycopg2.connect(cfg.database_connection_string())
		self.cur = self.con.cursor()
		self.commit = commit #when true, when exiting the query will be committed
		self.cache = cache # oh my goodness you will be hunting for hours if you dont disable this on database updates! :)
	
	def __enter__(self):
		return self #most things handled at init - maybe use a connect() method instead?
	
	def __exit__(self,exc_type,exc_val,exc_tb):
		if self.commit:
			self.con.commit()
		self.close()
	
	def get_default_parameters(self,params):
		all_params = {k:v for k,v in self.default_parameters.items()} #copy dictionary
		all_params.update(params)
		return all_params
	
	def mogrify(self,query,params):
		new_params = self.get_default_parameters(params)
		return self.cur.mogrify(query,new_params)
	
	def execute(self,query,params={},no_results=False):
		self.query = self.mogrify(query,params) #already in bytes
		
		if self.cache:
			hash = hashlib.sha256(self.query).hexdigest()
			filename = hash + '.pickle'
			fullfilename = os.path.join(self.query_cache_dir,filename)
			if os.path.exists(fullfilename):
				with open(fullfilename,'rb') as f:
					self.rows = pickle.load(f)
			else:
				self.cur.execute(query,self.get_default_parameters(params))
				if self.cur.rowcount >= 0:  #consider moving to own method fetchall()?
					try:
						self.rows = self.cur.fetchall()  #rsults in psycopg2.ProgrammingError if a query was ran with no results (eg update without returning) 
						with open(fullfilename,'wb') as f:
							pickle.dump(self.rows,f)
					except TypeError as te:
						log.warning('Type error occurred when attemptin to pickle.', exc_info=True)
						if str(te) == "can't pickle memoryview objects":
							pass #we have  some raw bytes that pickle doesnt like. that's okay though we can continue without caching. 
						else:
							raise te #might be something else so best to propagate the error and not swallow it
					except psycopg2.ProgrammingError as pe:
						log.warning('Executed with no results to fetch.')
						if no_results and str(pe) == 'no results to fetch':
							pass
						else:
							raise pe
							
		else:
			self.cur.execute(query,self.get_default_parameters(params))
			try:
				if self.cur.rowcount > 0:
					self.rows = self.cur.fetchall()
			except psycopg2.ProgrammingError as pe:
				if no_results and str(pe) == 'no results to fetch':
					log.debug('Executed with no results to fetch.')
					pass
				else:
					pass #log.warning('Executed with no results to fetch.')
					#raise pe   #this can happen if there were any updates/deletes etc and no returning statement 
				
		try:
			with open(self.previous_query_filename,'wb') as f:
				f.write(self.query)
		except:
			pass #should log here 
			
	def fetchall(self):
		return self.rows
	
	def fetchone(self):
		return self.rows[0] if len(self.rows) > 0 else None
	
	def flush(self):
		self.rows = [] 
		#self.cur.flush()
		
	#move to somewhere else
	def fetchcandles(self,instruments):
		return_dict = {} 	
		
		for instrument in instruments:
			try:
				return_dict[instrument] = sorted([
				[
					snapshot[2][instrument]['open_price'],
					snapshot[2][instrument]['high_price'],	
					snapshot[2][instrument]['low_price'],
					snapshot[2][instrument]['close_price'],
					snapshot[0] #the date should always go at the bottom of the candle
				]
				for snapshot in self.rows],key=lambda c:c[-1]) #sort into chronological order 
			except KeyError as ke:
				log.warning(f"Unable to find '{instrument}'.",exc_info=True)
				return_dict[instrument] = None 
		return return_dict
	
	def close(self):
		self.cur.close()
		self.con.close()


class DataComposer:
	'''
	Class for handling all the database stuff for us when we want to get indicators or currency strength etc. 
	The class can be chained or used normally, and takes away a lot of complications when combining stuff in 
	query files separately. Is this a good idea? :/ yes because the upkeep will be much easier! :) if we need 
	to change anyting about collecting the candles we now only have to do it in the get_candles functions. 
	Previously we had to change every single sql file... 
	'''
	
	cursor = None
	_function_register_query_file = 'queries/function_register_json.sql'
	_temp_tables = [] 
	#_prev_function_signature = None
	_function_register = {}
	_call_queue = []
	_schema = 'trading'
	_branch = 0
	_this_branch = 0
	_end_join_tables = []
	_sql_code = ''
	
	_temp_table_formats =	{
		'values':[
			('row_index','INTEGER'),
			('the_date','TIMESTAMP WITHOUT TIME ZONE'),
			('full_name','TEXT'),
			('value','DOUBLE PRECISION')
		],
		'candles':[
			('row_index','INTEGER'),
			('the_date','TIMESTAMP WITHOUT TIME ZONE'),
			('full_name','TEXT'),
			('open_price','DOUBLE PRECISION'),
			('high_price','DOUBLE PRECISION'),
			('low_price','DOUBLE PRECISION'),
			('close_price','DOUBLE PRECISION')
		]
	}
	
	_type_map = {
		'TIMESTAMP WITHOUT TIME ZONE':datetime.datetime,
		'INTEGER':int,
		'DOUBLE PRECISION':float,
		'TEXT':str,
		'ARRAY':list,
		'BOOL':bool, 
		'BOOLEAN':bool
	}
	
	def __startup(self):	
		lfr = ListFileReader()
		function_register_query = lfr.read_full_text(self._function_register_query_file)
		function_register_query = function_register_query.replace('%','%%')
		self.cursor.execute(function_register_query)
		self._function_register = self.cursor.fetchone()[0] 
		self.cursor.flush()
	
	def __init__(self,cursor,reset_branches=False):
		self.cursor = cursor
		if reset_branches:
			DataComposer._branch = 0
			DataComposer._temp_tables = [] 
			DataComposer._call_queue = []
			DataComposer._end_join_tables = []
			
		self._this_branch = DataComposer._branch
		DataComposer._branch += 1
		
	
	#each call will create a functiong call on the call queue. THese can then be evaluated and threaded together into SQL when fetching results. 
	def call(self,name,args={},additional_aliases=None):
		
		if not self._function_register:
			self.__startup()
		
		if name not in self._function_register:
			log.error(f"Function {name} was not in the register (did you forget to build it? re-build it and make sure the cache is clear). Skipping... ")
			return self
		#check the in-parameters. build the arguments list throwing errors if any are missing and not default 
		function_signature = self._function_register[name]
		
		parameters = function_signature['parameters']
		collected_parameters = []#use these later in the function calls 
		
		routine_name = function_signature['routine_name']
		
		#make the temp table name & type here and keep track of it! 
		temp_table_type = 'get'
		if routine_name.startswith('candles_'):
			temp_table_type = 'candles'
		if routine_name.startswith('values_'):
			temp_table_type = 'values'
		
		temp_table_name = temp_table_type +'_'+str(self._this_branch)+ '_' + str(len(self._temp_tables)) + '_tmp'
		prev_temp_table = self._temp_tables[-1] if len(self._temp_tables) else None 
			
		#for candles and values functions, first parameter is ALWAYS a temp table name
		if temp_table_type in ['candles','values'] and parameters[0]['type'].upper() != 'TEXT':
			log.error(f"Function {name} was not of the correct format- the first parameter should be a name for a temporary table containing {temp_table_type} Skipping...")
		
		temp_table_columns = self._create_temp_table_columns(function_signature,additional_aliases)
		temp_table = {'type':temp_table_type,'name':temp_table_name,'function':name,'branch':self._this_branch,'columns':temp_table_columns}
		self._temp_tables.append(temp_table)
		
		for param in (parameters[1:] if temp_table_type in ['candles','values'] else parameters):   
			#param->name, param->type and optional param->default
			if 'name' not in param:
				log.error(f"Function {name} - a parameter is missing its name. Skipping...")
				return self
			if 'type' not in param:
				log.error(f"Function {name} - a parameter is missing its type. Skipping...")
				return self
			arg_type = param['type'].upper()
			arg_value = None
			if arg_type not in self._type_map:
				log.error(f"Unrecognised sql type '{arg_type}' for function {name}. Add it to the _type_map! Skipping... ")
				return self
			
			py_type = self._type_map[arg_type]
			is_default = False
			if 'default' in param:
				arg_value = args.get(param['name'],None) #sql handles the default but we need to ensure for example the candle_offset does not go in days_back place
				if arg_value is None:
					is_default = True
					if py_type != datetime.datetime:
						arg_value = py_type(param['default'])#work? :/ 
					else:
						pdb.set_trace()
						raise NotImplementedError("I thought there were no default timestamps?")
			else:
				if param['name'] not in args:
					log.error(f"Missing argument {param['name']} for function {name}. Skipping... ")
					return self
				arg_value = args[param['name']]
			if arg_value is not None:
				if not type(arg_value) == self._type_map[arg_type]:
					log.error(f"Function {name} - argument {param['name']} '{arg_value}' is not of type '{py_type}' (sql type '{arg_type}'). Skipping...")
					return self
				collected_parameters.append({'name':param['name'], 'value':arg_value,'default':is_default}) #use is_default to take off the end arguments 
		chop_index = 0
		for i in range(len(collected_parameters)):#take off the tail 
			chop_index = i
			if not collected_parameters[-(i+1)]['default']:	
				break 
		if chop_index > 0:
			collected_parameters = collected_parameters[:-chop_index] #take off end default parameters
		call_details = {
			'routine_name':routine_name,
			'parameters':collected_parameters,
			'temp_table':temp_table,
			'prev_temp_table':prev_temp_table,
			'branch':self._this_branch,
			'additional_aliases':additional_aliases,
			'returns':temp_table_columns
		}
		self._call_queue.append(call_details)
		return self
		
	
	def branch(self): #tricks with temp table names here
		new_composer = DataComposer(self.cursor)
		new_composer._function_register = self._function_register
		#new_composer._prev_function_signature = None
		new_composer._call_queue = []
		new_composer._end_join_tables = [] #dont know what they are yet! 
		new_composer.cursor = self.cursor #needed?
		new_composer._temp_tables = self._temp_tables[-1:] #only keep last temp table - we will call from this one onwards 
		return new_composer
		
		
	def join(self,branches): #using temp table name trick, join result sets back together by row number 
		#add to function call queue
		#add the last tyemp table per branch to the join tables.
		last_table = self._temp_tables[-1]
		if last_table not in self._end_join_tables:
			self._end_join_tables.append(last_table)
		for branch in branches:
			branch_temps = branch._temp_tables[1:]
			self._call_queue += branch._call_queue
			self._temp_tables += branch_temps
			self._end_join_tables.append(branch._temp_tables[-1])
			
	
	def collect_by_date(self): #sql function or just plain ol' sql to group together all the result sets by date. 
		pass
		
	def result_join(self,other_results):
		pass #perhaps join together other results to this one by timestamp, not by row index --necessary?
	
	def result(self,aliases={},as_json=False): #'collect results up into rows the usual way (one per timestamp)
		#perform the query   
		#topper sql code ? 
		if len(self._end_join_tables) == 0:
			self._end_join_tables.append(self._temp_tables[-1])
		
		self.execute()
		
		columns = self.__get_result_columns(self._end_join_tables)
		columns_string = self.__get_result_columns_str(columns,aliases)
		
		sql_result_table = 'DROP TABLE IF EXISTS end_results_table_tmp CASCADE;\n' #delete old results
		sql_result_table += 'SELECT ' + columns_string + ' INTO end_results_table_tmp FROM ' + self._end_join_tables[0]['name'] + ' t0\n' #t0 is the root table
		table_joins = []
		for ti,end_table in enumerate(self._end_join_tables[1:]):	
			table_joins.append('JOIN '+end_table['name']+' t'+str(ti+1)+ ' ON t0.row_index = t'+str(ti+1)+'.row_index')
			
		sql_result_table += '\n'.join(table_joins)
		
		#pdb.set_trace()
		self.cursor.execute(sql_result_table,no_results=True) #do some kind of caching here to prevent executing twice? 
		
		returning_sql = ''
		if as_json:
			#do collection
			returning_sql = '''
			WITH create_json_blobs AS (
				SELECT the_date, full_name, row_to_json(end_results_table_tmp) as json_obj FROM end_results_table_tmp
			),
			collected_dates AS (
				SELECT the_date, count(1) as n, json_object_agg(full_name,json_obj)
				FROM create_json_blobs
				GROUP BY the_date 
			),
			max_row AS (
				SELECT MAX(n) AS should_be FROM collected_dates
			)
			SELECT cd.* FROM collected_dates cd, max_row
			WHERE cd.n = max_row.should_be
			ORDER BY the_date ASC
			'''
		else:
			returning_sql = 'SELECT * FROM end_results_table_tmp;' #doing some other thing without JSON then 
		
		
		self.cursor.execute(returning_sql)
		return [r for r in self.cursor.fetchall()]
	
	def	execute(self):	#execute up to this point in case we wnat to branch and then call different results? 
		#only call if the current temp_table has not been created - perhaps record this? 
		sql_code = self.to_sql()
		if sql_code.strip():
			#pdb.set_trace()
			self._sql_code = sql_code
			self.cursor.execute(sql_code,no_results=True)
			#clear function calls and start from current? 
			self._call_queue = self._call_queue[-1:] #keep only last call 
		else:
			log.debug(f"No sql code to run!")
		
	#find what the next function wants and marry up the column name nicely... 
	def __auto_alias(self,current_call,next_call):
		#for each returned result in this current call, ensure the alias will put it into value or into candle form 
		#then from these, create tuples eg ('rsi_value','value') which would become 'rsi_value AS value' 
		#return_parameters = current_call['returns'] 
		#current_call_return = current_call[]
		
		
		return_params = [(r['name'],r['type']) for r in current_call['returns']]
		#remove any parameters that are custom alias values 
		custom_aliases = current_call['additional_aliases']
		if custom_aliases:
			for i in reversed(range(len(return_params))):
				for (old_value,new_value) in custom_aliases.items():
					if return_params[i][0] == new_value: #remove it as it will be added as an alias (hopefully!) 
						if old_value not in [r[0] for r in return_params]:
							log.error(f"Function {current_call['routine_name']} unable to find alias old value '{old_value}' for alias '{new_value}'")
						else:
							del return_params[i]
		
		used_return_parameters = []
		return_parameter_list = []
		next_temp_table = None
		if next_call and next_call['branch'] == current_call['branch']:
			next_temp_table = next_call['temp_table']
		
		if next_temp_table is None:
			return_parameter_list = [(r[0],r[0]) for r in return_params] #nothing to do
		
		#if next_call['temp_table']['type'] == 'get':
		#	pdb.set_trace()
		
		if next_temp_table is not None:
			temp_table_format = self._temp_table_formats[next_temp_table['type']] #target format  
			target_name = {tf[0]:None for tf in temp_table_format} # new_name -> old_name. We reverse it afterwards. 
			target_type = {tf[0]:tf[1] for tf in temp_table_format}
			
			
			#generate from forward pass first for optimisation. then thread up afterwards for any missing values 
			for i in range(len(temp_table_format)):
				target_param = temp_table_format[i]
				return_param = return_params[i]
				if target_param == return_param:
					used_return_parameters.append(return_param[0])
					target_name[target_param[0]] = return_param[0]
			
			#now pass again look for exact matches
			for target_param in temp_table_format:
				if target_name.get(target_param[0]) is not None:
					continue #already have this parameter!
				for return_param in return_params:
					if return_param[0] in used_return_parameters:
						continue #already used this return parameter! we should use another one! 
					if target_param == return_param:
						used_return_parameters.append(return_param[0])
						target_name[target_param[0]] = return_param[0]
			
			#thirdly, pass again looking for similar words and same types 
			for target_param in temp_table_format:
				if target_name.get(target_param[0]) is not None:
					continue #already have this parameter!
				for return_param in return_params:
					if return_param[0] in used_return_parameters:
						continue #already used this return parameter! we should use another one! 
					if target_param[1] == return_param[1] and (target_param[0].startswith(return_param[0]) or return_param[0].startswith(target_param[0])):
						used_return_parameters.append(return_param[0])
						target_name[target_param[0]] = return_param[0]
			
			#lastly, pass through and just get the next matching type, hoping all the logically named stuff has been consumed. 
			for target_param in temp_table_format:
				if target_name.get(target_param[0]) is not None:
					continue #already have this parameter!
				for return_param in return_params:
					if return_param[0] in used_return_parameters:
						continue #already used this return parameter! we should use another one! 
					if target_param[1] == return_param[1]:
						used_return_parameters.append(return_param[0])
						target_name[target_param[0]] = return_param[0]
			
			return_parameter_list = [(target_name.get(tfm[0]),tfm[0]) for tfm in temp_table_format]
			
		if custom_aliases:
			for (old_name,new_name) in custom_aliases.items():
				#check old name exists first?
				return_parameter_list.append((old_name,new_name))
		
		for (old,new) in return_parameter_list:
			if old is None and next_temp_table is not None:	
				pdb.set_trace()
				log.error(f"Function {current_call['routine_name']} unable to find a mapping for parameter '{new}'")
		if any(r[1] == 'my_magic_value' for r in return_parameter_list):
			pdb.set_trace()
		
		return return_parameter_list
		
	#get the result coilumns for the join at the end using the last temp tables. 
	def __get_result_columns(self,result_temp_tables):
		#build a sensible list of columns from the temp tables given so we can join them together in the ending SQL query
		collected_columns = {} 
		for i,temp_table in enumerate(result_temp_tables):
			columns = temp_table['columns'] #get the current temp table i, and the columns. Append to collected columns and use the earlierst name collison each time to create the joins' column selection
			for column in columns:	
				has = collected_columns.get(column['name'],[])
				has.append({'column':column,'temp_table_index':i}) #temp tables will be aliased to t1 t2 t3 etc 
				collected_columns[column['name']] = has
		
		return_cols = []
		for column_name, columns in collected_columns.items():
			columns = sorted(columns,key=lambda c:c['temp_table_index'])
			return_cols.append(columns[0])
		
		return return_cols
	
	def __get_result_columns_str(self,columns,aliases={}):
		sql_column_strs = []
		for column in columns: 
			column_name = column['column']['name'] 
			t_alias = 't'+str(column['temp_table_index'])
			new_column_name = aliases.get(column_name)
			sql_column_strs += [t_alias+'.'+column_name + ((' AS ' + new_column_name) if new_column_name else '')]
		return ','.join(sql_column_strs)
		
	def to_sql(self):
		func_calls = self._call_queue + [None] #one none at the end 
		paired_calls = zip(func_calls[:-1],func_calls[1:])
		sql_lines = []
		
		for (this_call,next_call) in paired_calls:
			#construct the SQL here for each function call
			main_aliases = self.__auto_alias(this_call,next_call) #needs to look ahead! cant get rid of next_call :(
			function_parameters, sql_parameters = self.__param_list(this_call['parameters'])
			temp_table = this_call['temp_table'] if this_call else None
			prev_temp_table = this_call['prev_temp_table']
			
			
			#main_aliases += additional_aliases  #add these on at the end of the current aliases 
			keep_old = temp_table in self._end_join_tables
			
			sql_line =  'SELECT ' + self.__alias_sql(main_aliases,keep_old)
			if temp_table is not None:
				sql_line += ' INTO %(temp_table)s ' #create a temp table & keep track...  
				sql_parameters.update({'temp_table':Inject(temp_table['name'])})
			
			if prev_temp_table is not None and temp_table is not None and temp_table['type'] in ['values','candles']:
				function_parameters = '%(prev_table_name)s'+(',' if function_parameters else '')+function_parameters
				sql_parameters.update({'prev_table_name':prev_temp_table['name']})
			sql_line += ' FROM '+self._schema+'.'+this_call['routine_name']+'('+function_parameters+');' #previous temp table name
			sql_line = self.cursor.mogrify(sql_line,sql_parameters).decode()
			sql_lines.append(sql_line)

		
		temp_tables = [fc['temp_table'] for fc in func_calls if fc and fc['temp_table'] and fc['temp_table']['branch'] == self._this_branch]
		drop_if_exists_cascade = 'DROP TABLE IF EXISTS %(temp_table)s CASCADE;'
		drops = [self.cursor.mogrify(drop_if_exists_cascade,{'temp_table':Inject(t['name'])}).decode() for t in temp_tables]
		
		return '\n'.join(drops) + '\n' + '\n'.join(sql_lines)
	
	def __alias_sql(self,aliases,keep_old=True):
		parts = [a[0] if a[0] == a[1] else a[0] + ((','+ a[0]) if keep_old else '') +  ' AS ' + a[1] for a in aliases]
		return_str = ','.join(parts) 
		#now remove duplicates! 
		return self.__dedupe_aliases_sql(return_str)
		
	def __dedupe_aliases_sql(self,sql_str):
		parts_again = sql_str.split(',') 
		parts_again = list(set(parts_again))   #only removes singular column names not alias column names. Extend to also remove dupolicate aliases
		return ','.join(parts_again)
	
	def __param_list(self,parameters):
		sql_param_list = ','.join(['%('+p['name']+')s' for p in parameters])
		sql_params = {p['name']:p['value'] for p in parameters}
		return sql_param_list,sql_params
		
	def _create_temp_table_columns(self,function_signature,aliases):
		returns = [r for r in function_signature['returns']] #get the usual function returns 
		#now add to returns any alias types (as copies) 
		if aliases is not None:
			for old_name,new_name in aliases.items():
				found = False
				for r in returns:
					if r['name'] == old_name:
						s = dict(r)
						s['name'] = new_name
						returns.append(s)
						found = True
				if not found:
					log.error(f"Function {function_signature['name']} - alias {new_name} was not able to be linked to any return columns.")
		return returns 
	
	#convert a candle result into candles for indicators 
	@staticmethod 
	def as_candles(candle_result,instruments):
		return_dict = {} 	
		for instrument in instruments:
			try:
				return_dict[instrument] = sorted([
				[
					snapshot[2][instrument]['open_price'],
					snapshot[2][instrument]['high_price'],	
					snapshot[2][instrument]['low_price'],
					snapshot[2][instrument]['close_price'],
					snapshot[0] #the date should always go at the bottom of the candle
				]
				for snapshot in candle_result],key=lambda c:c[-1]) #sort into chronological order 
			except KeyError as ke:
				log.warning(f"Unable to find '{instrument}'.",exc_info=True)
				return_dict[instrument] = None 
		return return_dict
	
	@staticmethod 
	def as_volumes(volume_result,instruments):
		return_dict = {} 	
		for instrument in instruments:
			try:
				return_dict[instrument] = sorted([
				[
					snapshot[2][instrument]['bid_volume'],
					snapshot[2][instrument]['ask_volume'],	
					snapshot[0] #the date should always go at the bottom of the candle
				]
				for snapshot in candle_result],key=lambda c:c[-1]) #sort into chronological order 
			except KeyError as ke:
				log.warning(f"Unable to find '{instrument}'.",exc_info=True)
				return_dict[instrument] = None 
		return return_dict
	
	@staticmethod 
	def as_candles_volumes(candle_result,instruments):
		return_dict = {} 	
		for instrument in instruments:
			try:
				return_dict[instrument] = sorted([
				[
					snapshot[2][instrument]['open_price'],
					snapshot[2][instrument]['high_price'],	
					snapshot[2][instrument]['low_price'],
					snapshot[2][instrument]['close_price'],
					snapshot[2][instrument]['bid_volume'],
					snapshot[2][instrument]['ask_volume'],
					snapshot[0] #the date should always go at the bottom of the candle
				]
				for snapshot in candle_result],key=lambda c:c[-1]) #sort into chronological order 
			except KeyError as ke:
				log.warning(f"Unable to find '{instrument}'.",exc_info=True)
				return_dict[instrument] = None 
		return return_dict
	
	
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
	
	pip_map = {} 

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
		























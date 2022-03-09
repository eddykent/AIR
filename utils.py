# class for reading list files

import psycopg2
import datetime
import time
import hashlib
import pickle
import os

import numpy as np

#from collections import MutableSequence


from configparser import ConfigParser

import pdb
from psycopg2.extensions import AsIs as Inject
	
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
	
	@staticmethod
	def from_str_1(the_str):
		#09.03.2022 00:52:56
		a_date,a_time = the_str.split(' ')
		date_bits = [int(a) for a in  a_date.split('.')]
		time_bits = [int(a) for a in  a_time.split(':')]
		d,m,y = date_bits
		h,n,s = time_bits
		return datetime.datetime(y,m,d,h,n)
		
	@staticmethod
	def timestamp(the_time=None):
		if the_time is None:
			the_time = time.time()
		#get timestamp
		return datetime.datetime.utcfromtimestamp(the_time).strftime('%Y-%m-%d@%Hh%Mm%Ss')
		
	@staticmethod
	def datestamp(the_date=None):
		if the_date is None:
			the_date = datetime.datetime.now()
		#get datestamp
		return the_date.strftime('%Y-%m-%d@%Hh%Mm%Ss')
		
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
	
	
class Log:   ##learn how to use logger first
	pass

#allows for comments inside files that are simply a list of stuff. 
class ListFileReader:
	
	comment_tokens = ['--']
	errors=None
	
	def __init__(self):
		pass
	
	def read(self,filename):
		the_list = []
		lines = []
		with open(filename,'r',errors=self.errors) as f:
			lines = f.read().split('\n')
		for line in lines:
			for c in self.comment_tokens:
				line = line.split(c)[0]
			result_line = line.strip()
			if result_line:
				the_list.append(result_line)
		return the_list
	
	def read_full_text(self,filename):
		return '\n'.join(self.read(filename))
	
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
	query_cache_dir = 'pickles/datacache'
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
	
	def __init__(self,commit=False,cache=True):
		cfg = Configuration()
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
		return self.cur.mogrify(query,self.get_default_parameters(params))
	
	def execute(self,query,params):
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
				if self.cur.rowcount >= 0:
					try:
						self.rows = self.cur.fetchall()  #rsults in psycopg2.ProgrammingError if a query was ran with no results (eg update without returning) 
						with open(fullfilename,'wb') as f:
							
							pickle.dump(self.rows,f)
					except TypeError as te:
						if str(te) == "can't pickle memoryview objects":
							pass #we have  some raw bytes that pickle doesnt like. that's okay though we can continue without caching. 
						else:
							raise te #might be something else so best to propagate the error and not swallow it
							
		else:
			self.cur.execute(query,self.get_default_parameters(params))
			self.rows = self.cur.fetchall()
			
	def fetchall(self):
		return self.rows
	
	def close(self):
		self.cur.close()
		self.con.close()


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
		
		

def overrides(interface_class):
    def overrider(method):
        assert(method.__name__ in dir(interface_class)), "method {} is not overriden by {}".format(method.__name__,interface_class.__name__)
        return method
    return overrider
























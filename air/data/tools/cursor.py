

import datetime
import time
import hashlib
import pickle

import psycopg2
from psycopg2.extensions import AsIs as Inject

import logging
log = logging.getLogger(__name__)
#import pdb


from air.configuration import Configuration

##file for controls for the database - including database tools like cursors 


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
	
	default_parameters = { #eww - yes this needs to be removed 
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
		self.flush() #flush old result to prevent bugs
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
		
	def copy_from(self,*args,**kwargs):
		self.cur.copy_from(*args,**kwargs)
	
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
		function_register_query = ''
		with open(self._function_register_query_file,'r') as f:
			function_register_query = f.read()
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
	
	@staticmethod
	def as_full_candles(candle_result,instruments):
		return_dict = {} 	
		for instrument in instruments:
			try:
				return_dict[instrument] = sorted([
				[
					snapshot[2][instrument]['bid_open'],
					snapshot[2][instrument]['bid_high'],	
					snapshot[2][instrument]['bid_low'],
					snapshot[2][instrument]['bid_close'],
					snapshot[2][instrument]['ask_open'],
					snapshot[2][instrument]['ask_high'],	
					snapshot[2][instrument]['ask_low'],
					snapshot[2][instrument]['ask_close'],
					snapshot[2][instrument]['bid_volume'],
					snapshot[2][instrument]['ask_volume'],
					snapshot[0] #the date should always go at the bottom of the candle
				]
				for snapshot in candle_result],key=lambda c:c[-1]) #sort into chronological order 
			except KeyError as ke:
				log.warning(f"Unable to find '{instrument}'.",exc_info=True)
				return_dict[instrument] = None 
		return return_dict
	
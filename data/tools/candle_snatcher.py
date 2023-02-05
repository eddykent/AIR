
#maybe?
import datetime
import time
import psycopg2
from collections import namedtuple
import pdb


import multiprocessing
from multiprocessing import Process, Queue

####purpose of this file: 
# make a pool of selenium handlers that are all running. Use this pool to then pull data from the internet via X. 
# this file might also use/benefit from a proxy so that we do not get banned when pulling data from X. This is 
# something worth thinking about asap but for now I am focusing on functionality. 
#


#my own imports
from web.crawler import SeleniumHandler
from web.crawler import WebDriverException 
from data.tools.dukascopy import Dukascopy
from utils import Configuration, Database

now = datetime.datetime.now()
NOW = datetime.datetime(now.year,now.month,now.day,now.hour,now.minute)



#async? 
#class CandleSnatcher


#class NoDaemonProcess(multiprocessing.Process):
#    @property
#    def daemon(self):
#        return False
#
#    @daemon.setter
#    def daemon(self, value):
#        pass

class DataWorker():
	
	task_queue = None 
	worker_num = None
	credentials = None
	dukascopy = None
	max_attempts = 5
	#browser_threads = None
	
	#def __init__(self,worker_num,task_queue):
	def __init__(self, worker_num,credentials):
		self.worker_num = worker_num
		#self.task_queue = task_queue
		self.credentials = credentials
		#self.browser_threads = browser_threads
	
	def set_task_queue(self,task_queue):
		self.task_queue = task_queue
	
	def run(self):
		
		#need proxy! 
		#need to be headless! (caused file system issues)
		hidden = False
		cursor = Database(commit=True, cache=False)
		selenium_handle = SeleniumHandler(hidden=hidden) #hidden=True?, proxy=? 45.79.110.81
		selenium_handle.start() 	
		
		self.dukascopy = Dukascopy(selenium_handle,
			credentials=self.credentials,
			cursor=cursor)
		self.dukascopy.begin()
		
		looping = True
		
		while looping:
			task = self.task_queue.get() #get the next task
			
			if task is not None:
				try:
					self.worker_func(task)
					
				except WebDriverException as wde:
					
					#restart - perhaps a page failed to load
					selenium_handle.finish()
					
					selenium_handle = SeleniumHandler(hidden=hidden) #hidden=True?, proxy=? 45.79.110.81
					selenium_handle.start() 	
					
					self.dukascopy = Dukascopy(selenium_handle,
						credentials=self.credentials,
						cursor=cursor)
					self.dukascopy.begin()
					
					#and re-add the task as it is probably not finished
					self.task_queue.put(task)
				
				except OSError as ose:
					
					#restart - perhaps a download failed
					selenium_handle.finish()
					
					selenium_handle = SeleniumHandler(hidden=hidden) #hidden=True?, proxy=? 45.79.110.81
					selenium_handle.start() 	
					
					self.dukascopy = Dukascopy(selenium_handle,
						credentials=self.credentials,
						cursor=cursor)
					self.dukascopy.begin()
					
					#and re-add the task as it is probably not finished
					self.task_queue.put(task)
				
				except Exception as e:
					print(e) 
					#pdb.set_trace()
					print('Something else went wrong')
					raise e
					
			else:
				looping = False #exit loop 
				
			#? 
			self.task_queue.task_done()	#indicate a task was done 	
			 
		
		cursor.close()
		selenium_handle.finish()
	
	#get the instrument and dates from task. Run web crawler and get data
	#if there are rectify tasks to fix errors and we have only attempted a few times, 
	#add these back to the task queue
	def worker_func(self, task):
		attempt = task['attempt']
		instrument = task['instrument']
		self.dukascopy.set_gets([instrument],task['date_from'],task['date_to'],attempt)
		rectify_tasks = self.dukascopy.perform()
		#data = self.dukascopy.get_full_data(instrument)
		#data = self.dukascopy.fix_end_volumes(data)
		#self.dukascopy.upload_to_database(data,instrument)
		if rectify_tasks:
			if attempt < self.max_attempts: #try 5 times
				#add new tasks 
				for new_task in rectify_tasks: #put the rectify tasks onto the queue 
					self.task_queue.put({'date_from':new_task[0],'date_to':new_task[1],'instrument':instrument,'attempt':attempt+1})
			else: 
				log.warning(f"Leaving {len(rectify_tasks)} tasks unfinished and exiting due to too many attempts")
		
		
		#if not rectify_tasks or attempt >= self.max_attempts: #handled outside
		#	self.task_queue.put(None) #flag this (or other!) worker for completion. 
			
	def __call__(self,**kwargs): #absorb args
		self.run()


class CandleSnatcherDukascopy: #consider super later if needed 
	
	pool_size = 1
	#browser_threads = None #store available browsers 
	worker_pool = []
	browser_threads = []
	startup_wait = 2 # wait this long to ensure no spam of dukascopy and disconnect 
	
	task_queue = None #store all data processing tasks 
	
	def __init__(self, pool_size=None):
		if pool_size is not None:
			self.pool_size = pool_size
	
	#make a load of selenium handlers and put them in the pool 
	def setup(self,configs=[]):
		#account setups
		config = Configuration() #use configs 
		username = config.get('dukascopy','username')
		password = config.get('dukascopy','password')
		credentials = {'username':username, 'password':password} 
		
		
		for i in range(self.pool_size):
			#setup selenium objects here
			worker = DataWorker(i,credentials)
			self.worker_pool.append(worker)
			#pass
		
		#put into worker threads? 		
		
	
	def perform(self,instruments,date_from,date_to=NOW):
		
		self.setup()
		
		self.browser_threads = [] #flat list of available browsers 
		manager = multiprocessing.Manager()
		self.task_queue = manager.Queue() 
		
		#start threads 
		for instrument in instruments: 
			self.task_queue.put({'instrument':instrument,'date_from':date_from,'date_to':date_to,'attempt':1})
			#if self.startup_wait: #wait in task queue too to prevent spam? 
			#	time.sleep(self.startup_wait) 
		
		for worker in self.worker_pool:
		#or i in range(self.pool_size):
			#worker = CandleTaskProcess(i,self.task_queue)
			worker.set_task_queue(self.task_queue)
			browser_thread = Process(target=worker,args={})
			browser_thread.start()
			self.browser_threads.append(browser_thread)
			if self.startup_wait:
				time.sleep(self.startup_wait) 
		
		
		##should now be running all at once
		#wait until completion 
		while not self.task_queue.empty():
			time.sleep(1) #keep checking if  the queue is empty or not and when it is, tear down 
		
		self.tear_down() 
		
		
	def tear_down(self):
		print('TEAR DOWN CALLED')
		
		for worker in self.browser_threads: 
			self.task_queue.put(None) #flag a worker to finish
			
		for worker in self.browser_threads: 
			worker.join() 
		
		
			
	
	
	
	




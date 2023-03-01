
#from a load of links from News, get all the news stories (multiprocess) and put them into the database
class NewsSnatcher:
	
	pool_size = 1
	#browser_threads = None #store available browsers 
	worker_pool = []
	browser_threads = []
	startup_wait = 0.5 # wait this long to ensure no spam of dukascopy and disconnect 
	
	news_queue = None #store all data processing tasks 
	news_results = None
	
	def __init__(self, pool_size=None):
		if pool_size is not None:
			self.pool_size = pool_size
	
	#make a load of selenium handlers and put them in the pool 
	def setup(self,configs=[]):
		#account setups
		config = Configuration() #use configs 
		username = config.get('dukascopy','username')
		password = config.get('dukascopy','password')
		fetch_details = {'username':username, 'password':password} 
		
		
		for i in range(self.pool_size):
			#setup selenium objects here
			worker = NewsFetchWorker(i,credentials)
			self.worker_pool.append(worker)
			#pass
		
		#put into worker threads? 		
		
	def get_instruments(self,instruments,date_from,date_to=NOW):
		
		start_tasks = [] 
		
		for instrument in instruments:
			start_tasks.append({'instrument':instrument,'date_from':date_from,'date_to':date_to})
		self.perform(start_tasks)
			
	def perform(self,news_tasks):
		
		self.setup()
		
		self.browser_threads = [] #flat list of available browsers 
		manager = multiprocessing.Manager()
		self.news_queue = manager.Queue() 
		self.news_results = manage.Queue()
		
		
		
		for news_task in news_tasks: 
			self.news_queue.put(news_task)

		#start threads 
		for worker in self.worker_pool:
		#or i in range(self.pool_size):
			#worker = CandleTaskProcess(i,self.task_queue)
			worker.set_queues(self.news_queue,self.news_results)
			
			#worker()#for debugging 
			
			browser_thread = Process(target=worker,args={})
			browser_thread.start()
			self.browser_threads.append(browser_thread)
			if self.startup_wait:
				time.sleep(self.startup_wait) 
		
		
		##should now be running all at once
		#wait until completion 
		while not self.news_queue.empty():
			time.sleep(1) #keep checking if  the queue is empty or not and when it is, tear down 
		
		self.tear_down() 
	
	def tear_down(self):
		#print('TEAR DOWN CALLED')
		
		for worker in self.browser_threads: 
			self.news_queue.put(None) #flag a worker to finish
			
		for worker in self.browser_threads: 
			worker.join() 
	
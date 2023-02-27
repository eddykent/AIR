import multiprocessing 
from multiprocessing import Queue, Manager


class ProcessWorker:
	
	task_queue = None 
	result_queue = None 
	worker_num = None
	
	def __init__(self, worker_num):
		self.worker_num = worker_num
	
	def __call__(self,*args,**kwargs): #swallow kwargs 
		self.run() 
	
	def set_task_queue(self,task_queue):
		self.task_queue = task_queue
	
	def set_result_queue(self,result_queue):
		self.result_queue = result_queue
	
	def run(self):	
		
		self.pre_loop()
		
		looping = True 
		while looping:
			task = self.task_queue.get()
			if task:
				result = self.perform_task(task)
				if self.result_queue:
					self.result_queue.put(result)
			else:
				looping = False
			self.task_queue.task_done() 
		
		self.post_loop() 
	
	def pre_loop(self):
		pass
	
	def post_loop(self):
		pass
	
	def perform_task(self,task):
		raise NotImplementedError('This method must be overridden') 
	

class ProcessPool:
	
	worker_pool = []
	
	pool_processes = []
	task_queue = None #store all data processing tasks 
	result_queue = None 
	
	def __init__(self, pool_size=None):
		if pool_size is not None:
			self.pool_size = pool_size
	
	#make a load of selenium handlers and put them in the pool 
	def pass_workers(self,workers):
		self.worker_pool = workers
		
	def perform(self,process_tasks):
		
		self.pool_processes = [] #flat list of available browsers 
		manager = multiprocessing.Manager()
		self.task_queue = manager.Queue()
		self.result_queue = Queue()
		
		#start threads 
		for process_task in process_tasks: 
			self.task_queue.put(process_task)
		
		for worker in self.worker_pool:
		#or i in range(self.pool_size):
			#worker = CandleTaskProcess(i,self.task_queue)
			worker.set_task_queue(self.task_queue)
			worker.set_result_queue(self.result_queue)
			
			pool_process = Process(target=worker,args={})
			pool_process.start()
			
			self.pool_processes.append(pool_process)
			
			if self.startup_wait:
				time.sleep(self.startup_wait) 
		
		##should now be running all at once
		#wait until completion 
		while not self.task_queue.empty():
			time.sleep(1) #keep checking if  the queue is empty or not and when it is, tear down 
		
		self.tear_down() 
		
		#return results somehow 
		return [r for r in self.result_queue]
	
	def tear_down(self):
		#print('TEAR DOWN CALLED')
		
		for worker in self.pool_processes: 
			self.task_queue.put(None) #flag a worker to finish
			
		for worker in self.pool_processes: 
			worker.join() 
		












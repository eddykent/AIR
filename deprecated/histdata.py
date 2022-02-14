
import psycopg2
import datetime


import pdb

# this class is responsible for gathering data from the database and then 
# preparing it into a format that is easy to use in an ARIMA model or an 
# ANN. This includes sectioning the data into subsequences and also getting
# the win and loss cases from the data. 
#
# ASSUME : One sequence per day (any more polutes the learning algorithm (*))	
#	 : There are no holes in the data (no days where the price is missing/null)
#	 : A win/loss is when a particular amount of change has happened, determined
#	   by the average movement for each currency pair
#
# TIMESTAMPED: When splitting into subsequences, if the sequence is timestamped 
# 	then the date is used to anchor each sequence. Otherwise, 24*4 is used as 
#	there are 24*4 quarter-of-an-hours in a day and each subsequence should 
#	start at the same time each day. 
#
#
#
#
# * The previous version was able to do more than 1 sequence per day but results
# 	were always worse. So once per day is better since we can take advantage of 
# 	the current time of day

class HistData:
	
	query_file = './queries/candles_with_percent_change.sql'
	the_date = datetime.datetime.now()
	n_sequences = 100
	sequence_length_days = 6
	raw_data = [] 
	
	def __init__(self,fx_pairs):
		self.raw_data = []
		self.fx_pairs = fx_pairs
		
	def read(self,the_date,n_sequences,sequence_length_days):#
		self.the_date = the_date
		self.n_sequences = n_sequences
		self.sequence_length_days = sequence_length_days
		
		sql_string = ""
		with open(self.query_file,'r') as f:
			sql_string = f.read()
		
		days_back = (sequence_length_days + n_sequences)*1.4 + 10 # 10 is just a buffer to ensure we got enough data
					#the 1.4 is so that we account for weekends 
		con = psycopg2.connect("host='localhost' user='postgres' password='0o9i8u7y' dbname='TradeData'")
		cur = con.cursor()
		cur.execute(sql_string,{'the_date': self.the_date.date(),'hour':self.the_date.hour ,'days_back':days_back ,'pairs':self.fx_pairs})

		self.raw_data = cur.fetchall()[1:] #chop first entry off - it isn't complete
		with open('./queries/previous_query.txt','w') as f:
			f.write(cur.query.decode())
		cur.close()
		con.close()
	
	#if data is missing, the whole candle will be omitted for every currency pair. 
	#thus, every sequence datetimes will be identical for every pair 
	def get_data_sequences(self,pairs=[],keys=["close_percent_change"],timestamped=True):
		if not pairs:
			pairs = self.fx_pairs
		pcs = {}
		missing_quarts = 0 
		for snap in self.raw_data:
			snapshot = snap[1]
			this_date = snap[0]
			if not all((snapshot.get(p) for p in pairs)): #if we dont have all pairs, skip this candle
				missing_quarts += 1
				continue
			for pair in pairs:
				datum = snapshot.get(pair) #potential fail here - if this particular time has no reading for this pair
				pc = [datum[k] for k in keys]
				if timestamped:
					pc.append(this_date)
				pc_list = pcs.get(pair,[])
				pc_list.append(pc)
				pcs[pair] = pc_list
		#pdb.set_trace()
		return pcs
	
	def get_candles(self,pairs=[],timestamped=True): #useful for any indicators (o,h,l,c,date) 
		if not pairs:
			pairs = self.fx_pairs
		return self.get_data_sequence(pairs,keys=['open_price','high_price','low_price','close_price'],timestamped=timestamped)
	
	def split_sequence_into_subsequences(self,sequence,timestamped=True): #sequence is of just one! not dict of all pairs/instruments
		start_pos = [] # start position for every subsequence we will use in the dataset
		if timestamped: 
			#first, get index of every this hour on each day
			working_date = self.the_date
			for i in range(0,len(sequence)):
				sequim = sequence[i]
				this_date = [t for t in sequim if type(t) == datetime.datetime][0]
				if this_date < working_date:
					#pdb.set_trace()
					if this_date.weekday() == 4 and this_date.hour >= 21 and this_date.minute >= 30:
						pass
					elif this_date.weekday() == 5:
						pass
					elif this_date.weekday() == 6 and this_date.hour < 22:
						pass
					else:
						start_pos.append(i)
					working_date -= datetime.timedelta(days=1)#over the weekend there are no candles  
					#check if working_date in the break period
					#just remove fridays after 21h or sunday earlier than 22h
			#pdb.set_trace()
		else:
			start_pos = list(range(0,len(sequence),24*4)) #split by every 24*4 entries
		#pdb.set_trace()
		sequence_length_15m = self.sequence_length_days * 4 * 24
		subsequences = [sequence[sp:sp+sequence_length_15m] for sp in start_pos][:self.n_sequences] #nasty! :(
		return subsequences
	

#class to determine what is to be predicted and what is sourced (X,Y) as well as how Y is calculated 
class DataXY:	
	
	quarts = 24*4 # number of candles/points to use for Y (quarter-of-an-hours)
	win_function = None
	
	def __init__(self,win_function):
		self.win_function = win_function
	 
	
	def getXY(self,sequence):
		Y_head = sequence[:self.quarts][::-1] #reverse
		X = sequence[self.quarts:][::-1] #reverse (latest->earliest) -> (earliest->latest)
		return X, self.win_function(Y_head)
		
def is_buy_win(y_data,average_movement,good_bound,bad_bound):	
	start = y_data[0][0]
	for d in y_data:
		if d[2] <= start - average_movement * bad_bound:  #check index? 
			#lose
			return -1
		elif d[1] >= start + average_movement * good_bound:
			#win
			return 1
	return 0

def is_sell_win(y_data,average_movement,good_bound,bad_bound):	
	start = y_data[0][0]
	for d in y_data:
		if d[1] >= start + average_movement * bad_bound: 
			#lose
			return -1
		elif d[2] <= start - average_movement * good_bound:
			#win
			return 1
	return 0

#pdb.set_trace()
#hd = HistData(['EUR/GBP','USD/JPY','AUD/CHF'])
#hd.read(datetime.datetime(2020,5,12,15,0),100,5)
#sequences = hd.get_data_sequences(keys=['open_price','close_price'])
#subsequences = hd.split_sequence_into_subsequences(sequences['EUR/GBP'])














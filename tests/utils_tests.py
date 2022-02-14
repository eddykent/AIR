
import datetime 
import pdb
import pickle

#hack to allow our test to import from parent directory
from sys import path
path.append('..')

from utils import TimeZipper, SplitAndPrepare


the_date = datetime.datetime(2022,1,15,10,0)

sequence_length_days = 10
N_HOURS_IN_DAY = 24

sample_x = [(the_date - datetime.timedelta(hours=i),i) for i in range(0,N_HOURS_IN_DAY*sequence_length_days)]
sample_y = [(the_date - datetime.timedelta(days=i),i) for i in range(0,sequence_length_days)]

with open('pickles/test_data.pickle','rb') as f: 
	sample = pickle.load(f)
	sample_x = sample['x']
	sample_y = sample['y']


tz = TimeZipper()
tz.n_sequences = 220
tz.x_sequence_lengths = [24*5]
Xs, Y = tz.process([sample_x],sample_y)

	
sap = SplitAndPrepare() 
sap.test_size = 10
sap.validation_size = 10
sap.instruments = ['AUD/CAD','GBP/USD','CHF/JPY']
sap.features = ['BUY']
sap.sequential = False
train_y, validate_y, test_y = sap.prepare(Y)
pdb.set_trace()



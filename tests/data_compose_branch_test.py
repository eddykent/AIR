
import datetime 

import pdb

from utils import Database, DataComposer 

result = []
rsi_result = [] 

this_date = datetime.datetime(2022,3,7)

with Database(commit=False, cache=False) as cursor: 
	composer = DataComposer(cursor) #.candles(params).call()...
	composer.call('get_candles_from_currencies',{'currencies':['AUD','USD','JPY'],'this_date':this_date,'days_back':100})
	composer.call('close_price')
	composer.call('relative_strength_index',{'period':14})
	composer.call('currency_strength')
	branch1 = composer.branch()
	
	composer.call('simple_moving_average',{'period':3})
	composer.call('instrument_ranking')
	 
	branch1.call('exponential_moving_average',{'period':5},{'ema_value':'value'}) #need to figure out why {'ema_value':'value'} is required?
	branch2 = branch1.branch()
	
	branch2.call('simple_moving_average',{'period':2},{'sma_value':'my_magic_value'})
	
	composer.join([branch1,branch2])
	result = composer.result(as_json=True)



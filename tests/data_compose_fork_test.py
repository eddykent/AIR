
import datetime 

import pdb

from utils import Database, DataComposer 

result = []

this_date = datetime.datetime(2022,3,7)

with Database(commit=False, cache=False) as cursor: 
	composer = DataComposer(cursor) #.candles(params).call()...
	composer.call('get_candles_from_currencies',{'currencies':['AUD','USD','JPY'],'this_date':this_date,'days_back':100})
	composer.call('close_price')
	composer.call('relative_strength_index',{'period':14})	
	composer.execute() #must build the temp tables ready for the branch 

	rsi_branch = composer.branch()
	#rsi_branch.call('simple_moving_average',{'period':1})
	rsi_result = rsi_branch.result(as_json=True)
	#should be able to get rsi separate from currency strength 
	
	
	composer.call('currency_strength')
	cs_branch = composer.branch()
	
	composer.call('exponential_moving_average',{'period':3})
	ecs_branch = composer.branch()
	
	composer.call('instrument_ranking')
	
	
	composer.join([cs_branch,ecs_branch])
	result = composer.result(as_json=True)
	



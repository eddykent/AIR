
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
	



'''
--TEST
DROP TABLE IF EXISTS candles_tmp CASCADE;
DROP TABLE IF EXISTS close_prices_tmp CASCADE; 
DROP TABLE IF EXISTS rsi_tmp CASCADE; 
DROP TABLE IF EXISTS currency_strengths_tmp CASCADE;
DROP TABLE IF EXISTS simple_moving_averages_tmp CASCADE;
SELECT * INTO candles_tmp FROM get_candles_from_currencies(ARRAY['EUR','USD','JPY','AUD','NZD','CAD','CHF','GBP'], '07 Mar 2022 12:30:00'::timestamp, 100, 15);
SELECT row_index, full_name, the_date, close_price AS value INTO close_prices_tmp FROM candles_close_price('candles_tmp');
SELECT row_index, full_name, the_date, rsi AS value INTO rsi_tmp FROM values_relative_strength_index('close_prices_tmp', 14, 1);
SELECT row_index, currency AS full_name, the_date, currency_strength AS value INTO currency_strengths_tmp FROM values_currency_strength('rsi_tmp');
SELECT row_index, full_name, the_date, value INTO simple_moving_averages_tmp FROM values_simple_moving_average('currency_strengths_tmp',3);
SELECT * FROM values_instrument_ranking('simple_moving_averages_tmp');
'''


import datetime

import pdb 
assert __name__ != '__main__', 'use run_test.py'
from web.broker import Trading212
from web.crawler import SeleniumHandler


from setups.trade_setup import TradeSignal, TradeDirection

instrument_eurusd = []
instrument_eurgbp = []


trade_id1 = 'POS891224840'
trade_id2 = 'POS890555658'
close_trade = 'POS892089212'
missing_id = 'banana'
#acc_info = 

trade_info = []
signal = TradeSignal()
signal.the_date = datetime.datetime.now()
signal.strategy = 'testing bot' 
signal.instrument = 'GBP/USD'  
signal.direction = TradeDirection.BUY 
signal.entry = None #the entry price to start 
signal.take_profit_distance = 0.003 
signal.stop_loss_distance = 0.002
signal.length = 1440 #1440 minutes in 24 hours


new_tp = 1.13
new_sl = 1.09

#we need to make this file test everything - add a few pending orders and a few other things then query them and remove them etc 
with SeleniumHandler(hidden=False) as sh:
	t212 = Trading212(sh)
	t212.begin()
	#input() #wait 
	
	#t212.pull_the_plug() #needs retesting 
	#trades = t212.get_live_trades()
	#instrument_eurusd = t212.get_instrument_info('EUR/USD') 
	#instrument_eurgbp = t212.get_instrument_info('EUR/GBP') 
	
	#acc_info = t212.get_account_info()
	#trade_info = t212.get_historic_trades([trade_id1,missing_id,trade_id2])
	
	#print('opening trade')
	succ, trade_position_id = t212.place_trade(signal,1000)
	#pending_trades = t212.get_pending_trades()
	#closing 
	#
	#print('close trade')
	#t212.close_trade('POS897104712')
	#t212.update_trade('POS897104785',new_tp,new_sl)
	pdb.set_trace()
	
	print("reached here without breaking!")
	
	#get live trades
	#...
	#get a trade - even if it is in closed trades
	#...
	#add a trade - make sure to be on demo :)
	#...
	#remove all the trades 
	#...
	
	t212.finish()
	

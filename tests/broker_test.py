

import datetime

import pdb 
assert __name__ != '__main__', 'use run_test.py'
from web.broker import Trading212
from web.crawler import SeleniumHandler


from trade_setup import TradeSignal, TradeDirection

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
signal.instrument = 'USD/JPY'  
signal.direction = TradeDirection.SELL 
signal.entry = None #the entry price to start 
signal.take_profit = 0.1  
signal.stop_loss = 0.1 
signal.length = 1440 #1440 minutes in 24 hours




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
	
	print('opening trade')
	trade_position_id = t212.place_trade(signal)
	
	pdb.set_trace()
	
	print('close trade')
	t212.close_trade(trade_position_id)
	
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
	

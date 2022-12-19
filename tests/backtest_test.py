

import pickle

from backtest import BackTesterDatabase, TradeSignal, TradeResult, TradeDirection, BackTestStatistics 
from utils import ListFileReader, TimeHandler, Database


lfr = ListFileReader()

bts = True
if not bts:
	mock_signals_file = 'mocks/signals.csv'
	mock_signals_dicts = lfr.read_csv(mock_signals_file)
	for msd in mock_signals_dicts:
		msd['the_date'] = TimeHandler.from_str_1(msd['the_date'],date_delimiter='/')
		msd['direction'] = TradeDirection.BUY if msd['direction'] == 'BUY' else TradeDirection.SELL if msd['direction'] == 'SELL' else TradeDirection.VOID
		msd['entry'] = float(msd['entry'])
		msd['take_profit_distance'] = float(msd['take_profit_distance'])
		msd['stop_loss_distance'] = float(msd['stop_loss_distance'])
		msd['length'] = int(msd['length'])

	mock_signals = [TradeSignal.from_full(**msd) for msd in mock_signals_dicts]

	cursor = Database(cache=False,commit=False)
	btd = BackTesterDatabase(cursor)
	result = btd.perform(mock_signals)

else:
	with open('data/pickles/backtestdata.pkl','rb') as f:
		(tsd,signals,result) = pickle.load(f)
		
	bts = BackTestStatistics(tsd, signals, result)
	some_result = bts.calculate()
	print(some_result)
	
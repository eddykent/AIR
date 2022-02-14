import pickle
import psycopg2
import datetime

import plotly.express as px

import pdb

from trade_schedule import TradeSchedule, CurrencyStrengthFilter, RSIFilter, MAFilter, MACDFilter, BollingerBandsFilter
from utils import Configuration, ListFileReader, TimeZipper, Database



lfr = ListFileReader()
currencies = lfr.read('fx_pairs/currencies.txt')
fx_pairs = lfr.read('fx_pairs/fx_mains.txt')

config = Configuration()
cur = Database()
#con = psycopg2.connect(config.database_connection_string())
#cur = con.cursor()

weekday_numbers = [0,1,2,3,4] #change to suit 

query = ''
with open('queries/auto_regression.sql','r') as f:
	query = f.read()

hours = [8,12,16] #[8, 12, 16]#try 0? #which time is most/least profitable?
number_tests = 200
days_back = int(number_tests * 1.5) #approx
all_days = [datetime.datetime(2022,1,28,0,0) - datetime.timedelta(days=x) for x in range(0,days_back)]
weekdays = [d for d in reversed(all_days) if d.weekday() in weekday_numbers]
sessions = [d for day in weekdays for d in [day+datetime.timedelta(hours=h) for h in hours]]

n_trades_per_session = 10

stop_loss = 7
take_profit = 7
parameters = config.get_default_parameters()
parameters.update({
	'the_date':sessions[-1], #start with latest data and use the stream to run tests on 
	'hour':sessions[-1].hour,
	'days_back':days_back + 80, #put some extra back to ensure we get consistency (so it fits in correlation window)
	'chart_resolution':240,
	'correlation_lags':12,#default 12
	'correlation_window':100, #default 100
	'correlation_threshold':0.2,#default 0.3
	'currencies':currencies
})

cur.execute(query,parameters)
raw_correlation_data = cur.fetchall()

query2 = ''
with open('queries/currency_strength_diff_auto_regression_rsi.sql','r') as f:
	query2 = f.read()

parameters.update({
	'relative_strength_index_period':14,
	'diff':1, 
	'ema_window':3,
	'chart_resolution':240
})

cur.execute(query2,parameters)
currency_strengths = cur.fetchall()

pdb.set_trace()

##ema stuff? or RSI etc? 
parameters.update({
	'chart_resolution':240
})

query3 = ''
with open('queries/candles_and_indicators.sql','r') as f:
	query3 = f.read()

cur.execute(query3,parameters)
raw_indicator_data = cur.fetchall()

tz = TimeZipper()
tz.number_of_sequences = number_tests
tz.x_sequence_lengths = [1,1,1,2]
#tz.overlap = True #only matters when using larger timeframes?
Xs, sessions = tz.process([raw_correlation_data,raw_indicator_data,currency_strengths,raw_indicator_data],[[s] for s in sessions])
#results_zipped = zip(Xs[0][:-1],Xs[1][:-1],Xs[2][1:],Xs[3][:-1],sessions) #use the actual currency strength of this session - might be predictable 
#results_zipped = zip(Xs[0],Xs[1],Xs[2],sessions)

results_zipped = zip(Xs[0],Xs[1],Xs[2],Xs[3],sessions)


#pdb.set_trace()

all_results = []
result_counts = []
cumulative_wins = 0
cumulative_profit_factor = 0
total_wins = 0
total_loses = 0
total_trades = 0

cur.cache = False #dont cache result files 

for result_z in results_zipped:	
	#try:
		#pdb.set_trace()
		result, snapshot_, currency_strength, snapshots_, the_date_ = result_z
		the_date = the_date_[0]#y has been wrapped nicely into singleton lists...
		data_start_date, N, prediction = result[0] #0 as x is treated as a sequence in TimeZipper
		data_start_date2, N2, currency_strengths = currency_strength[0]
		data_start_date3, N3, snapshot = snapshot_[0]
		snapshots = [ss[2] for ss in snapshots_]
		trade_deltas = [(pair,prediction[pair]['delta']) for pair in fx_pairs]
		ts = TradeSchedule(the_date)
		ts.take_profit_factor = take_profit
		ts.stop_loss_factor = stop_loss
		ts.build_from(trade_deltas,'delta_tuples')
		
		#set up some filters to try mitigate loses 
		csfilter = CurrencyStrengthFilter(currency_strengths,fx_pairs) 
		csfilter.tolerance = 2#2
		rsifilter = RSIFilter(snapshot,fx_pairs)
		rsifilter.boundary = 0.2 #.2 is best result 
		
		stochfilter = RSIFilter(snapshot,fx_pairs)
		stochfilter.rsi_key = 'stochastic_oscillator_d'
		stochfilter.boundary = 0.2
		
		smafilter = MAFilter(snapshot,fx_pairs)
		smafilter.ma_key = 'ema200'
		ts.trades = ts.trades[:n_trades_per_session]
		n_trades_before = len(ts.trades)
		
		macdfilter = MACDFilter(snapshots,fx_pairs)
		macdfilter.fast_key = 'macd_line'
		macdfilter.slow_key = 'macd_signal'
		
		bbfilter = BollingerBandsFilter(snapshot,fx_pairs)
		bbfilter.upper_key = 'bollinger_band_upper'
		bbfilter.lower_key = 'bollinger_band_lower'
		
		#ts.trades = macdfilter.filter(ts.trades)
		
		ts.trades = csfilter.filter(ts.trades) #comment out to stop filtering
		#ts.trades = smafilter.filter(ts.trades)
		#ts.trades = rsifilter.filter(ts.trades)#remove high-rsi trades
		#ts.trades = stochfilter.filter(ts.trades) #remove high-stoch trades 
		#ts.trades = bbfilter.filter(ts.trades)
		
		
		
		n_filtered = n_trades_before - len(ts.trades)
		trade_result = ts.run_test(cur)
		all_results.append(trade_result)
		wins = len([t for t in trade_result if t[3] == 'WON'])
		loses = len([t for t in trade_result if t[3] == 'LOST'])
		print('%(the_date)s - %(n_filtered)s Filtered, %(wins)s WINS, %(loses)s LOSES.' % {'n_filtered':n_filtered,'the_date':the_date,'wins':wins,'loses':loses})
		result_counts.append(wins - loses)
		cumulative_wins += (wins - loses)
		cumulative_profit_factor += take_profit*wins - stop_loss*loses
		total_wins += wins
		total_loses += loses
		total_trades += len(ts.trades) 
	#except Exception as e:
	#	print('%(the_date)s - FAILED - '+str(e) % {'the_date':the_date})

print('cumulative wins/profit: %(wins)s/%(profit)s' % {'wins':cumulative_wins,'profit':cumulative_profit_factor})
pdb.set_trace()


#28 / 1 / 2022
#tp/sl 7/7
#79/553 without filter!
#31/217 with filter - currency_strength_rsi(ranked_avereage)
#52/364 with filter - currency_strength_rsi(rank)
#53/371 with filter - RSI(0.15) and EMA
#       with filter - EMA(ema200)
#91/637 with filter - RSI(0.15) 
#93/657 with filter - RSI(0.2)
#69/483 with filter - Stoch_k(0.2)

#macd filter -- not worth it? 
#total_trades = 1980 - 1925 => 55 filtered
#total_wins = 921 - 891  => 30 wins filtered!
#total_loses =  889 - 869 => 20 loses filtered!

#rsi filter 
#total_trades = 1980 - 1969 => 11 filtered
#total_wins = 921 - 918 => 3 wins filtered!
#total_loses =  889 - 882 => 7 loses filtered



#currency strength filter (tolerance 1)
#total_trades = 1980 - 1059 => 921 filtered
#total_wins = 921 - 476 => 445 wins filtered
#total_loses =  889 - 475 => 414 loses filtered! 

#currency strength filter (tolerance 2)
#total_trades = 1980 - 1286 =>  filtered 
#total_wins = 921 - 582 => 339 wins filtered
#total_loses =  889 - 578 => 311 loses filtered


#lead currency strength filter (tolerance 1) - REQUIRES RERUN
#total_trades = 1980 - 1048 => 932 filtered
#total_wins = 921 - 571 => 350 wins filtered
#total_loses =  889 - 381 => 508 loses filtered! 

#lead currency strength filter (tolerance 2)
#total_trades = 1980 - 1265 => 715 filtered 
#total_wins = 921 - 690 => 231 wins filtered
#total_loses =  889 - 452 => 437  loses filtered



#AR currency strength filter (tollerace 1)
#total_trades = 1980 - 982 => 998 filtered
#total_wins = 921 - 420 => 501 wins filtered
#total_loses =  889 - 450 => 439 loses filtered! 

#AR currency strength filter (tollerace 2)
#total_trades = 1980 - 1221 => 759 filtered
#total_wins = 921 - 550 => 371 wins filtered
#total_loses =  889 - 541 => 348 loses filtered! 


##doesn't genereate enough rows :) 
#AR diff currency strength filter (tollerace 1)
#total_trades = 1980 -  =>  filtered
#total_wins = 921 -  =>  wins filtered
#total_loses =  889 -  =>  loses filtered! 

#AR diff currency strength filter (tollerace 2)
#total_trades = 1980 -  =>  filtered
#total_wins = 921 -  =>  wins filtered
#total_loses =  889 -  =>  loses filtered! 





#ema200 filter - not worth it
#total_trades = 1980 - 911 => 1069 filtered
#total_wins = 921 - 425 => 496 wins filtered
#total_loses =  889 - 409 -> 480 loses filtered 

#stoch filter  - not worth it 
#total_trades = 1980 - 1583 => 397 trades filtered
#total_wins = 921 - 740 => 181 wins filtered
#total_loses =  889 -  713 => 176 loses filtered 

#bollinger bands filter
#total_trades = 1980 - 1828 => 152 trades filtered
#total_wins = 921 - 858 => 63 wins filtered
#total_loses =  889 - 809 => 80 loses filtered 















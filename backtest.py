
import datetime
import time
from collections import namedtuple, Counter
from typing import Optional,List

from psycopg2.extensions import AsIs as Inject
import numpy as np 
import pandas as pd
import dateutil.parser

from enum import Enum

import pdb 

from utils import CurrencyPair, ListFileReader, overrides, InstrumentDetails
from setups.signal import TradeDirection, TradeSignal, TradeExitSignal, TradeSignallingData
from charting import candle_stick_functions as csf

import debugging.functs as dbf 
import debugging.charts as dbc

#use pandas
##classes that take a set of trade signals and then test if they won/lost. Also report statistics (win streaks, percent loss, drawdowns??) 

#stagnated = started but didnt stop, unfit = didnt start as out of bounds? eg already hit tp/sl straight away. or the tp/sl targets dont make sense 
BackTestStatistic = namedtuple('BackTestStatistic','total stagnated unfinished invalid wins losses ups downs winstreak losestreak') #growth, drawdown  drawdown')#allows for multiple tests at once

class TradeResultStatus(Enum):
	#CUT = -5 #the signal is cut if there was an expire_cut price that was hit before the entry price. 
	INVALID = -5  #the trade parameters were wrong in some way  
	STAGNATED = -4 #the trade never hit its entry price 
	LOST_SL = -3 #the trade stopped out at the stop loss price 
	LOST_EXIT = -2 #the trade hit an exit criteria and lost
	LOSING = -1 #the trade didnt stop out, but is down 
	VOID = 0 # the trade has not gone ahead (eg hit a cancel price)
	WINNING = 1 #the trade didnt stop out, but is up
	WON_PL = 2 #we moved the stop loss to lock in profit and this value got hit. 
	WON_EXIT = 3 #the trade hit an exit criteria and won
	WON_TP = 4 # the trade stopped out at the take profit price 
	WON_EXTRA = 5 #the trade hit the profit lock activation and continued to the extra profit target 

win_statuses = [TradeResultStatus.WINNING, TradeResultStatus.WON_PL, TradeResultStatus.WON_EXIT, TradeResultStatus.WON_TP, TradeResultStatus.WON_EXTRA]
lose_statuses = [TradeResultStatus.LOST_SL, TradeResultStatus.LOST_EXIT, TradeResultStatus.LOSING]

#lot = 100000 #(for currencies) 
mini_lot = 0.1
micro_lot = 0.01

#TradeProfitPath = namedtuple('TradeProfitPath','typical optimistic pessimistic')
TradeResult = namedtuple('TradeResult','signal_id entry_date entry_price entry_candle exit_date exit_price exit_candle result_movement result_percent result_status')

#activation = price to reach in order to move the stops 
#adjustment = ratio of the take profit distance to place the stop loss at
#extra_ = ratio of the take profit distance of extra profit to strive for 
ProfitLockData = namedtuple('ProfitLockData','activation adjustment extra')

class PercentPathType(Enum):
	PESSIMISTIC = -1
	TYPICAL = 0
	OPTIMISTIC = 1

#tool for finding conversion rates between currencies for when trading anything on eg the US the stock market, or for trading forex 
class ExchangeRateTool:
	
	instruments = None
	timeline = None 
	np_conversions = []
	base_currency = 'GBP' 
	_instrument_map = {} 
	
	#by default always make the tool from an underlying trade_signalling_data object
	@classmethod
	def from_trade_signalling_data(cls, tsd, base_currency):
		ert = ExchangeRateTool() 
		ert.base_currency = base_currency.upper()
		ert.timeline = tsd.timeline
		np_candles = tsd.np_candles
		np_typical = cls.get_np_typical(np_candles)
		instrument_indexs = [i for i,inst in enumerate(tsd.instruments) if cls.has_base(base_currency,inst)] 
		instheads = np.array(tsd.instruments)[instrument_indexs]
		np_typicals1 = np_typical[instrument_indexs]
		instflips = np.array([cls.swap_curr_rate(inst) for inst in instheads])
		np_typicals2 = 1.0 / np_typicals1
		timelinelen = len(ert.timeline) 
		ident = np.ones((1,timelinelen))
		instid = np.array([f"{base_currency}/{base_currency}"])
		ert.np_conversions = np.concatenate([np_typicals1,ident,np_typicals2],axis=0)
		TradeSignallingData.set_instruments(ert, np.concatenate([instheads,instid,instflips],axis=0))		
		return ert
		
	#usual functions for later
	def closest_time_index(self, the_date):
		return TradeSignallingData.closest_time_index(self,the_date)
	
	def instrument_index(self, instrument):
		return TradeSignallingData.instrument_index(self,instrument)
	
	def produce_exchange_rates(self,entry_indexs, exit_indexs, exchanges):
		N = len(entry_indexs)
		lens = exit_indexs - entry_indexs + 1
		maxlen = max(lens)
		exchanges_dest = np.full((N,maxlen),np.nan)
		instrument_indexs = np.repeat(exchanges,lens)
		df_indexs = np.repeat(np.arange(N),lens)
		
		offsets = np.cumsum(lens)
		offsets = np.concatenate([[0],offsets[:-1]],axis=0)
		exchange_indexs = np.arange(df_indexs.shape[0]) - np.repeat(offsets,lens)
		
		conversion_indexs = exchange_indexs + np.repeat(entry_indexs,lens)
		exchanges_dest[df_indexs,exchange_indexs] = self.np_conversions[instrument_indexs,conversion_indexs]
		return exchanges_dest
	
	def spot_exchange_rates(self, time_indexs, exchange_indexs):
		return self.np_conversions[exchange_indexs,time_indexs]
	
	@staticmethod
	def has_base(base_currency,instrument):
		instrument = instrument.upper() 
		try:
			if len(instrument) == 7: ###/###
				if instrument[0:3] == base_currency:
					return True 
				if instrument[-3:] == base_currency:
					return True
			return False 
		except:
			return False 
	
	#so we dont have to care if it is 
	@staticmethod
	def get_np_typical(np_candles):
		if len(np_candles.shape) == 4:	
			return np.mean(np.mean(np_candles[:,:,:,1:4],axis=3),axis=2)
			
		if len(np_candles.shape) == 3:
			return np.mean(np_candles[:,:,1:4],axis=2)
		raise ValueError(f"Unknown np_candles with shape of {np_candles.shape}")
		return None 
	
	@staticmethod
	def swap_curr_rate(instrument):
		try:
			c1,c2 = instrument.split('/')[:2]
			return f"{c2}/{c1}"
		except Exception as e:
			return instrument

#consider putting meta data such as exchange/instrument/etc indexs into a separate class so it can be used elsewhere for speed 

#class for handling the stats? eg for querying 
# allow for sorting/grouping etc of trade results into separate parts 
class BackTestStatistics: 
	
	#- drawdown is min of sum of all negative profit paths 
	#- win/loss ratio
	#- winstreak, losestreak
	#- total trades, wins, loses (result status)
	#- 
	#- result profit in %, calc using capital risk factor 1% * capital, capital, lotsize?  (leverage per instrument makes for borrowing capability) 
	#- (other, volatility? market exposure? sharpe ratio? profit factor? largest win/lose, ave win/lose)
	
	signalling_data = [] 
	exchange_rates = [] #this must be same format as the underlying signalling data to get an accurate exchange rate and the best PnL 
	signals = [] 
	results = [] 
	
	lotsize = 0.01 #microlots 
	starting_capital = 100 #pounds ofcourse! 
	capital_risk = 0.02 #1% - might not be needed - use to calc lot size only 
	
	
	mainframe = None
	
	#usually always gbp but can be USD if we are using a different broker
	#set to None to ignore making profit loss and drawdown metrics
	base_currency = 'GBP' 
	
	
	def __init__(self,ts_data,signals,results):
		self.signalling_data = ts_data #use for the scope of the backtest (from date, to date, etc) and for calculating drawdowns 
		self.signals = signals
		self.results = results 
		self.mainframe = self.get_df()
	
	def set_exchange_rate_tool(self,exchange_rates=None):
		if exchange_rates == None:
			self.exchange_rates = ExchangeRateTool.from_trade_signalling_data(self.signalling_data, self.base_currency)
		else:
			self.exchange_rates = exchange_rates
		assert np.all(self.exchange_rates.timeline == self.signalling_data.timeline), "exchange rate timelines do not match"
	
	#for use with optimisation when testing lots of strats together
	#def fast_objective(self,)
	
	def get_df(self):
		#get all time to index data wrt backtest data (only do this once as expensive)
		dft = pd.DataFrame.from_records([{
			'signal_id':s.signal_id, 
			'start_index':self.signalling_data.closest_time_index(s.the_date),
			'instrument_index':self.signalling_data.instrument_index(s.instrument)
		} for s in self.signals]) 
		dft2 = pd.DataFrame.from_records([{
			'signal_id':r.signal_id, 
			'entry_index': self.signalling_data.closest_time_index(r.entry_date),
			'exit_index': self.signalling_data.closest_time_index(r.exit_date),
		} for r in self.results])
		dft = dft.merge(dft2,on='signal_id')
		dfr = pd.DataFrame(self.results,columns=TradeResult._fields)
		dfs = pd.DataFrame.from_records(s.to_dict() for s in self.signals)
		#pdb.set_trace() #append the start indexs here 
		dfs = dfs.merge(dft,on='signal_id')
		dfs = dfs.merge(dfr,on='signal_id')
		dfs = dfs.sort_values(['entry_date']) #sort all trades in order ready for later
		dfs['win'] = dfs['result_status'].isin(win_statuses) #wack every win/lose in a separate column for later too 
		dfs['lose'] = dfs['result_status'].isin(lose_statuses)
		return dfs
	
	#calc individual strategy ref performances 
	def calculate(self,query_params=None):
		df = self.mainframe
		#scores = self.strategy_result(df)
		
		dbf.stopwatch('calc objective and strategy results')
		
		print('setup exchange') 
		self.set_exchange_rate_tool()
		df = self.update_df_for_exchange(df) #adds data from ExchangeRateTool  
		df = self.update_df_for_currency(df) #adds data from InstrumentDetails 
		
		obj_result = self.per_instrument(df,self.objective_result)
		#pdb.set_trace()
				 
		
		#dbf.stopwatch('calcualte pnl line')
		#percent_line = self.merge_to_chart(typical,df['entry_index'],df['exit_index'],accumulate=False)
		#dbf.stopwatch('calcualte pnl line')
		
		#dbc.draw_numbers(percent_line)
		
		#pdb.set_trace()
		#strat = df[(df['strategy_ref']=='setups.trade_pro.RSIS_EMA_X') & (df['instrument'] == 'GBP/USD')]
		strat_result = self.per_instrument(df,self.strategy_result)
		dbf.stopwatch('calc objective and strategy results')
		
		pdb.set_trace()
		
		print('formulate')
		return obj_result
	

	#functions for grid search - what about instrument AND strategy? code smell?
	def per_instrument(self,df=None,objective_function=None):
		if df is None:
			df = self.mainframe
		if objective_function is None:
			objective_function = self.objective_result
		instruments = self.signalling_data.instruments  #df['instrument'].unique() #perhaps can use this if insturments is not known 
		result = [] 
		for instrument in instruments:
			df_i = df[df['instrument'] == instrument]
			objective = objective_function(df_i)
			objective['instrument'] = instrument 
			result.append(objective)
		return pd.DataFrame.from_records(result)
	
	def per_strategy_ref(self,df=None,objective_function=None):
		if df is None:
			df = self.mainframe
		if objective_function is None:
			objective_function = self.objective_result
		strategy_refs = df['strategy_ref'].unique() #perhaps can use this if insturments is not known 
		result = [] 
		for strategy_ref in strategy_refs:
			df_i = df[df['strategy_ref'] == strategy_ref]
			objective = objective_function(df_i)
			objective['strategy_ref'] = strategy_ref 
			result.append(objective)
		return pd.DataFrame.from_records(result)
		
	#objective result is used in search algorithms to find best strategies on what instruments. some instruments might respond better than others
	#to the different strategies we are testing
	def objective_result(self,df=None): #from dataframe, build a simple result list (win/lose ratio, max wins in row, max losses in row etc)
		if df is None:
			df = self.mainframe
		
				
		#pdb.set_trace()
		
		#calc streaks 
		df = df.sort_values(['entry_date'])
		win_grouper = (df['win'] != df['win'].shift()).cumsum()
		df['win_streak'] = df['win'].groupby(win_grouper).cumsum()
		
		lose_grouper = (df['lose'] != df['lose'].shift()).cumsum()
		df['lose_streak'] = df['lose'].groupby(lose_grouper).cumsum()
		
		dict_result = {
			'wins':df['win'].sum(),
			'loses':df['lose'].sum(), 
			'win_streak':df['win_streak'].max(), 
			'lose_streak':df['lose_streak'].max(), 
			'max_win_percent':df['result_percent'].max(),
			'max_loss_perent':df['result_percent'].min(),
			'len':len(df)
		}
		dict_result['ratio'] = dict_result['wins'] / (dict_result['wins'] + dict_result['loses'])
		
		
		#if we have set up the currency things, we can also get results in terms of money 
		if set(['exchange_index','lot_size','leverage']).issubset(df.columns):
			#get hold cost for each trade (trade size * conversion rate * 1/levereage)
			exchange_rates = self.exchange_rates.spot_exchange_rates(df['exit_index'],df['exchange_index'])
			
			trade_sizes = np.array(self.lotsize * df['lot_size']) #!need to get from instruments not from this constant 
			
			#margin_ratios = np.array(1.0 / df['leverage'])  #margin not needed? 
			#margin_requirements = (1.0 / exchange_rates) * trade_sizes * margin_ratios
			money_output = exchange_rates * trade_sizes * (df['result_percent']  / 100)
			dict_result['max_win_money'] =  money_output.max()
			dict_result['max_loss_money'] =  money_output.min()
			
			dict_result['output_balance'] = money_output.sum()
		
		return dict_result
		
		
	#conversion index (for exchange rates)
	def update_df_for_exchange(self,df):
		df['exchange'] = df['currency'] + '/' + self.base_currency
		df['exchange_index'] = df['exchange'].apply(lambda en, instruments=self.exchange_rates.instruments.tolist() : instruments.index(en))
		return df 
	
	#for profit/loss line, units per lot, leverage, 
	def update_df_for_currency(self,df):
		idetails = InstrumentDetails() 
		df['leverage'] = df['instrument'].apply(lambda i, imap=idetails.instrument_map : imap[i]['leverage_pro'])
		df['lot_size'] = df['instrument'].apply(lambda i, imap=idetails.instrument_map : imap[i]['lot_size'])
		df['pip_size'] = df['instrument'].apply(lambda i, imap=idetails.instrument_map : imap[i]['pip_size'])
		#pdb.set_trace()
		return df 
	
	
	#the dif with this and objective_result is this gets everything in terms of money, including pnl charts and drawdowns
	def strategy_result(self, df): #todo: compounding interest somehow
		#base_result = self.objective_result(df)
		#print('calc strategy result')
		#first get typical percentages and worst percentages 
		typical = self.select_percent_tracks(df,PercentPathType.TYPICAL) 
		best = self.select_percent_tracks(df,PercentPathType.OPTIMISTIC)
		worst = self.select_percent_tracks(df,PercentPathType.PESSIMISTIC) 
		
		#for percent only runs, combine 
		percent_line = self.merge_to_chart(typical,df['entry_index'],df['exit_index'])
		#pdb.set_trace()
		
		return_charts = {
			'typical':self.merge_to_chart(typical,df['entry_index'],df['exit_index']),
			'best':self.merge_to_chart(best,df['entry_index'],df['exit_index']),
			'worst':self.merge_to_chart(worst,df['entry_index'],df['exit_index'])
		}
		
		#percent time in market - lower the better since we want to be in then out with a profit asap
		market_activity = self.market_activity(df['entry_index'],df['exit_index'])
		return_charts['market_time_percentage'] = 100 * np.sum(market_activity == 0) / market_activity.shape[0]
		
		
		
		if set(['exchange_index','lot_size','leverage']).issubset(df.columns):
			
			#calc the PnL chart for this strat and the drawdown etc 
			exchange_rates = self.exchange_rates.produce_exchange_rates(df['entry_index'],df['exit_index'],df['exchange_index'])
			
			#get hold cost for each trade (trade size * conversion rate * 1/levereage)
			trade_sizes = np.array(self.lotsize * df['lot_size']) #!need to get from instruments not from this constant 
			margin_ratios = np.array(1.0 / df['leverage'])
			margin_requirements = (1.0 / exchange_rates) * trade_sizes[:,np.newaxis] * margin_ratios[:,np.newaxis]
			
			typical_results = exchange_rates * trade_sizes[:,np.newaxis] * typical / 100 #remember typical is percentages 
			best_results = exchange_rates * trade_sizes[:,np.newaxis] * best / 100  
			worst_results = exchange_rates * trade_sizes[:,np.newaxis] * worst / 100 
			
			
			return_charts.update({
				'typical_money':self.merge_to_chart(typical_results,df['entry_index'],df['exit_index']) + self.starting_capital,
				'best_money':self.merge_to_chart(best_results,df['entry_index'],df['exit_index']) + self.starting_capital,
				'worst_money':self.merge_to_chart(worst_results,df['entry_index'],df['exit_index']) + self.starting_capital
			})
			
			#grab the chart data by doing something like:
			#strat_result[strat_result['instrument'] == 'EUR/CHF']['typical_money'].iloc[0]
			
			#amount of margin required to perform the trades 
			return_charts.update({
				'margin_money':self.merge_to_chart(margin_requirements,df['entry_index'],df['exit_index'],accumulate=False)
			})
			
			(x1,v1), (x2,v2) = self.max_drawdown_points(return_charts['worst_money']) 
			maxddm = min(((v2 - v1) / v2)*100 , 100) #100 => account blown
			assert maxddm >= 0 , "drawdown is negative which indicates error "
			
			return_charts['draw_down'] = maxddm
			
		return return_charts
	
	def select_percent_tracks(self,df,percent_path_type=PercentPathType.TYPICAL):
		N = len(df)
		lens = df['exit_index'] - df['entry_index'] + 1
		maxlen = max(lens)
		values_dest = np.full((N,maxlen),np.nan)
		instrument_indexs = np.repeat(df['instrument_index'],lens)
		df_indexs = np.repeat(np.arange(N),lens)
		
		offsets = np.cumsum(lens)
		offsets = np.concatenate([[0],offsets[:-1]],axis=0)
		time_indexs = np.arange(df_indexs.shape[0]) - np.repeat(offsets,lens)
		
		value_indexs = time_indexs + np.repeat(df['entry_index'],lens)
		direction_indexs = np.repeat((df['direction'] == TradeDirection.SELL).astype(np.int),lens)
		
		np_candles = self.signalling_data.np_candles
		if len(np_candles.shape) == 3:
			#grow to same as usual backtest candles
			np_candles = np.stack([np_candles,np_candles],axis=2)#test
		
		price_values = None #use to calc percent changes 
		if percent_path_type == PercentPathType.TYPICAL:
			price_values = np.mean(np_candles[instrument_indexs,value_indexs,direction_indexs,1:4],axis=1)
			
		elif percent_path_type == PercentPathType.OPTIMISTIC:
			channel = np.full(df_indexs.shape,csf.high)
			channel[direction_indexs == 1] = csf.low
			price_values = np_candles[instrument_indexs,value_indexs,direction_indexs,channel]
			
		elif percent_path_type == PercentPathType.PESSIMISTIC:
			channel = np.full(df_indexs.shape,csf.low)
			channel[direction_indexs == 1] = csf.high
			price_values = np_candles[instrument_indexs,value_indexs,direction_indexs,channel]
			
		else:
			raise ValueError(f"Unknown percent path type : {percent_path_type}")
		
		start_values = np.repeat(df['entry_price'],lens)
		
		#calc percentage change
		values_dest[df_indexs,time_indexs] = (((price_values - start_values) / start_values) * 100) * (1 - (2*direction_indexs))
		
		#set last index to exit percentage
		values_dest[np.arange(N),lens-1] = df['result_percent']
		
		return values_dest
	
	
	#for every point in time, return number of trades active
	def market_activity(self, start_indexs, end_indexs):
		linelen = len(self.signalling_data.timeline)
		output = np.zeros(linelen)
		
		for (start_index, end_index) in zip(start_indexs,end_indexs):
			output[start_index:end_index] += 1 
			
		return output 
	
	#from a list of profit paths (in money or percents) merge it to a single line 
	def merge_to_chart(self,value_tracks,start_indexs,end_indexs,accumulate=True): 
		
		linelen = len(self.signalling_data.timeline)
		N = len(value_tracks) 
		lens = end_indexs - start_indexs + 1
		maxlen = max(lens)
		#output = np.zeros((N,linelen))
		
		output = np.zeros(linelen)
		
		#try this instead if below keeps behaving weirdly 
		for (value_track, start_index, end_index) in zip(value_tracks,start_indexs,end_indexs):
			#pdb.set_trace()
			end_value = value_track[end_index - start_index]
			output[start_index:end_index] += value_track[:end_index - start_index]
			if accumulate:
				output[end_index:] += end_value #good for pnl
			else:
				output[end_index] += end_value #good for margin requirement
		return output
		
	
	#used for calculating what trades were skipped using margin requirement, and calculating compounding interest 
	def merge_in_order_gen(self,df):
		#use a generator or similar to determine whether to place the trade or not, and what the trade size should be
		pass  
	
	#TODO: given a set of values from a PnL chart or similar, get the maximum drawdown found in percentage 
	@staticmethod
	def max_drawdown_points(linechart):
		x1 = np.argmax(np.maximum.accumulate(linechart) - linechart) # end of the period
		x2 = np.argmax(linechart[:x1]) # start of period
		v1 = linechart[x1]
		v2 = linechart[x2]
		#pdb.set_trace()
		return (x1,v1),(x2,v2)
		
	#@staticmethod
	#def has_money_columns(df):
		
	
	
	#dumb version for getting more info from results 
	def _get_statistics_on(self,subset_signals):  #anything else
		subset_signals = sorted(subset_signals,key=lambda s:s.the_date)
		#lose means finish down or lost
		win_streaks = []
		lose_streaks = [] 
		accum_wins = [] 
		accum_loses = [] 
		rolling_wins = 0
		rolling_loses = 0
		global_wins = len([s for s in subset_signals if s.result_status in win_statuses])
		global_loses = len([s for s in subset_signals if s.result_status in lose_statuses])
		accumwin = 0
		accumloss = 0
		max_win = max(s.result_percent for s in subset_signals)
		max_loss = min(s.result_percent for s in subset_signals)
		
		#streak calc
		for s in subset_signals:
			rolling_wins = (rolling_wins+1) if s.result_status in win_statuses else 0
			rolling_loses = (rolling_loses+1) if s.result_status in lose_statuses else 0
			win_streaks.append(rolling_wins)
			lose_streaks.append(rolling_loses)
		
		
		return {
			'total':len(subset_signals),
			'stagnated':len([s for s in subset_signals if s.result_status == TradeResultStatus.STAGNATED]),
			'unfinished':len([s for s in subset_signals if s.result_status not in [TradeResultStatus.WON,TradeResultStatus.LOST]]),
			'void':len([s for s in subset_signals if s.result_status == TradeResultStatus.VOID]),
			'invalid':len([s for s in subset_signals if s.result_status == TradeResultStatus.INVALID]),
			'wins':len([s for s in subset_signals if s.result_status in win_statuses]),
			'loses':len([s for s in subset_signals if s.result_status in lose_statuses]),
			'ups':len([s for s in subset_signals if s.result_status == TradeResultStatus.WINNING]),
			'downs':len([s for s in subset_signals if s.result_status == TradeResultStatus.LOSING]),
			'win_streak':max(win_streaks),
			'lose_streak':max(lose_streaks),
			'max_win':max_win,
			'max_loss':max_loss
			#'growth':max(...)
			#'drawdown':max(...)
		}


#TODO : A tool to take a dataset of candles and add a percentage error to all the candles to produce a fuzzy dataset based on real world data.
#The idea is to be able to strengthen backtest results and prevent overfitting. A strategy can be considered quite strong if it also passes 
#a fuzzed dataset 
 
#The strategy produces signals based on the fuzzed data and this data is stored in here so it can be used in the results step too
# - a database backtest might not be ideal here. also testing against fundamentals might shake it up too much
#
class FuzzFactor: 

	fuzz_pc = 5; #float between 0 and 100 prefreably 10% or less (experiments welcomed)
	

#main interface for what a backtester is and how it will work
class BackTester:
	
	'''
	Class for doing backtesting on trading signals to see if they won or not. 
	
	Attributes
	----------	
	mode : str
		Of the form "typical", "optimistic" and "pesimistic" to reflect on the modelling strategy when finding 
		results of a backtest. For example, a pesimistic mode will report prices furthest from the take profit
	'''
	mode = 'typical' #TODO - optimistic,pesimistic (use best/worst scenario)
	fuzz = None  #TODO: add fuzz to the dataset. If not none, the data from the fuzz should be used instead 
	
	profit_lock = None 
	exit_per_entry = False # if true, every entry signal also has an exit signal (speeds up the backtest)
	
	def set_profit_lock(self,profit_lock : ProfitLockData):
		##if not of type ProfitLockData?
		if type(profit_lock) != ProfitLockData:
			profit_lock = ProfitLockData._make(profit_lock)
		self.profit_lock = profit_lock
	
	#def test_trade(trade_signal : TradeSignal) -> TradeResult:
	#	pass
	
	def perform(trade_signals : List[TradeSignal], exit_signals : Optional[List[TradeExitSignal]]) -> List[TradeResult]: 
		'''
		Function to perform the backtesting. The method is defined in the subclass. 
		
		Parameters
		----------
		trade_signals : list(TradeSignal)
			The list of trade signals that need to be backtested 
		
		Returns
		-------
		list(TradeResult)
			The list of results (one per trade signal) of what happened with that trade 
		'''
		raise NotImplementedError("This method must be overridden")
		

#perform a backtest by passing the trade signals directly into the database and using a sql query to get the results. 
#Due to using the database, there is no way to be able to expose this to a loss function in tensorflow 
class BackTesterDatabase(BackTester):
	
	sql_query_file = 'queries/new_backtester_execution.sql'
	cursor = None #the database cursor - handled from something else 
	
	trade_result = {
		'INVALID':TradeResultStatus.INVALID,
		'STAGNATED':TradeResultStatus.STAGNATED, 
		'LOST':TradeResultStatus.LOST_SL,
		'EXIT_DOWN':TradeResultStatus.LOST_EXIT,
		'LOSING':TradeResultStatus.LOSING, 
		'VOID':TradeResultStatus.VOID,
		'WINNING':TradeResultStatus.WINNING,
		'PROFIT_LOCK':TradeResultStatus.WON_PL,
		'EXIT_UP':TradeResultStatus.WON_EXIT,
		'WON':TradeResultStatus.WON_TP,
		'WON_EXTRA':TradeResultStatus.WON_EXTRA
	}
	
	
	def __init__(self,cursor):
		self.cursor = cursor
	
	
	@overrides(BackTester)
	def perform(self,trade_signals,exit_signals=[]):		
		
		if not exit_signals: 
			exit_signals = [TradeExitSignal.mock()]
		
		entry_sql_rows = [self.cursor.mogrify(TradeSignal.sql_row,ts.to_dict_row()).decode() for ts in trade_signals]
		exit_sql_rows = [self.cursor.mogrify(TradeExitSignal.sql_row,te.to_dict_row()).decode() for te in exit_signals]
		
		sql_query = None
		with open(self.sql_query_file,'r') as f:
			sql_query = f.read()
		
		query_params = {
			'trade_signals':Inject(','.join(entry_sql_rows)),
			'exit_signals':Inject(','.join(exit_sql_rows)),
			'profit_lock_activation':None,
			'profit_lock_adjustment':None,
			'profit_lock_extra':None,
			'exit_per_entry':self.exit_per_entry
		}
		
		if self.profit_lock is not None:
			query_params['profit_lock_activation'] = self.profit_lock.activation
			query_params['profit_lock_adjustment'] = self.profit_lock.adjustment
			query_params['profit_lock_extra'] = self.profit_lock.extra
		
		self.cursor.execute(sql_query,query_params)
		query_result = self.cursor.fetchall()
		
		trade_results = []
		for result in query_result:
			result_row = result[0] #unpack 
			result_status = self.trade_result.get(result_row['result_status'].upper(),TradeResultStatus.INVALID)
			result_row['result_status'] = result_status
			result_row['entry_date'] = dateutil.parser.parse(result_row['entry_date'])
			result_row['exit_date'] = dateutil.parser.parse(result_row['exit_date'])
			trade_result = TradeResult(**result_row)
			trade_results.append(trade_result)
		return trade_results
	


#pass streams candles (labelled with their instrument name) to this class and then perfrom backtesting using this data
#this class might be exposable to an AI loss function. 
#TODO - this is broken - fix it
class BackTesterCandles(BackTester): #allows for fuzzing the data 
	
	signalling_data = None
	_instrument_map = {} 
	
	def __init__(self, candle_data):	
		self.signalling_data = candle_data
			
	@overrides(BackTester)
	def perform(self,trade_signals,exit_signals=[]):
		
		#this is what each result needs: 
		#signal_id entry_date entry_price entry_candle exit_date exit_price exit_candle result_movement result_percent result_status profit_path
		
		trade_tracks, timeline_indexs = self._get_trade_tracks_and_timeline_indexs(trade_signals)
		trade_directions = np.array([ts.direction for ts in trade_signals])
		trade_directions_end = (trade_directions == TradeDirection.SELL).astype(np.int) 
		trade_directions_start = 1 - trade_directions_end 
		
		bid_ask_trade_tracks = np.stack([trade_tracks[:,:,0,:],trade_tracks[:,:,1,:]])
		trade_tracks_start = bid_ask_trade_tracks[(trade_directions_start,np.arange(trade_tracks.shape[0]))]
		trade_tracks_end = bid_ask_trade_tracks[(trade_directions_end,np.arange(trade_tracks.shape[0]))]
		
		entry_prices, entry_indexs = self._get_start_prices_and_positions(trade_signals, trade_tracks_start)
		signal_ids = [ts.signal_id for ts in trade_signals]
		
		ci_max = np.full(trade_tracks.shape[0],trade_tracks.shape[1]-1) #if any index is equal or larger than this it never happened
		timeline_max = self.signalling_data.timeline.shape[0] - 1
		overflows = timeline_indexs + ci_max - timeline_max
		
		ci_max[overflows > 0] -= overflows[overflows > 0]
		
		
		trade_directions = np.array([ts.direction for ts in trade_signals])
		
		result_statuses = np.array([TradeResultStatus.STAGNATED for ts in trade_signals])
		exit_indexs = ci_max.copy() + 1
		
		
		exit_prices = entry_prices.copy()
		
		
		##key price points 
		cutoffs, take_profits, stop_losses = self._get_key_price_points(trade_signals, entry_prices)
		
		#work out where trades get cut off 
		cutoff_indexs = self._price_hit_calculation(trade_tracks_start, cutoffs)   
		
		cutoff_mask = cutoff_indexs <= entry_indexs
		result_statuses[cutoff_mask] = TradeResultStatus.VOID
		exit_indexs[cutoff_mask] = cutoff_indexs[cutoff_mask]
		exit_prices[cutoff_mask] = cutoffs[cutoff_mask]	
	
		take_profit_indexs = self._price_hit_calculation(trade_tracks_end,take_profits,entry_indexs)
		stop_loss_indexs = self._price_hit_calculation(trade_tracks_end,stop_losses,entry_indexs)
		
		stop_loss_mask = ~cutoff_mask & (stop_loss_indexs <= take_profit_indexs) & (stop_loss_indexs <= ci_max) #add bounds to the indexs to keep stagnated trades ?
		take_profit_mask = ~cutoff_mask & (stop_loss_indexs > take_profit_indexs) & (take_profit_indexs <= ci_max)
		
		result_statuses[stop_loss_mask] = TradeResultStatus.LOST_SL
		result_statuses[take_profit_mask] = TradeResultStatus.WON_TP
		
		exit_indexs[stop_loss_mask] = stop_loss_indexs[stop_loss_mask]
		exit_indexs[take_profit_mask] = take_profit_indexs[take_profit_mask]
		exit_prices[stop_loss_mask] = stop_losses[stop_loss_mask]
		exit_prices[take_profit_mask] = take_profits[take_profit_mask]
			
		if self.profit_lock:
			#pl price points 
			pl_activation, pl_adjustment, pl_extra = self._get_profit_lock_price_points(entry_prices, take_profits)
			pl_activation_indexs = self._price_hit_calculation(trade_tracks_end,pl_activation,entry_indexs)
			
			profit_locked = stop_loss_indexs > pl_activation_indexs
			stop_loss_mask = (~cutoff_mask) & (~profit_locked)
			
						
			pl_sl_indexs = self._price_hit_calculation(trade_tracks_end,pl_adjustment,pl_activation_indexs)
			pl_tp2_indexs = self._price_hit_calculation(trade_tracks_end,pl_extra,pl_activation_indexs)
			
			won_pl_mask = (~cutoff_mask) & profit_locked & (pl_sl_indexs <= pl_tp2_indexs) & (pl_sl_indexs <= ci_max) 
			won_extra_mask = (~cutoff_mask) & profit_locked & (pl_sl_indexs > pl_tp2_indexs) & (pl_tp2_indexs <= ci_max) 
			
			#re-do stop losses 
			result_statuses[stop_loss_mask] = TradeResultStatus.LOST_SL
			exit_indexs[stop_loss_mask] = stop_loss_indexs[stop_loss_mask]
			exit_prices[stop_loss_mask] = stop_losses[stop_loss_mask]
			
			#pl 
			result_statuses[won_pl_mask] = TradeResultStatus.WON_PL
			exit_indexs[won_pl_mask] = pl_sl_indexs[won_pl_mask]
			exit_prices[won_pl_mask] = pl_adjustment[won_pl_mask]
			
			#tp2
			result_statuses[won_extra_mask] = TradeResultStatus.WON_EXTRA if self.profit_lock.extra != 0 else TradeResultStatus.WON_TP
			exit_indexs[won_extra_mask] = pl_tp2_indexs[won_extra_mask]
			exit_prices[won_extra_mask] = pl_extra[won_extra_mask]
			
		#lastly, check the exit signals and adjust trades that exit before they hit their exit index 	
		#TODO -  check entry_indexs <= exit_signal <= exit_indexs 
		exit_timeline_signal_indexs = None 
		if self.exit_per_entry :
			assert len(trade_signals) == len(exit_signals), "Number of exit signals must match number of entry signals"
			self._get_timeline_indexs_from_datetimes([es.the_date for es in exit_signals])
		else:
			exit_timeline_signal_indexs = self._get_exit_signal_indexs(trade_signals, exit_signals) 
		exit_signal_indexs = exit_timeline_signal_indexs - timeline_indexs
		
		#now build results (firstly by deleting any candles that have elapsed the entire track eg (exit_indexs == ci_index)
		entry_dates = np.full(entry_indexs.shape, None)
		exit_dates = entry_dates.copy() 
				
		result_mask = (entry_indexs <= ci_max) & (exit_indexs <= ci_max) #all these have a result 
		#result_values =  np.full(entry_indexs.shape, np.nan)
		
		exit_signal_mask = (entry_indexs <= exit_signal_indexs) & (exit_signal_indexs <= exit_indexs)
		
		entry_dates[result_mask] = self.signalling_data.timeline[timeline_indexs[result_mask] + entry_indexs[result_mask]]
		exit_dates[result_mask] = self.signalling_data.timeline[timeline_indexs[result_mask] + exit_indexs[result_mask]]
		
		depleated_mask = (entry_indexs <= ci_max) & (exit_indexs > ci_max) #handle these using a typical price at ci_max-1?
		
		entry_dates[depleated_mask] = self.signalling_data.timeline[timeline_indexs[depleated_mask] + entry_indexs[depleated_mask]]
		
		exit_indexs[depleated_mask] = ci_max[depleated_mask]
		exit_dates[depleated_mask] = self.signalling_data.timeline[timeline_indexs[depleated_mask] + exit_indexs[depleated_mask]] 
		
		#use the typical prices for the exit price when no SL or TP was hit
		exit_prices[depleated_mask] = np.mean(trade_tracks_end[depleated_mask,exit_indexs[depleated_mask],1:],axis=1)
		exit_prices[exit_signal_mask] = np.mean(trade_tracks_end[exit_signal_mask,exit_indexs[exit_signal_mask],1:],axis=1)
		
		dir_mult = (trade_directions == TradeDirection.BUY).astype(np.int) - (trade_directions == TradeDirection.SELL).astype(np.int)
		result_movements = (exit_prices - entry_prices) * dir_mult 
		result_movements[cutoff_mask] = 0
		result_percents = (result_movements / entry_prices) * 100 
		
		exit_indexs[exit_signal_mask] = exit_signal_indexs[exit_signal_mask] 
			
		result_statuses[~cutoff_mask & depleated_mask & (result_movements <= 0)] = TradeResultStatus.LOSING 
		result_statuses[~cutoff_mask & depleated_mask & (result_movements > 0)] = TradeResultStatus.WINNING 
		result_statuses[~cutoff_mask & exit_signal_mask & (result_movements <= 0)] = TradeResultStatus.LOST_EXIT 
		result_statuses[~cutoff_mask & exit_signal_mask & (result_movements > 0)] = TradeResultStatus.WON_EXIT 

		
		all_results = [] 
		for result in zip(signal_ids,entry_dates,entry_prices,entry_indexs,exit_dates,exit_prices,exit_indexs,result_movements,result_percents,result_statuses):	
			all_results.append(TradeResult._make(result))
		
		#pdb.set_trace()
		return all_results 
		
		
	def _get_timeline_indexs_from_datetimes(self, datetimes):
		return [self.signalling_data.closest_time_index(dt) for dt in datetimes] #check for later ones to ensure they don't just all end up as at the end
	
	
	#for every trade, get the list of candles associated with it ordered from the start to end & get the associated timeline index
	def _get_trade_tracks_and_timeline_indexs(self,trade_signals):
		
		trade_tracks = [] 
		trade_lengths = [] 
		timeline_indexs = [] 
		
		for ts in trade_signals: #TODO: see if this can be optimised further (use dataframes and fancy indexing) 
			ii = self.signalling_data.instrument_index(ts.instrument)
			ti = self.signalling_data.closest_time_index(ts.the_date)
			timeline_indexs.append(ti)
			#if we are not on a weekend 
			ti_ub = ti + (ts.length // self.signalling_data.chart_resolution) 
			
			#what if weekend? 
			trade_track = self.signalling_data.np_candles[ii,ti : ti_ub,...]
			trade_tracks.append(trade_track)
			trade_lengths.append(trade_track.shape[0])
			
			#if not trade_tracks[-1].shape[0] == trade_lengths[-1]:
			#	pdb.set_trace()
			#	print('hit a problem building tts')
			#	assert trade_tracks[-1].shape[0] == trade_lengths[-1]
		
		maxlen = np.max(trade_lengths)
		result = np.full((len(trade_signals),maxlen,2,4),np.nan)
		#pdb.set_trace()
		for i,(tt,tl) in enumerate(zip(trade_tracks,trade_lengths)):
			try:	
				result[i,:tl] = tt[:tl,:,:4] #length,(bid0 or ask1),ohlc
			except Exception as e:
				pdb.set_trace()
				print('hit a problem')
			
		return result, np.array(timeline_indexs)
	
	def _get_exit_signal_indexs(self, trade_signals, exit_signals):
		
		#st = time.time()
		exit_indexs = np.full(len(trade_signals),-1)
		if not exit_signals:
			return exit_indexs
		
		#looks mad but this works well and is faster than iterating in loops (test!)
		#firstly, turn every comparat to np arrays
		exit_signal_dates = np.array([es.the_date for es in exit_signals]).astype(np.datetime64)
		entry_start_dates = np.array([ts.the_date for ts in trade_signals]).astype(np.datetime64)
		entry_end_dates = np.array([ts.the_date + datetime.timedelta(minutes=ts.length) for ts in trade_signals]).astype(np.datetime64)
		
		entry_strategy_refs = np.array([ts.strategy_ref for ts in trade_signals])
		exit_strategy_refs = np.array([es.strategy_ref for es in exit_signals])
		
		entry_instruments  = np.array([ts.instrument for ts in trade_signals])
		exit_instruments  = np.array([es.instrument for es in exit_signals])
		
		entry_directions = np.array([ts.direction for ts in trade_signals])
		exit_directions = np.array([es.direction for es in exit_signals])
		
		#next, calculate the truthy matrices for every conditional 
		#pdb.set_trace()
		match_strategy_refs = entry_strategy_refs[:,np.newaxis] == exit_strategy_refs[np.newaxis,:]
		match_instruments = entry_instruments[:,np.newaxis] == exit_instruments[np.newaxis,:]
		match_directions = entry_directions[:,np.newaxis] == exit_directions[np.newaxis,:]
		within_dates = (entry_start_dates[:,np.newaxis] <= exit_signal_dates[np.newaxis,:]) & (exit_signal_dates[np.newaxis,:] < entry_end_dates[:,np.newaxis])
		
		#and all the matrices together 
		exit_signal_matches = np.all(np.stack([match_strategy_refs,match_instruments,match_directions,within_dates],axis=2),axis=2)
		
		#find the earliest exit signal date for non-nan rows 
		exit_mask = np.any(exit_signal_matches,axis=1)
		exit_datetimes = np.full(exit_signal_matches.shape,datetime.datetime(9999,1,1))  #Surely I will live this long to see this bug :D 
		indexer = np.where(exit_signal_matches)
		exit_datetimes[indexer] = exit_signal_dates[indexer[1]]
		exit_signal_dates_np = np.min(exit_datetimes,axis=1)
		
		exit_indexs[exit_mask] = [self.signalling_data.closest_time_index(the_date) for the_date in exit_signal_dates_np[exit_mask]]
		#print("time took with np = "+str(time.time() - st))
		
		#st = time.time()
		#test with regular python
		#exit_signal_dates_py = [None] * len(trade_signals)
		#for i,ts in enumerate(trade_signals):
		#	for es in exit_signals:
		#		if (ts.strategy_ref, ts.direction, ts.instrument) == (es.strategy_ref, es.direction, es.instrument):
		#			if es.the_date >= ts.the_date and es.the_date <= ts.the_date + datetime.timedelta(minutes=ts.length):
		#				if exit_signal_dates_py[i] is None or exit_signal_dates_py[i] > es.the_date:
		#					exit_signal_dates_py[i] = es.the_date
		#
		##finally, use the earliest exit signal datetimes to get the timeline indexs 
		#exit_indexs2 = [-1 if the_date is None else self.signalling_data.closest_time_index(the_date) for the_date in exit_signal_dates_py]
		#print("time took with py = "+str(time.time() - st))
		#pdb.set_trace()
		
		return exit_indexs
	
	def _get_start_prices_and_positions(self, trade_signals, trade_tracks):	
		
		signal_start_prices = np.array([ts.entry for ts in trade_signals],dtype=np.float64)
		nanmask = np.isnan(signal_start_prices)
		
		start_prices = np.full(len(trade_signals),np.nan)
		start_positions = np.full(len(trade_signals),0)
		
		start_candles = trade_tracks[:,0,:]
		start_prices[nanmask] = np.mean(start_candles[nanmask,1:],axis=1) #typical price (csf.open = 0)
		start_prices[~nanmask] = signal_start_prices[~nanmask]
		
		#TODO: uncomment out when this is working & example
		price_start_poistions =  self._price_hit_calculation(trade_tracks[~nanmask],signal_start_prices[~nanmask])
		start_positions[~nanmask] = price_start_poistions # self._price_hit_calculation(trade_tracks[~nanmask],signal_start_prices[~nanmask])
		
		return start_prices, start_positions
		
		
	def _get_key_price_points(self,trade_signals,start_prices):
		
		tpd = np.array([ts.take_profit_distance for ts in trade_signals],dtype=np.float64)
		sld = np.array([ts.stop_loss_distance for ts in trade_signals],dtype=np.float64)
		
		dirs = np.array([1 if ts.direction == TradeDirection.BUY else -1 if ts.direction == TradeDirection.SELL else 0 for ts in trade_signals],dtype=np.float64)
		
		cutoffs = np.array([ts.entry_cut for ts in trade_signals],dtype=np.float64)
		
		take_profits = start_prices + (dirs * tpd)
		stop_losses = start_prices - (dirs * sld)
		
		return cutoffs, take_profits, stop_losses #, profit_lock_activations, profit_lock_adjustments, profit_lock_extra
	
	def _get_profit_lock_price_points(self, start_prices, take_profits):
		
		pl_activation_mult = self.profit_lock.activation if self.profit_lock is not None and self.profit_lock.activation is not None else np.nan
		pl_adjustment_mult = self.profit_lock.adjustment if self.profit_lock is not None and self.profit_lock.adjustment is not None else np.nan
		pl_extra_mult = self.profit_lock.extra if self.profit_lock is not None and self.profit_lock.extra is not None else np.nan 
		
		tpd = take_profits - start_prices
		
		profit_lock_activations = start_prices + (tpd *  pl_activation_mult)
		profit_lock_adjustments = start_prices + (tpd *  pl_adjustment_mult)
		profit_lock_extra = start_prices + (tpd * (1.0 + pl_extra_mult))
		
		return profit_lock_activations, profit_lock_adjustments, profit_lock_extra
	
	#def get_profit_paths(self, trade_tracks_end, dir_mult, entry_indexs, exit_indexs):
	#	profit_paths = np.full(dir_mult.shape[0],None)
	#	pdb.set_trace()
	#	#optimistic = 
	#	#pessimistic = 
	#	#typical =  
	#	
	#	#delete where index not between entry and exit indexs by setting to 0 
	#	return profit_paths 
	
	#most used part of the backtesting algorithm so needs to be fast  
	@staticmethod
	def _price_hit_calculation(trade_tracks, price_target, start_pos=None):
	
		price_target = price_target[:,np.newaxis] #newaxis somewhere
		within = (trade_tracks[:,:,csf.low] <= price_target) & (price_target <= trade_tracks[:,:,csf.high])
		
		trade_track_closes = trade_tracks[:,:-1,csf.close]
		padding = np.full((trade_track_closes.shape[0],1),np.nan)
		prev_closes = np.concatenate([padding, trade_tracks[:,:-1,csf.close]],axis=1)
		next_opens = trade_tracks[:,:,csf.open]
		
		before_low = (prev_closes <= price_target) & (price_target <= next_opens)
		before_high = (next_opens <= price_target) & (price_target <= prev_closes)
		
		#unsure of this 	
		result_grid = within | before_low | before_high
		time_ind = np.arange(result_grid.shape[1]) + 1 
		
		if start_pos is None:
			start_pos = np.zeros(price_target.shape[0])
		
		start_positions = 1.0 / (start_pos + 1.0)
		
		#to ensure we get the earliest after start position, everything before that index will be less than 1 so we can floor it off
		result_numeric = np.floor(time_ind[np.newaxis,:]  * result_grid.astype(np.int) * start_positions[:,np.newaxis]).astype(np.int)
		result_numeric[result_numeric == 0] = result_numeric.shape[1] ##then set all 0s to max value to stop them being selected by argmin
		
		result_numeric = np.concatenate([result_numeric,np.full((result_numeric.shape[0],1), result_numeric.shape[1]-1)],axis=1)
		results = np.argmin(result_numeric,axis=1)

		return results
	






















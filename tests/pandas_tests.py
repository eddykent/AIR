


import pickle
import pandas as pd

from setups.signal import TradeSignal
from backtest import TradeResult


results = []
signals = []

##use pandas for evaluating backtest results 

with open('pickles/trade_results.pkl','rb') as f:
	results = pickle.load(f)

with open('pickles/trade_signals.pkl','rb') as f:
	signals = pickle.load(f)



df_results = pd.DataFrame.from_records(
   results,
   columns=TradeResult._fields
)

df_signals = pd.DataFrame([vars(s) for s in signals ])
df_results = df_results.drop(['profit_path'],axis=1) #drop the profit paths as they are just clutter 

df_alltests = df.merge(df_signals,df_results,on=['signal_id']) #nice! 


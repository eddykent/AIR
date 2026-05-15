==Autoregressions, Indicators and Recursive NNs==

This is a new implementation of the previous methods combined with an ARIMA model 
and a bunch of indicators. The whole thing was re-implemented to try and avoid bugs
and to cater for the new data table. (exchange_value_tick) 


IDEAS:
1) Combine ARIMA / VARMA result with the NN to see if that aids its decision making

2) Use only the currency strength metrics, predict future strengths and then build 
trading strat from that instead? The NN will be significantly smaller and also 
ARIMA might work well with currency strengths instead of prices  - VARMA too slow :( 


Classes: 
HistData - gets data from DB and processes it into subsequences
	- methods are exposed to process anything into subsequences

TradeSchedule - Gets a trade schedule and then tests it using the database

Predictor - Gets data and builds a model to create trade schedules
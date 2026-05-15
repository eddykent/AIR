# Forex Trading Bot Testing Framework (In Python) 
This project is a completely stand alone forex trading framework. The main purpose of this project is to try ideas that are perhaps novel and not common in the CFD trading market and use science and statistics to optimise the best CFD short-term portfolios. This includes getting and procuring data, facilitating the writing of "setup" scripts, creating filters to prevent "bad" trades and backtesting to gauge & execute strategies that get the best results. The framework uses a combination of well-known indicators, mathematical and statistical methods like correlations and ARIMA models and uses AI to predict demands, price action and ANNs/XGBoost/reinforcment learning to attempt to trade the FX market. 

The framework relies heavily on numpy, a linear algebra numerical library and scipy, a scientific computation framework for calculating and backtesting. This makes it very fast for computing maxima/minima, statistics, price-pattern shapes, indicator values and more (https://numpy.org/doc/stable/). 

The utopia is to be able to do something like: 

```
import Grab from air.data
import MyStrat from air.strategy
import NoSillyDecisions from air.filters
import display from air.charting

data = Grab(currencies=['USD','JPY','GBP'],from=2024,until='now')

signals = MyStrat(data)

better_signals = NoSillyDecisions.filter(signals)

display(better_signals) #might spam charts! 
```

Or even: 

```
import Grab from air.data
import air.backtest

import CharlatanStrat from air.strategy

data = Grab(currencies=['USD','JPY','GBP'],from=2024,until='now')

signals = Charlatan(data)

backtest.test(signals) ## print wins/loses
```

Ideally, a strat can be made from this library with numpy syntactic sugar, like this:

```
from air.indicators import MACD, RSI
from air.strategy import Strategy


class MyStrat(Strategy):
    macd  = MACD(14,23,3)
    rsi = RSI(14,20,80)
    __init__(self, some_params):
        #set rsi or macd here if overridden

    def detect(self,charts):
        rsi_result = rsi(charts)
        macd_result = macd(charts)
        bullish = rsi_result > 80 && macd_result.signal < macd.macd_line   #macd crossed the signal upwards 
        bearish = rsi_result < 20 && macd_result.signal > macd.macd_line   #macd crossed the signal downwards
```

All vectorised. Many instruments all at once. 

This whole project is, ofcourse, a work in progress. 
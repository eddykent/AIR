import yfinance as yf
import plotly.graph_objects as plot

import pdb

df = yf.Ticker('QQQ').history(interval='1h')

fig = plot.Figure(data=[plot.Candlestick(
                open=df['Open'],
                high=df['High'],
                low=df['Low'],
                close=df['Close'])])
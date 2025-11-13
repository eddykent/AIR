



from charting.chart_viewer import *


plotly = PlotlyChartPainter()

def reset():
	plotly = PlotlyChartPainter()

def draw_numbers(numbers):	
	cv = ChartView()
	number_path = [Point(i,float(n)) for (i,n) in enumerate(numbers)]
	cv.draw('price_actions keyinfo paths',number_path)
	plotly.paint(cv)
	plotly.show()

def draw_candles(candles):
	opens = [c[0] for c in candles]
	highs = [c[1] for c in candles]
	




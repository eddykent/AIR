



from charting.chart_viewer import *


plotly = PlotlyChartPainter()

def draw_numbers(numbers):	
	cv = ChartView()
	number_path = [Point(i,n) for (i,n) in enumerate(numbers)]
	cv.draw('price_actions keyinfo paths',number_path)
	plotly.paint(cv)
	plotly.show()
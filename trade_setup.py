## setups are trades that have been produced from signals from various sources. 




class Setup(ChartPattern):	
	pass





##https://www.youtube.com/watch?v=4dVB_g5YeSE  
##keep it simple - all chart pattern objects should only look at one timeframe. A setup looks at many.
#find trendline/support&resistance from higher timeframe and divergence from this and lower timeframe, and breakout from lower timeframe
class RSIDivergence(TradeSetup):
	   
	def __init__(self):
		pass
	
	#override
	@staticmethod
	def to_candles(sequence,instrument):
		return sorted([
			[
				snapshot[2][instrument]['open_price'],
				snapshot[2][instrument]['high_price'],	
				snapshot[2][instrument]['low_price'],
				snapshot[2][instrument]['close_price'],
				snapshot[2][instrument]['relative_strength_index'],   ##will be needed to detect divergence
				snapshot[0] #datetime for debugging if needed...
			]
		for snapshot in sequence],key=lambda c:c[4]) #sort into chronological order 







#we know his strategy & we can improve it with some extra timeframes!
class ForexSignalsEngulferPinbar(TradeSetup):
	pass
	






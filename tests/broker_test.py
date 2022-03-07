

from web.broker import Trading212
from web.crawler import SeleniumHandler

with SeleniumHandler(hidden=False) as sh:
	t212 = Trading212(sh)
	t212.begin()
	#input() #wait 
	
	t212.pull_the_plug()
	
	
	#get live trades
	#...
	#get a trade - even if it is in closed trades
	#...
	#add a trade - make sure to be on demo :)
	#...
	#remove all the trades 
	#...
	
	t212.finish()
	

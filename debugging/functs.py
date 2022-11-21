

import time


stopwatch_names = {}
def stopwatch(name):
	st = stopwatch_names.get(name)
	if st is None:
		stopwatch_names[name] = time.time() 
		print(f"timing {name}")
	else:
		del stopwatch_names[name]
		tt = time.time()-st
		print(f"{name} took {tt:.2f} seconds")
		

def datetimestr(dt):
	return f"{dt.year:0>4d}/{dt.month:0>2d}/{dt.day:0>2d} @{dt.hour:0>2d}:{dt.minute:0>2d}"
	

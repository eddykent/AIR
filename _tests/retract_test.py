




def retracement(value1,value2,the_value):
		return ((the_value - value2) / (value1 - value2)) if value1 != value2 else 0
	
def extension(value1,value2,the_value):  
	return ((the_value - value1) / (value2 - value1)) if value1 != value2 else 0
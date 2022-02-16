from collections import namedtuple

TrendLine = namedtuple('TrendLine','x1 y1 x2 y2 error')



#chops a trendline into smaller pieces so we can use them for measuring errors or getting points on the line 
def parametric(trendline):
	
	start_x,start_y,end_x,end_y,_ = trendline
	direction = 1 if  start_x < end_x else -1 if start_x > end_x else 0
	assert direction != 0, 'Our trendline is at the same x'
	
	start_index = min(start_x,end_x)
	end_index = max(start_x,end_x)
	index_len = end_index - start_index
	indexs = range(start_index,end_index+1)
	
	ts = [ti/index_len for ti in range(0,index_len+1)]
	
	start_value = start_y if direction == 1 else end_y if direction == -1 else 0
	end_value = end_y if direction == 1 else start_y if direction == -1 else 0
	
	parametric_values = [end_value * t + start_value * (1-t) for t in ts]   #useful for many things surely so put here! :) 

	return  {x:y for x,y in zip(indexs,parametric_values)}

#most chart windows we work backwards - we start at the snapshot index and then move back to find trends. after this we need
#to put our trendline in the correct way round to prevent it breaking 

def reverse_trendline(trendline): #needs to be called if we are finding a backwards trendline 
	return TrendLine(trendline.x2,trendline.y2,trendline.x1,trendline.y1,trendline.error)

def is_reversed(trendline):
	return trendline.x1 > trendline.x2

def orientate(trendline):
	if is_reversed(trendline):
		return reverse_trendline(trendline)
	return trendline

def overlap(t1x1,t1x2,t2x1,t2x2):
	return t1x1 < t2x2 and t2x1 < t1x2

def overlap_x(trendline1,trendline2):
	trendline1 = orientate(trendline1)
	trendline2 = orientate(trendline2)
	return overlap(trendline1.x1,trendline1.x2,trendline2.x1,trendline2.x2)
	#return trendline1.x1 < trendline2.x2 and trendline2.x1 < trendline1.x2

def lower_y(trendline):
	return min(trendline.y1,trendline.y2)
	
def higher_y(trendline):
	return max(trendline.y1,trendline.y2)

def lower_x(trendline):
	return trendline.x1 if trendline.x1 < trendline.x2 else trendline.x2

def higher_x(trendline):
	return trendline.x2 if trendline.x1 < trendline.x2 else trendline.x1


def overlap_y(trendline1,trendline2):
	min_1 = lower_y(trendline1)
	min_2 = lower_y(trendline2)
	max_1 = higher_y(trendline1)
	max_2 = higher_y(trendline2)
	return overlap(min_1,max_1,min_2,max_2)
	
def intersecting_bounds(trendline1, trendline2):
	return overlap_x(trendline1,trendline2) and overlap_y(trendline1,trendline2) 
	

def intersection_point(trendline1,trendline2): #return a point in which the projected lines of these two intersect
	line1 = (trendline1.x1,trendline1.y1),(trendline1.x2,trendline1.y2)
	line2 = (trendline2.x1,trendline2.y1),(trendline2.x2,trendline2.y2)
	xdiff = (line1[0][0] - line1[1][0], line2[0][0] - line2[1][0])
	ydiff = (line1[0][1] - line1[1][1], line2[0][1] - line2[1][1])
	
	def det(a, b):
		return a[0] * b[1] - a[1] * b[0]
	
	div = det(xdiff, ydiff)
	if div == 0:
		return None,None
	
	d = (det(*line1), det(*line2))
	x = det(d, xdiff) / div
	y = det(d, ydiff) / div
	return x, y


def angle(trendline1,trendline2):
	return 0 
	
	
 #return point only if it is within the lines 
def intersection(trendline1,trendline2):
	if not intersecting_bounds(trendline1,trendline2):
		return None ,None
	x,y = intersection_point(trendline1,trendline2)
	if x is None or y is None:
		return None,None
	if lower_x(trendline1) <= x and x <= higher_x(trendline1):
		if lower_x(trendline2) <= x and x <= higher_x(trendline2):
			if lower_t(trendline1) <= y and y <= higher_y(trendline1):
				if lower_y(trendline2) <= y and y <= higher_y(trendline2):
					return x,y
	return None,None


def gradient(trendline):
	return (trendline.y2 - trendline.y1) / (trendline.x2 - trendline.x1)

def combined_gradient(trendline1,trendline2):
	return (gradient(trendline1) + gradient(trendline2)) / 2.0

def length(trendline):
	#python preserves the sign for ** functions!
	return (abs(trendline.y2 - trendline.y1)*2+abs(trendline.x2 - trendline.x1)*2)**0.5

def convergent(trendline1,trendline2):
	trendline1 = orientate(trendline1)
	trendline2 = orientate(trendline2)
	m1 = gradient(trendline1)
	m2 = gradient(trendline2)
	if m1 == m2: #parallel check 
		return False
	#get slowest and fastest movers 
	return abs(trendline1.y1 - trendline2.y1) > abs(trendline1.y2 - trendline2.y2)
	
def divergent(trendline1,trendline2):
	return not convergent(trendline1,trendline2)

def convergence_speed(trendline1,trendline2):
	m1 = gradient(trendline1)
	m2 = gradient(trendline2)
	return abs(m1 - m2)

def get_x_range(trendline):
	return range(trendline.x1,trendline.x2+1) if not is_reversed(trendline) else range(trendline.x2,trendline.x1+1)

def x_iou(trendline1,trendline2):
	trendline1 = orientate(trendline1)
	trendline2 = orientate(trendline2)
	unio = max(trendline1.x2,trendline2.x2) - min(trendline1.x1,trendline2.x1)
	sect = min(trendline1.x2,trendline2.x2) - max(trendline1.x1,trendline2.x1)
	return sect/unio

def iou(trendline1,trendline2):
	#get the bb for each trendline then calculate the intersection over u
	return 0 

def projection(trendline,x):
	#despite x being larger than this trendline, this function uses linear extrapolation to give us a value at the x we provide 
	#I am sure this function can be make more simple!
	M = gradient(trendline)
	min_x = lower_x(trendline)
	max_x = higher_x(trendline)
	min_yx = trendline.y1 if trendline.x1 < trendline.x2 else trendline.y2 if trendline.x1 > trendline.x2 else 0
	max_yx = trendline.y2 if trendline.x1 < trendline.x2 else trendline.y1 if trendline.x1 > trendline.x2 else 0
	if min_x <= x and x <= max_x:
		pvar = parametric(trendline)
		return pvar[x]
	elif x < min_x:
		return min_yx - M*(min_x - x)
	elif x > max_x:
		return max_yx + M*(x - max_x)
	return 0














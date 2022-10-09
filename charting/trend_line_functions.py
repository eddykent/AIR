import numpy as np 


import pdb

#some named coordinates
x1 = 0
y1 = 1
x2 = 2
y2 = 3 
error = 4


#from a set of points (with nan points at the end), create a line from the start to the end non-nan point. 
#chop this line into pieces, one per point. This is useful for making the data level. 
#for lines with 1 or less points, return a bunch of 0s 
def make_parametric(pointlists):
	Xs = pointlists[:,:,0]
	Ys = pointlists[:,:,1]
	
	nanmask = np.isnan(Xs)
	nonnanmask = 1 - nanmask
	index = np.arange(Xs.shape[1])
	indexs = np.stack([index]*pointlists.shape[0])
	
	endis = np.max(indexs * nonnanmask,axis=1)
	actual_lines = np.where(endis > 0)
	
	endvs = Ys[actual_lines,endis]
	startvs = Ys[actual_lines,0]
	endn = endis[actual_lines]
	
	ranges = endvs - startvs
	steps = ranges / endn
	
	step_indexs = np.arange(Xs.shape[1])[:,np.newaxis]
	paravals = np.outer(step_indexs,steps).T
	
	parametrics = np.zeros(Xs.shape)
	parametrics[actual_lines,:] = paravals
	return parametrics

def gradient(trendlines):
	return (trendlines[:,y2] - trendlines[:,y1]) / (trendlines[:,x2] - trendlines[:,x1])

def projection(trendlines,xvals):
	gradient_step = gradient(trendlines)
	step_multiplier = xvals - trendlines[:,x1]
	return trendlines[:,y1] + (step_multiplier * gradient_step) 

def parametric_projection(trendlines,startx,endx):
	return 

#needed?
def orientate(tl1,tl2):  #determine which line is the max and which is the min 
	return tl1, tl2

def convergent(minlines, maxlines):
	g1 = gradient(minlines)
	g2 = gradient(maxlines)
	return (g2 - g1) < 0 

def parallel(trendlines1,trendlines2):
	g1 = gradient(trendlines1) 
	g2 = gradient(trendlines2)
	return g1 == g2 #probably never 

def divergent(minlines, maxlines):
	g1 = gradient(minlines)
	g2 = gradient(maxlines)
	return (g2 - g1) > 0 

#def overlap_x 
#def overlap_y

#if they intersect within the bounds
#def intersects(trendlines1,trendlines2): #-> [Bool] 

def intersection(trendlines1,trendlines2): #-> [(x,y)]
	pass

#move trendlines to x1,x2
def stretch_move(trendlines,x1vals,x2vals): #why not use projection?
	gradient_step = gradient(trendlines)
	step_mul1 = x1vals - trendlines[:,x1]
	step_mul2 = x2vals - trendlines[:,x1]
	new_y1 = trendlines[:,y1]+(step_mul1*gradient_step)
	new_y2 = trendlines[:,y1]+(step_mul2*gradient_step)
	errs = np.full(new_y1.shape,np.nan)
	result = np.stack([x1vals,new_y1,x2vals,new_y2,errs],axis=1)
	#pdb.set_trace()
	return result
	

#add trendline functions here for any trendline related stuff (eg, gradient, intersection, overlap, convergent, range, projection etc) 

















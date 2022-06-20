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
	
	parametrics = np.zeros((Xs.shape[0],Xs.shape[1]))
	parametrics[actual_lines,:] = paravals
	return parametrics
	
def gradient(trendlines):
	return (trendlines[:,y2] - trendlines[:,y1]) / (trendlines[:,x2] - trendlines[:,x1])

def projection(trendlines,xvals):
	gradient_step = gradient(trendlines)
	step_multiplier = xvals - trendlines[:,x1]
	return trendlines[:,y1] + (step_multiplier * gradient_step) 
	
def intersects(trendlines1,trendlines2): #-> [Bool]
	pass

def intersection(trendlines1,trendlines2): #-> [(x,y)]
	pass
	

#add trendline functions here for any trendline related stuff (eg, gradient, intersection, overlap, convergent, range, projection etc) 




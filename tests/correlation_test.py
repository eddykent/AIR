#this file shows all the correlations of the pairs on a 2d plane. 
#points that are close together are strongly correlated
#to collect together points by weakest correlation, use 1.0 - distance

import numpy 
import psycopg2
import datetime

from sklearn import manifold
import plotly.express as px

import pdb

from utils import Configuration, ListFileReader

config = Configuration()
con = psycopg2.connect(config.database_connection_string())
cur = con.cursor()

lfr = ListFileReader()
currencies = lfr.read('fx_pairs/currencies.txt')
fx_pairs = lfr.read('fx_pairs/fx_mains.txt')
sorted(fx_pairs)

the_date = datetime.datetime(2022,1,27,16,0)


query = ''
with open('queries/correlation_matrix.sql','r') as f:
	query = f.read()
	
parameters = {
	'currencies':currencies,
	'the_date':the_date,
	'hour':the_date.hour,
	'days_back':100,
	'chart_resolution':240,
	'correlation_window':50
}

cur.execute(query,parameters)
correlations = cur.fetchall()

correlation_matrix = correlations[0][2]

dists = [[1 - correlation_matrix[pair1]['with'][pair2]['distance'] for pair1 in fx_pairs] for pair2 in fx_pairs]

mds = manifold.MDS(n_components=2,dissimilarity='precomputed',random_state=6)
result = mds.fit(dists)
coords = result.embedding_

fig = px.scatter(x=coords[:,0],y=coords[:,1],text=fx_pairs)
fig.show()





















import datetime

from charting.match_pattern import MatchPattern
from utils import ListFileReader, Database 


the_date = datetime.datetime(2022,3,2,15,15)


query = 'querys/candle_stick_selector.sql'
params = {
	'the_date':the_date,
	'hour':the_date.hour,
	
}

cur = Database()



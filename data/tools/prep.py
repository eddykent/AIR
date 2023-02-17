##file for handling miscelaneous tools for preparing data for analysis and training

import datetime
from collections import defaultdict

#use these funcs for datetime AND pandas 
def datetime_day_floor(the_date):
	return datetime.datetime(the_date.year,the_date.month,the_date.day,0,0)
	
def datetime_day_ceil(the_date):
	return datetime_day_floor(the_date) + datetime.timedelta(days=1)

#merges list of date times into consecutive blocks of time 
class TimelineMerge:
	
	error_space_days = 3
	
	def __init__(self,error_space_days=3):
		if error_space_days:
			self.error_space_days = error_space_days
	
	def get_blocks(self,the_dates):
		if not the_dates:
			return []
		
		the_dates = sorted(the_dates)
		n_dates = len(the_dates)
		paired_dates = [x for x in zip(the_dates[:-1],the_dates[1:])]
		gap_indexs = [-1] \
				+ [i for i,(ed1,ed2) in enumerate(paired_dates) if (ed2 - ed1) > datetime.timedelta(days=self.error_space_days)] \
				+ [n_dates-1]
		
		timeline_block_indexs = [(i+1,j) for (i,j) in zip(gap_indexs[:-1],gap_indexs[1:])]
		timeline_blocks = [(the_dates[i],the_dates[j]) for (i,j) in timeline_block_indexs]
		timeline_blocks = [(datetime_day_floor(ts1),datetime_day_ceil(ts2)) for (ts1,ts2) in timeline_blocks] 
		return timeline_blocks
		
	def from_hole_finder(self,holes):
		instrument_holes = defaultdict(list)
		instrument_timelines = {}
		
		for instrument, the_date in holes:
			instrument_holes[instrument].append(the_date)
		
		for instrument, dates in instrument_holes.items():
			instrument_timelines[instrument] = self.get_blocks(dates) 
		
		return instrument_timelines
	
	
	def create_data_tasks(self,instrument_timelines):
		data_tasks = [] 
		for instrument, time_blocks in instrument_timelines.items():
			for time_block in time_blocks:
				data_tasks.append({'instrument':instrument,'date_from':time_block[0],'date_to':time_block[1]})
		return data_tasks 
	
	
	def hole_finder_tasks(self,holes):
		return self.create_data_tasks(self.from_hole_finder(holes))
		
		
		
		
		
		
	

	







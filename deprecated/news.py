#instead of loading all articles in place, load the publish times then load the article separately and test it
#against an AI of choice if the news is good or bad.

class NewsFetch:
	pass  #base class for tools for getting news articles within dates or in specified dates etc 
	
#class LazySentimentNewsFetch:
class LazyAINewsFetch:

	def __init__(self,model_loader):
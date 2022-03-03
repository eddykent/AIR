


##this is a work in progress file for developing a process for figuring out what type of text an article is. 
##a similar test can be done for finding insights from text data in a different file. 

assert __name__ != "__main__", "You must run tests through the run_test.py hoister"
import pdb 
from fundamental import TextAnalysis, ForexSlashHelper, KeywordMapHelper  ##we want to keep playing with TextAnalysis until it starts to work for us 
import scrape.feed_collector as feedco

from utils import ListFileReader 
from collections import Counter
from string import punctuation
import spacy
import nltk

lfr = ListFileReader()
lfr.errors = 'ignore'


mock_signal1 = lfr.read_full_text('mocks/eurjpy_signal.txt')
mock_signal2 = lfr.read_full_text('mocks/audusd_signal.txt')

mock_story1 = lfr.read_full_text('mocks/usdjpy_story.txt')
mock_story2 = lfr.read_full_text('mocks/eurusd_story.txt')

mock_tutorial1 = lfr.read_full_text('mocks/tutorial1.txt')



nlp  = spacy.load("en_core_web_lg")
fsh = ForexSlashHelper()

def keyworded(some_text):
	some_text = fsh.strip_slashes(some_text)
	keywords = [w for w in nltk.word_tokenize(some_text.lower()) if w not in punctuation and w not in nlp.Defaults.stop_words]
	return Counter(keywords) 

def spacy_keyworded(some_text):
	some_text = fsh.strip_slashes(some_text)
	document = nlp(some_text.lower())
	keywords = [tok.text for tok in document if tok.text not in nlp.Defaults.stop_words and tok.pos_ in ['PROPN','ADJ','NOUN'] and tok.text not in punctuation]
	return Counter(keywords)





#fx_pairs = lfr.read('fx_pairs/fx_mains.txt')
##cs = ClientSentiment(fx_pairs)##put fx pairs in!
##cs.fetch()

##use this for cherry-picking articles for mocks 
#(use fetch_full_text on an article. Eg: rss.articles[2].fetch_full_text() )
def show_articles():
	rss = feedco.RSSCollect(lfr.read('sources/rss_feeds.txt'))
	rss.parse_feeds()
	[print(str(i) + ' - ' + str(a)) for (i,a) in enumerate(rss.articles)]










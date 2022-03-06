


##this is a work in progress file for developing a process for figuring out what type of text an article is. 
##a similar test can be done for finding insights from text data in a different file. 

assert __name__ != "__main__", "You must run tests through the run_test.py hoister"
import pdb 
from fundamental import TextAnalysis, ForexSlashHelper, KeywordMapHelper  ##we want to keep playing with TextAnalysis until it starts to work for us 
import web.feed_collector as feedco
from web.feed_collector import TextType

from utils import ListFileReader 
from collections import Counter
from string import punctuation
#import spacy

import nltk
import time
import pickle

lfr = ListFileReader()
lfr.errors = 'ignore'


mock_signal1 = lfr.read_full_text('mocks/eurjpy_signal.txt')
mock_signal2 = lfr.read_full_text('mocks/audusd_signal.txt')

mock_story1 = lfr.read_full_text('mocks/usdjpy_story.txt')
mock_story2 = lfr.read_full_text('mocks/eurusd_story.txt')

mock_tutorial1 = lfr.read_full_text('mocks/tutorial1.txt')


#nlp  = spacy.load("en_core_web_lg")

#from spacy.pipeline.textcat_multilabel import DEFAULT_MULTI_TEXTCAT_MODEL 
#textcat_config = {
#	"threshold":0.5,
#	"model":DEFAULT_MULTI_TEXTCAT_MODEL
#}
#textcat = nlp.add_pipe("textcat", last=True) # this breaks :( - would be nice  to have it but ah well


fsh = ForexSlashHelper()

rss = feedco.RSSCollect(lfr.read('sources/rss_feeds.txt'))
rss.parse_feeds()
with open('pickles/stories.pkl','rb') as f:
	rss.articles = pickle.load(f)

#n = len(rss.articles)
#for (i,a) in enumerate(rss.articles):
#	print('fetching article '+str(i+1)+'/'+str(n)+ '... ')
#	a.fetch_full_text()
#
#with open('pickles/stories.pkl','wb') as f:
#	pickle.dump(rss.articles,f)

stopwords = set(nltk.corpus.stopwords.words('english'))

def pad(t):
	return ' ' + t + ' '

def keyworded(some_text):
	some_text = fsh.strip_slashes(some_text)
	keywords = [w for w in nltk.word_tokenize(some_text.lower()) if w not in punctuation and w not in stopwords]
	return Counter(keywords) 

#def spacy_keyworded(some_text):
#	some_text = fsh.strip_slashes(some_text)
#	document = nlp(some_text.lower())
#	keywords = [tok.text for tok in document if tok.text not in nlp.Defaults.stop_words and tok.pos_ in ['PROPN','ADJ','NOUN'] and tok.text not in punctuation]
#	return Counter(keywords)


def is_signal(some_text):
	
	#add to these as we discover more indicators that the text might be a signal
	take_profits = ['take profit','tp','tp1','tp2']
	stop_losss = ['stop loss','sl']
	
	some_text = fsh.strip_slashes(some_text)
	words = [w for w in nltk.word_tokenize(some_text.lower()) if w not in punctuation and w not in stopwords]
	new_text = ' '.join(words)
	
	if any(pad(o) in new_text for o in ['buy','sell']):
		if any(pad(o) in new_text for o in stop_losss):
			if any(pad(o) in new_text for o in take_profits):
				#pretty sus! we got a buy or sell together with a take profit and stop loss
				return True
	return False

def tutorial_title(some_title):
	all_lesson_words = ['explain','explanation','explained','explaining','learn','tutorial','lesson','guide','tips','top','discover']
	all_lesson_phrases = ['find out','learn how','learn which','learn when','learn why','learn what']
	
	words = [s for s in nltk.word_tokenize(some_title.lower())]
	return any(lw in words for lw in all_lesson_words) or any(pad(ph) in some_title.lower() for ph in all_lesson_phrases)
	
	
def is_tutorial(some_text,db=False): #use in conjunction with title? "find out", "learn", "tutorial" etc in title? 
	#err... check also for video or seminar
	some_text = fsh.strip_slashes(some_text.lower())
	#words = [w for w in nltk.word_tokenize(some_text.lower()) if w not in punctuation and w not in nlp.Defaults.stop_words]
	#new_text = ' '.join(words)
	words = [s for s in nltk.word_tokenize(some_text)]
	word_count = Counter(words)
	
	all_lesson_words = ['explain','explanation','explained','explaining','learn','tutorial','lesson','guide','tips','top','discover']
	all_personifiers = ['you','i','us','we','our','one']
	all_question_words = ['who','what','where','when','why','how']
		
	personifiers = sum(word_count[w] for w in all_personifiers)
	questionables = sum(word_count[w] for w in all_question_words)
	
	lesson_words  = sum(word_count[w] for w in all_lesson_words) #check lesson words - explain, learn, tutorial, lession ... ? 
	qmarks = len([c for c in some_text if c == '?'])
	
	if db:
		return {'questionables':questionables,'personifiers':personifiers,'lesson_words':lesson_words,'qmarks':qmarks}
	#document = nlp(some_text)
	return questionables + personifiers > 14 #parameter
	
	
def is_invitation(some_text):
	#might need to somehow filter out the averts within the text? 
	#-- join us, time and place, what - lesson / webinar/ seminar etc 
	#contact details etc?
	all_invitation_words = ['join','webinar','held','lesson','invited','invite','invitation','attend','learn']
	all_invitation_phrases = ['would you','will you','join us','come to','see our','watch our','view our']
	
	some_text = fsh.strip_slashes(some_text)
	words = [w for w in nltk.word_tokenize(some_text.lower()) if w not in punctuation and w not in nlp.Defaults.stop_words]
	word_count = Counter(words)
	
	new_text = ' '.join([w for w in words if w not in punctuation])
	
	invitation_words = sum(word_count[w] for w in all_invitation_words)
	invitation_phrases = sum(pad(p) in new_text for p in all_invitation_phrases)
	
	return is_tutorial(some_text) and invitation_words > 3 and invitation_phrases > 3


def get_text_type(article):
	the_type = TextType.STORY #default to story
	if is_signal(article.full_text):
		the_type = TextType.TRADE_SIGNAL
	if tutorial_title(article.title + ' ' + article.summary) and is_tutorial(article.full_text):
		the_type = TextType.TUTORIAL
	return the_type

#fx_pairs = lfr.read('fx_pairs/fx_mains.txt')
##cs = ClientSentiment(fx_pairs)##put fx pairs in!
##cs.fetch()
##use this for cherry-picking articles for mocks 
#(use fetch_full_text on an article. Eg: rss.articles[2].fetch_full_text() )
def show_articles():
	for (i,a) in enumerate(rss.articles):
		the_type = repr(get_text_type(a))
		print((' ' if i < 10 else '') + str(i) + ' - ' + str(the_type) + ' - ' + str(a)) 


#2!, 18!, 6, 7, 14, 78?,







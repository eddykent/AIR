

import time 



from web.crawler import Crawler, SeleniumHandler
from web.client_sentiment_indicators import ForexClientSentiment
from utils import ListFileReader


#with SeleniumHandler() as sh:
#sh = SeleniumHandler()  #will need to fix error with webdriver-manager to auto-detect chrome version somehow (report in install_instructions.md)
#sh.start()
#time.sleep(3)
#sh.finish()


def wait_for_me():
	input()


url = 'forexclientsentiment.com/client-sentiment'
#url = 'https://www.dukascopy.com/swiss/english/marketwatch/sentiment/'
lfr = ListFileReader()
fx_pairs = lfr.read('fx_pairs/fx_mains.txt')

with SeleniumHandler(hidden=True) as sh:
	fcsc = ForexClientSentiment(sh,url,fx_pairs)
	client_sentiment = fcsc.get_client_sentiment_info()
	#wait_for_me()

print(client_sentiment)
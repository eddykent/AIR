# test hoisting  
# tests should definitely be stored in their own directory!  
# to run a test, simply import it here from tests 
# for example, to run chart_tests.py run this: 
# from tests.chart_tests import *

from utils import LogSetup
LogSetup() #think of how to rmeove this line

#from tests.web_crawling_tests import *  #<<<<<< run this to get latest volume indicators from dukascopy bank 


#from tests.typedlist_test import *

#from tests.candle_stick_tests import *

from tests.chart_pattern_test import *
#from tests.chart_pattern_support_resistance_test import *
#from tests.matching_test import * 

#from tests.harmonic_pattern_test import *

#bat - 213,419,805

#from tests.text_sentiment_test import *
#from tests.fundamental_test import *     # <<<<<<run this to get latest articles easily. 
#from tests.news_reader_invoke_test import * #more testing required!  

#from tests.timeline_test import *
#from tests.backtest_test import *

#from tests.spacy_test import *

#from tests.setup_test import *
#from tests.logging_test import *
#from tests.data_compose_test import *
#from tests.data_compose_branch_test import *
#from tests.data_compose_fork_test import *


#from tests.shape_patterns_test import *
#from tests.candle_offset_test import *

#from tests.broker_test import *
#from tests.indicators_test import *
#from tests.volume_indicators_test import *



#from currency_strength_nn import *
##447 doesnt work? 

#wedge breakout 140 - lower line has points below it 

#from charting.chart_viewer import *
###570 works but isnt being drawn!!!


#list of working for TrianglePattern: 
#509 bearish
#510 bearish
#393 bullish
#394 bullish 



#from tests.save_articles_test import *

















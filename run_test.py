## test hoisting  
# tests should definitely be stored in their own directory!  
# to run a test, simply import it here from tests 
# for example, to run chart_tests.py run this: 
# from tests.chart_tests import *

from air.utils import LogSetup
LogSetup() #think of how to rmeove this line
#from _tests.web_crawling_tests import *  #<<<<<< run this to get latest volume indicators from dukascopy bank 
	  
	  
#from _tests.candle_stick_tests import * ##ancient?
	  
#from _tests.chart_pattern_test import * #works
#from _tests.chart_pattern_support_resistance_test import * #anicent, not working anymore (TODO)
#from _tests.matching_test import * #works (results not tested)

#bat - 213,419,805

from _tests.heikinashi_test import *

#from _tests.text_sentiment_test import *
#from _tests.fundamental_test import *     # <<<<<<run this to get latest articles easily. 
#from _tests.news_reader_invoke_test import * #more testing required!  

#from _tests.timeline_test import *
#from _tests.backtest_test import *

#from _tests.backtest_np_test import *

#from _tests.spacy_test import *

#
#from _tests.heikinashi_test  import *
#from _tests.setup_test import *
#from _tests.chart_pattern_collection_test import *
#from _tests.logging_test import *
#from _tests.data_compose_test import *
#from _tests. _compose_branch_test import *
#from _tests. _compose_fork_test import *


#from _tests.shape_patterns_test import *
#from _tests.candle_offset_test import *

#from _tests.broker_test import * << stops on start screen (element not found?) 
#from _tests.indicators_test import *
#from _tests.volume_indicators_test import *



#from currency_strength_nn import *
##447 doesnt work? 

#wedge breakout 140 - lower line has points below it 

#from charting.chart_viewer import *
###570 works but isnt being drawn!!!


#from _tests.divergence_test import *


#from _tests.filter_tests import * 1
#from _tests.ai_filter_tests import *
#from _tests.ai_train_test import *
#from _tests.advanced_filter_tests import *w
#from _tests.pandas_tests import *
 
#[Bat,Crab,Butterfly,Gartley,DeepCrab]
#from _tests.selenium_test import * 

#list of working for TrianglePattern: 
#509 bearish
#510 bearish
#393 bullish
#394 bullish 


#from _tests.save_articles_test import *


#from _tests.data_pull_tests import *
#if __name__ == "__main__":	
#	run_test()

#import debugging.charts as dbc

#from _tests.maths_indicator_test import *
#from _tests.background_test import *


#from debug.charts import *

#from _tests.all_trade_pro_test import *
#from _tests.all_trader_dna_test import *



#from _tests.article_convert_test import *


#from _tests.data_pull_tests import * #gmt fine (dukascopy)
#from _tests.news_pull_test import * #go through 1 by 1 to check gmt
#from _tests.market_snapshot_test import * #can be used, but only for the NOW (but gmt needs to be checked for accuracy)
#from _tests.economic_calendar_test import * #check each calendar for gmt
#if __name__ == "__main__":
#	run_test()
#	run_one()



#from _tests.strategy_test import *
#from _tests.strategy_inference_test import *
#from _tests.strategy_inference_filters_test import *














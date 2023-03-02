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

#from tests.chart_pattern_test import *
#from tests.chart_pattern_support_resistance_test import *
#from tests.matching_test import * 

#bat - 213,419,805

#from tests.heikinashi_test import *

#from tests.text_sentiment_test import *
#from tests.fundamental_test import *     # <<<<<<run this to get latest articles easily. 
#from tests.news_reader_invoke_test import * #more testing required!  

#from tests.timeline_test import *
#from tests.backtest_test import *

#from tests.backtest_np_test import *

#from tests.spacy_test import *

#
#from tests.heikinashi_test  import *
#from tests.setup_test import *
#from tests.chart_pattern_collection_test import *
#from tests.logging_test import *
#from tests.data_compose_test import *
#from tests. _compose_branch_test import *
#from tests. _compose_fork_test import *


#from tests.shape_patterns_test import *
#from tests.candle_offset_test import *

#from tests.broker_test import * << stops on start screen (element not found?) 
#from tests.indicators_test import *
#from tests.volume_indicators_test import *



#from currency_strength_nn import *
##447 doesnt work? 

#wedge breakout 140 - lower line has points below it 

#from charting.chart_viewer import *
###570 works but isnt being drawn!!!


#from tests.divergence_test import *


#from tests.filter_tests import * 1
#from tests.ai_filter_tests import *
#from tests.advanced_filter_tests import *w
#from tests.pandas_tests import *
 
#[Bat,Crab,Butterfly,Gartley,DeepCrab]
#from tests.selenium_test import * 

#list of working for TrianglePattern: 
#509 bearish
#510 bearish
#393 bullish
#394 bullish 


#from tests.selenium_test import *
#from tests.save_articles_test import *


from tests.data_pull_tests import *
if __name__ == "__main__":	
	run_test()

#import debugging.charts as dbc

#from tests.maths_indicator_test import *
#from tests.background_test import *


#from debug.charts import *

#from tests.all_trade_pro_test import *
#from tests.all_trader_dna_test import *



#from tests.article_convert_test import *

#from tests.news_pull_test import *
#from tests.market_snapshot_test import *
#if __name__ == "__main__":	
#	run_test()
#	run_one()
	
#from tests.strategy_test import *

#AUD/CAD broke db query (no results?) - re-run this! - keep latest AUD/CAD files!
#AUD/USD used wrong file so re-ran whole thing (check date in filename) 




















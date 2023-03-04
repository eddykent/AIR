#use this file to call training scripts - a training script will create a weights file/update a weights file in /models
#production grade stuff might have to be done differently but we atleast will have the weights file

from utils import LogSetup
LogSetup()

import pdb

from training.currency_strength import *
#from training.news_reader import *


#from training.train import CobwebCache
#cobweb = CobwebCache.load_cobweb('./pickles/cobwebs/NewsReaderData-test.json')
#pdb.set_trace()
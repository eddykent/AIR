

from utils import ListFileReader
from data.text import DirectKeywordInstrumentMap
#from data.tools.dbarticleconvert import DBArticleConverter
from data.tools.dbarticleconvert import FXStreetDateFix

#lfa = ListFileReader()
#fx_pairs = lfa.read('fx_pairs/fx_mains.txt')
#dkim = DirectKeywordInstrumentMap(fx_pairs=fx_pairs)
#dbac = DBArticleConverter(dkim) 
#dbac.run()


fxsdf = FXStreetDateFix()
fxsdf.fix_dates()













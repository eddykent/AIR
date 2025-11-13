from utils import ListFileReader 

from models.news_reader_model import NewsReaderModel
from models.model_base import ModelLoader 

nrm = NewsReaderModel(weights_label='main_set')
ml = ModelLoader(nrm)

lfr = ListFileReader()
some_news = lfr.read_full_text('mocks/gbpusd_story.txt')


result = ml.invoke([some_news])

while True:
	story = input("Paste a news story in here, then press enter.")
	print(ml.invoke([story]))
	
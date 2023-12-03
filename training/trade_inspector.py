

from tqdm import tqdm
import datetime

import pdb

from models.trade_inspector_model import TradeInspectorModel
from training.train import DataProvider, ModelComposer, ValidationMode
from utils import overrides, Database, ListFileReader, Inject
from web.scraper import Article


class TradeInspectorData(DataProvider): #? WHTA THE FUFVCMK
	pass
	#def __init__(self, signals, results):
		
	
	
	

def perform_training():
	trade_inspector_model = TradeInspectorModel(weights_label='main_set')
	trade_inspector_model.create_model()
	
	trade_data = TradeInspectorData(trade_inspector_model,row_cache_label='main_set')
	trade_data.begin_load()
	#pdb.set_trace()
	model_composer = ModelComposer(trade_inspector_model,trade_data)
	model_composer.train(epochs=3)
	model_composer.test([<TradeSignal>]) #list of trade signals in here 


perform_training()
	
	
	
	
	

from os import environ
environ["CUDA_VISIBLE_DEVICES"] = "-1"

import spacy

nlp = spacy.load("en_core_web_lg")
document = nlp("some text that loads just fine into a spacy doc")


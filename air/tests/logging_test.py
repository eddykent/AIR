

import pdb
import logging



class TestLogHandler(logging.Handler):
	
	def emit(self,record):
		pdb.set_trace()
		print('test what is in the record!')

log = logging.getLogger(__name__)
log.addHandler(TestLogHandler())
log.setLevel(logging.INFO)
try :
	t = 5 / 0
except Exception:
	log.info('a test log message',exc_info=True)
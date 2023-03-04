

from configparser import ConfigParser


#wrapper around SafeConfigParser to get any global config
class Configuration: 

	config_ini = './config.ini'
	parser = None
	
	def __init__(self,config_ini=None):
		self.parser = ConfigParser()
		#pdb.set_trace()
		self.config_ini = config_ini if config_ini is not None else self.config_ini
		self.parser.read(self.config_ini)
		
	def get(self,section,key):
		return self.parser.get(section,key)
	
	def database_connection_string(self):
		connection_keys = ['host','user','password','dbname']
		connection_details = {key:self.get('postgres',key) for key in connection_keys}
		return ' '.join(["%(key)s='%%(%(key)s)s'" % {'key':key} for key in connection_details]) % connection_details

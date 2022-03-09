##file for handling any broker operations so we can create a bot and run it, and place trades that way. 
##although t212 is the main one we will use for now, we can add another broker to this later. 
from collections import namedtuple
from collections.abc import Sequence, Mapping
from typing import Optional
from enum import Enum
import time
#import typecheck

import pdb


from trade_setup import TradeSignal, TradeDirection
from web.crawler import Keys, By, SeleniumHandler, ElementClickInterceptedException
from utils import overrides, Configuration, Database, TimeHandler


class TradeResult(Enum):
	LOST = -2
	LOSING = -1
	BALANCED = 0 
	WINNING = 1
	WON = 2 

#trades should be "fire and forget" 
#these are trades from the broker that we have already placed - not TradeSignal 
LiveTrade = namedtuple('LiveTrade','trade_id entry_date instrument quantity direction entry_price current_price take_profit stop_loss result')

class Broker:
	
	
	risk_percentage = 1.1 #percent risk for each trade - used for determining quanitity 
	
	#start putting docs in!
	""" Abstract class for ensuring all functionality for a broker handler is implemented """
	
	
	
	def begin(self) -> None:
		"""
		Start a session on the broker. Handle authentication and navigation to the dashboard etc
		
		Returns 	
		-------
		None 
		
		Raises
		------
		NotImplementedError
			This method is abstract and needs to be overridden in a concrete class
		"""		
		raise NotImplementedError("This method must be overridden")
	
	def account_info(self) -> dict:
		"""
		Gets all account information such as capital, open trades, etc
		
		Returns 	
		-------
		a dictionary containing various keys of account information  
		
		Raises
		------
		NotImplementedError
			This method is abstract and needs to be overridden in a concrete class
		"""		
		raise NotImplementedError("This method must be overridden")
	
	def finish(self) -> None:
		"""
		End session on the broker. For example, log out. 
		
		Returns 	
		-------
		None 
		
		Raises
		------
		NotImplementedError
			This method is abstract and needs to be overridden in a concrete class
		"""		
		raise NotImplementedError("This method must be overridden")
	
	def get_live_trades(self)  -> list:
		"""
		Get all trades that are currently open
		
		Returns 	
		-------
		list 
			a list of LiveTrade tuples	
		
		Raises
		------
		NotImplementedError
			This method is abstract and needs to be overridden in a concrete class
		"""
		raise NotImplementedError("This method must be overridden")
	
	def place_trade(self,trade_signal : TradeSignal, custom_lot_size=None) -> str:  #quantity?
		"""
		Places a new trade 
		
		Parameters
		----------
		trade_signal : TradeSignal
			The trade that we want to place, in the form of a trade signal 
		custom_lot_size : float
			Optional - if we want to put in a custom size (eg always use 1000 for all currency pairs )
		
		Returns 	
		-------
		str 
			An identifier of the new trade recieved from the broker
		
		Raises
		------
		NotImplementedError
			This method is abstract and needs to be overridden in a concrete class
		"""
		raise NotImplementedError("This method must be overridden")
	
	def get_trade(self,trade_id) -> Optional[LiveTrade]:
		"""
		Get a trade using its identifier. If the trade does not exist in the live set then the closed trades are queried 
		
		Parameters
		----------
		trade_id : str
			The trade id of the trade that we want to investigate
		
		Returns 	
		-------
		LiveTrade 
			Details of the trade that the broker is holding, with the trade_id as its identifier
		None
			If the trade doesn't exist
		
		Raises
		------
		NotImplementedError
			This method is abstract and needs to be overridden in a concrete class
		"""
		raise NotImplementedError("This method must be overridden")
	
	def pull_the_plug(self) -> None:
		"""
		Stop all live trades regardless of profit/loss. 
		This is mainly for sanity check more than anything! If stuff is going wrong we can always 
		call this function to get out asap.
		
		Raises
		------
		NotImplementedError
			This method is abstract and needs to be overridden in a concrete class
		"""
		raise NotImplementedError("This method must be overridden")
		
	
#class for performing all trade actions on trading 212
class Trading212(Broker):

	#a selenium handler 
	browser = None
	demo = True	
	
	def __init__(self,selenium_handler : SeleniumHandler):
		self.browser = selenium_handler
			
	
	#broker functions 
	@overrides(Broker)
	def get_live_trades(self):
		self.__clean_dash()
		_data_table_positions = {'tag':'div','subclass1':'data-table','subclass2':'positions'}
		_data_table_rows = {'tag':'div','class':'positions-table-item'}
		keys = { #use as a rename 
			'instrument':'instrument',
			'position-number':'trade_id',
			'quantity':'quantity',
			'position-direction':'direction',
			'price':'entry_price',
			'current-price':'current_price',
			'take-profit':'take_profit',
			'stop-loss':'stop_loss',
			'date-created':'entry_date',
			'result':'result_value' #wll use a converter to convert result into winning/losing 
		}
		live_trades = []
		
		data_table = self.browser.perform_wait(By.XPATH,"//{tag}[contains(@class,'{subclass1}') and contains(@class,'{subclass1}')]".format(**_data_table_positions))
		if data_table:
			data_table_rows = data_table.find_elements(By.XPATH,".//{tag}[@class='{class}']".format(**_data_table_rows))
			row_dicts = []
			for dtr in data_table_rows:
				row_dict = {}
				for key in keys:
					row_dict[key] = dtr.find_element(By.CLASS_NAME,key)
				row_dicts.append(row_dict)
		'trade_id entry_date instrument quantity direction entry_price current_price take_profit stop_loss result'
		
		for row in row_dicts:
			live_trade_dict = {}
			for k in keys:
				nk = keys[k]
				if k == 'quantity':
					live_trade_dict[nk] = float(row[k].text.replace(',','')) 
				elif k == 'position-direction':
					live_trade_dict[nk] = TradeDirection.VOID
					if row[k].text.strip().upper() == 'BUY':
						live_trade_dict[nk] = TradeDirection.BUY
					if row[k].text.strip().upper() == 'SELL':
						live_trade_dict[nk] = TradeDirection.SELL
				elif k == 'price':
					live_trade_dict[nk] = float(row[k].text.strip())
				elif k == 'current-price':
					live_trade_dict[nk] = float(row[k].text.strip())
				elif k == 'take-profit':
					if row[k].text.strip() == '-':
						live_trade_dict[nk] = None
					else:
						live_trade_dict[nk] = float(row[k].text.strip())
				elif k == 'stop-loss':
					if row[k].text.strip() == '-':
						live_trade_dict[nk] = None
					else:
						live_trade_dict[nk] = float(row[k].text.strip())
				elif k == 'date-created':
					live_trade_dict[nk] = TimeHandler.from_str_1(row[k].text.strip())
				elif k == 'result':
					if '-' in row[k].text:
						live_trade_dict['result'] = TradeResult.LOSING
					else:
						live_trade_dict['result'] = TradeResult.WINNING
				
				
				else:
					live_trade_dict[nk] = row[k].text.strip().upper()
			live_trades.append(LiveTrade(**live_trade_dict))
		return live_trades
	
	@overrides(Broker)
	def place_trade(self,trade_signal):
		pass 
	
	@overrides(Broker)
	def get_trade(self,trade_id):
		trades = self.get_live_trades()
		for t in trades:
			if t.trade_id == trade_id:
				return t
		#shit... looks like we need to look through historic stuff 
		
		
		
		

			
		
	
	@overrides(Broker)
	def pull_the_plug(self):
		_close_all_btn = {'tag':'div','subclass':'close-all-icon'}
		_close_all_btn_in_drop = {'tag':'div','subclass1':'quick-close-all-option','subclass2':'close-all'}
		_quick_close_all = {'tag':'div','subclass':'dropdown-quick-close-all'}
		_close_all_content = {'tag':'div','class':'quick-close-all-content'}
		_sub_button_close = {'tag':'div','class':'sliding-button'}
		#_parent_animation = {'tag':'div','subclass':'dropdown-animation-enter-done'}
		
		
		
		close_all_btn = self.browser.perform_wait(By.XPATH,"//{tag}[contains(@class,'{subclass}')]".format(**_close_all_btn))
		
		#wait for some other elements to confirm everything has loaded
		quick_close_container = self.browser.perform_wait(By.XPATH,"//{tag}[contains(@class,'{subclass}')]".format(**_quick_close_all))
		
		if ' disabled ' in quick_close_container.get_attribute('class'):
			#it is disabled - you must not have any trades open .Perhaps an assert here would be good! 
			pass
		else:
			self.browser.click_on(close_all_btn)
			close_all_content = self.browser.perform_wait(By.XPATH,"//{tag}[@class='{class}']".format(**_close_all_content))
			
			close_all_btn_in_drop = self.browser.perform_wait(By.XPATH,"//{tag}[contains(@class,'{subclass1}') and contains(@class,'{subclass2}')]".format(**_close_all_btn_in_drop))
			
			pdb.set_trace()
			
			self.browser.click_on(close_all_btn_in_drop)  #check for disabled
			
			
			
			sub_button_close = close_all_content.find_element(By.XPATH,".//{tag}[@class='{class}']".format(**_sub_button_close))
			self.browser.click_on(sub_button_close) #works - we got to 
		
		
		
	
	@overrides(Broker)
	def begin(self):
		self.__begin() #handles authentication and gets to the right dashboard
		self.__ensure_demo()
		self.__clean_dash()		

	@overrides(Broker)
	def finish(self):
		self.__finish()
	
	#private t212 helper functions - waits for all stuff to be loaded. Then makes sure all columns are visible to extract live trades
	def __clean_dash(self):
		
		_chart_elem = {'tag':'div','class':'chartLayer'}
		_new_order = {'tag':'div','subclass':'new-order-icon'}
		_close_all = {'tag':'div','subclass':'close-all-icon'}
		_home = {'tag':'div','subclass':'home-icon'}
		_settings = {'tag':'div','subclass':'settings-icon'}
		_close_btns = {'tag':'div','class':'close-button-wrapper'}
		_close_btn = {'tag':'div','subclass':'close-button'}
		_position_data_table = {'tag':'div','subclass1':'positions','subclass2':'data-table'}
		_checkbox_bit = {'tag':'div','subclass1':'data-table-settings-dropdown-items','subclass2':' dropdown-items '}
		_sub_checkbox_bit = {'tag':'div', 'subclass':'selectable-list-item'}
		_chart_tabs = {'tag':'div','class':'trading-chart-tab-item'}
		
		print('click home button')
		#first, check we are loaded. To do so, perfom some waits without actually getting the elems
		home = self.browser.perform_wait(By.XPATH,"//{tag}[contains(@class,'{subclass}')]".format(**_home))
		self.browser.click_on(home) 
		
		#now wait for more stuff... 
		print('wait for chart')
		chart_elem = self.browser.perform_wait(By.XPATH,"//{tag}[@class='{class}']".format(**_chart_elem)) #dont grab - we are merely ensureing everying is loaded
		self.browser.perform_wait(By.XPATH,"//{tag}[contains(@class,'{subclass}')]".format(**_new_order)) #check all these exist
		self.browser.perform_wait(By.XPATH,"//{tag}[contains(@class,'{subclass}')]".format(**_close_all))
		
		print('click chart to close dropdowns')		
		self.browser.click_on(chart_elem) # closes all dropdowns 
		
		print('try click close chart buttons to close all charts')
		#close all charts we don't need. 
		chart_tab = self.browser.perform_wait(By.XPATH,"//{tag}[@class='{class}']".format(**_chart_tabs),1)
		n_chart_tabs = len(self.browser.find_elements(By.XPATH,"//{tag}[@class='{class}']".format(**_chart_tabs)))
		while chart_tab is not None and n_chart_tabs > 0: #inf loop?
			chart_close = chart_tab.find_element(By.XPATH,".//{tag}[@class='{class}']".format(**_close_btns))
			close_button = chart_close.find_element(By.XPATH,".//{tag}[contains(@class,'{subclass}')]".format(**_close_btn))
			self.browser.click_on(close_button) #may need a second click
			chart_tab = self.browser.perform_wait(By.XPATH,"//{tag}[@class='{class}']".format(**_chart_tabs),0.2)
			n_chart_tabs -= 1
			
		print('click settings in positions table')
		#ensure all columns exist 
		position_data_table = self.browser.perform_wait(By.XPATH,"//{tag}[contains(@class,'{subclass1}') and contains(@class,'{subclass2}')]".format(**_position_data_table))
		settings = position_data_table.find_element(By.XPATH,".//{tag}[contains(@class,'{subclass}')]".format(**_settings)) #perhaps use a wrapper?
		self.browser.click_on(settings)
		
		
		
		#now wait for  menu to appear, then wait a bit more for the animation to stop? 
		checkbox_panel = self.browser.perform_wait(By.XPATH,"//{tag}[contains(@class,'{subclass1}') and contains(@class,'{subclass2}')]".format(**_checkbox_bit))
		checkboxes = checkbox_panel.find_elements(By.XPATH,".//{tag}[contains(@class,'{subclass}')]".format(**_sub_checkbox_bit))
		
		for checkbox in checkboxes:
			if ' selected' not in checkbox.get_attribute('class'):
				self.browser.click_on(checkbox)  #enable the lot for easier querying
		
		print('click chart to close dropdowns')		#re-query to prevent stale elem exception and robustness
		chart_elem = self.browser.perform_wait(By.XPATH,"//{tag}[@class='{class}']".format(**_chart_elem))
		self.browser.click_on(chart_elem) # closes all dropdowns 
		
	#logging into t212 to bring up the dashboard. 
	def __begin(self):
			#list element queries here. Change if the broker changes them - they look like something that might be changed often 
		_login_button = {'tag':'p','subclass':'header_login-button__daXsh'}
		_login_modal = {'tag':'div','subclass':'authentication-popup_authentication-popup__dNPPM'} 
		_cookies_modal_btn = {'tag':'div','class':'button_button__tDDzY button_accent__dYsGU cookies-notice_button__3K8cT cookies-notice_button-accent__2rm8R'}
		_login_email = {'tag':'input','subclass':'labeled-input_input__6yVAo','type':'email'}  #type=email
		_login_pass = {'tag':'input','subclass':'labeled-input_input__6yVAo','type':'password'}	#type=password
		_login_remember = {'tag':'input','name':'rememberMe', 'type':'checkbox'}
		_login_login = {'tag':'input','type':'submit','value':'Log in'}
		
		config = Configuration()
		self.browser.get(config.get('trading212','demo_url' if self.demo else 'live_url')) #although this says to go to demo, it doesnt always! 
	
		#top right hand corner login button to open modal 
		login_button = self.browser.perform_wait(By.XPATH,"//{tag}[contains(@class,'{subclass}')]".format(**_login_button))
		login_modal = self.browser.perform_wait(By.XPATH,"//{tag}[contains(@class,'{subclass}')]".format(**_login_modal))
		
		accept_cookies = self.browser.perform_wait(By.XPATH,"//{tag}[@class='{class}']".format(**_cookies_modal_btn))
		
		if accept_cookies:
			self.browser.click_on(accept_cookies)
		
		if not login_modal:
			self.browser.click_on(login_button)
			login_modal = self.browser.perform_wait(By.XPATH,"//{tag}[contains(@class,'{subclass}')]".format(**_login_modal))
		
		
		
		login_email = self.browser.perform_wait(By.XPATH,"//{tag}[contains(@class,'{subclass}') and @type='{type}']".format(**_login_email))
		login_pass = self.browser.perform_wait(By.XPATH,"//{tag}[contains(@class,'{subclass}') and @type='{type}']".format(**_login_pass))
		login_remember = self.browser.perform_wait(By.XPATH,"//{tag}[@name='{name}' and @type='{type}']".format(**_login_remember))
		
		#actual log in button 
		login_login = self.browser.perform_wait(By.XPATH,"//{tag}[@type='{type}' and @value='{value}']".format(**_login_login))
		
		
		login_email.send_keys(config.get('trading212','username'))
		login_pass.send_keys(config.get('trading212','password'))
		
		if login_remember.is_selected():
			self.browser.click_on(login_remember) #dont remember for the bot
		
		self.browser.click_on(login_login) #go! 
		
	def __ensure_demo(self):
		_acc_menu_header = {'tag':'div','class':'account-menu-header'}
		_acc_menu_reveal = {'tag':'div','subclass':'arrow'}
		_acc_menu_demo_btn = {'tag':'div','subclass':'switch-to-demo-button'}
		_acc_menu_live_btn = {'tag':'div','subclass':'switch-to-live-button'}
		
		
		loading_wait = 15 #slightly longer since t212 can be slow to load sometimes
		button_wait = 0.9
		
		header = self.browser.perform_wait(By.XPATH,"//{tag}[@class='{class}']".format(**_acc_menu_header),loading_wait)
		reveal  = header.find_element(By.XPATH,".//{tag}[contains(@class,'{subclass}')]".format(**_acc_menu_reveal))
		
		demo_btn = self.browser.perform_wait(By.XPATH,"//{tag}[contains(@class,'{subclass}')]".format(**_acc_menu_demo_btn),button_wait)
		live_btn = self.browser.perform_wait(By.XPATH,"//{tag}[contains(@class,'{subclass}')]".format(**_acc_menu_live_btn),button_wait)
		
		if not demo_btn and not live_btn:
			self.browser.click_on(reveal) 
		
		demo_btn = self.browser.perform_wait(By.XPATH,"//{tag}[contains(@class,'{subclass}')]".format(**_acc_menu_demo_btn),button_wait)
		live_btn = self.browser.perform_wait(By.XPATH,"//{tag}[contains(@class,'{subclass}')]".format(**_acc_menu_live_btn),button_wait)
		
		if self.demo and demo_btn:
			demo_btn.click()
		
		if not self.demo and live_btn:
			live_btn.click()
			
				
	#logging out of T212 
	def __finish(self):	
		_acc_menu_header = {'tag':'div','class':'account-menu-header'}
		_acc_menu_reveal = {'tag':'div','subclass':'arrow'}
		_acc_menu_logout = {'tag':'div','class':'action-button','data-qa-action-btn':'btn-logout'}
		_modal_confirm_btn = {'tag':'div','class':'logout-dialog'}
		
		header = self.browser.perform_wait(By.XPATH,"//{tag}[@class='{class}']".format(**_acc_menu_header))
		reveal  = header.find_element(By.XPATH,".//{tag}[contains(@class,'{subclass}')]".format(**_acc_menu_reveal))
		self.browser.click_on(reveal)
		
		logout = self.browser.perform_wait(By.XPATH,"//{tag}[@class='{class}' and @data-qa-action-btn='{data-qa-action-btn}']".format(**_acc_menu_logout))
		if logout:
			self.browser.click_on(logout)
			
			sure_logout = self.browser.perform_wait(By.XPATH,"//div[@class='logout-dialog']/div[@class='buttons']/div[contains(@class,'confirm-button')]")
			self.browser.click_on(sure_logout)
		
		
		
		
		
		
		
		
#other brokers will have an API so their handling class will be tiny 	
		
		
		
		
		
		
		
		
		
		
		
	
	
	
	
	










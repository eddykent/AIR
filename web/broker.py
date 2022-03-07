##file for handling any broker operations so we can create a bot and run it, and place trades that way. 
##although t212 is the main one we will use for now, we can add another broker to this later. 
from collections import namedtuple
from collections.abc import Sequence, Mapping
from typing import Optional
from enum import Enum
#import typecheck

import pdb


from trade_setup import TradeSignal, TradeDirection
from web.crawler import Keys, By, SeleniumHandler
from utils import overrides, Configuration, Database


class TradeResult(Enum):
	LOST = -2
	LOSING = -1
	BALANCED = 0 
	WINNING = 1
	WON = 2 

#trades should be "fire and forget" 
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
	
	def place_trade(self,trade_signal : TradeSignal, custom_lot_size=None, strategy_name='Test' ) -> str:  #quantity?
		"""
		Places a new trade 
		
		Parameters
		----------
		trade_signal : TradeSignal
			The trade that we want to place, in the form of a trade signal 
		custom_lot_size : float
			Optional - if we want to put in a custom size (eg always use 1000 for all currency pairs )
		strategy_name : str 
			Optional - if this trade came from some strategy we can log the name of it in the database
		
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
		return []
	
	@overrides(Broker)
	def place_trade(self,trade_signal):
		pass 
	
	@overrides(Broker)
	def get_trade(self,trade_id):
		pass
	
	@overrides(Broker)
	def pull_the_plug(self):
		_close_all_btn = {'tag':'div','subclass':'close-all-icon'}
		_close_all_btn_in_drop = {'tag':'div','subclass1':'quick-close-all-option','subclass2':'close-all'}
		_close_all_content = {'tag':'div','class':'quick-close-all-content'}
		_sub_button_close = {'tag':'div','class':'sliding-button'}
		
		
		close_all_btn = self.browser.perform_wait(By.XPATH,"//{tag}[contains(@class,'{subclass}')]".format(**_close_all_btn))
		close_all_btn.click()
		
		close_all_content = self.browser.perform_wait(By.XPATH,"//{tag}[@class='{class}']".format(**_close_all_content))
		
		close_all_btn_in_drop = self.browser.perform_wait(By.XPATH,"//{tag}[contains(@class,'{subclass1}') and contains(@class,'{subclass2}')]".format(**_close_all_btn_in_drop))
		close_all_btn_in_drop.click() 
		
		sub_button_close = close_all_content.find_element(By.XPATH,".//{tag}[@class='{class}']".format(**_sub_button_close))
		#print('sub button close exist?')
		#pdb.set_trace()
		#sub_button_close.click() #is there a confirm? 
		
	
	@overrides(Broker)
	def begin(self):
		self.__begin() #handles authentication and gets to the right dashboard
		self.__ensure_demo()

	@overrides(Broker)
	def finish(self):
		self.__finish()
	
	#private t212 helper functions
	def __clean_dash(self):
		#close all open charts, close all dropdowns, ensure all columns are showing etc
		pass
	
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
			accept_cookies.click()
		
		if not login_modal:
			login_button.click()
			login_modal = self.browser.perform_wait(By.XPATH,"//{tag}[contains(@class,'{subclass}')]".format(**_login_modal))
		
		
		
		login_email = self.browser.perform_wait(By.XPATH,"//{tag}[contains(@class,'{subclass}') and @type='{type}']".format(**_login_email))
		login_pass = self.browser.perform_wait(By.XPATH,"//{tag}[contains(@class,'{subclass}') and @type='{type}']".format(**_login_pass))
		login_remember = self.browser.perform_wait(By.XPATH,"//{tag}[@name='{name}' and @type='{type}']".format(**_login_remember))
		
		#actual log in button 
		login_login = self.browser.perform_wait(By.XPATH,"//{tag}[@type='{type}' and @value='{value}']".format(**_login_login))
		
		
		login_email.send_keys(config.get('trading212','username'))
		login_pass.send_keys(config.get('trading212','password'))
		
		if login_remember.is_selected():
			login_remember.click() #dont remember for the bot
		
		login_login.click() #go! 
		
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
			reveal.click() 
		
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
		reveal.click()
		
		logout = self.browser.perform_wait(By.XPATH,"//{tag}[@class='{class}' and @data-qa-action-btn='{data-qa-action-btn}']".format(**_acc_menu_logout))
		if logout:
			logout.click()
			
			sure_logout = self.browser.perform_wait(By.XPATH,"//div[@class='logout-dialog']/div[@class='buttons']/div[contains(@class,'confirm-button')]")
			sure_logout.click()
		
		
		
		
		
		
		
		
		
		
		
		
		
		
		
		
		
		
		
		
	
	
	
	
	










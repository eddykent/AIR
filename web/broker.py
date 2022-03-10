##file for handling any broker operations so we can create a bot and run it, and place trades that way. 
##although t212 is the main one we will use for now, we can add another broker to this later. 
from collections import namedtuple
from collections.abc import Sequence, Mapping
from typing import Optional, List
from enum import Enum
import time
#import typecheck

import pdb


from trade_setup import TradeSignal, TradeDirection
from web.crawler import Keys, By, SeleniumHandler, ElementClickInterceptedException, XPathNavigator
from utils import overrides, Configuration, Database, TimeHandler


class TradeResult(Enum):
	LOST = -2
	LOSING = -1
	BALANCED = 0 
	WINNING = 1
	WON = 2 

#consider:
#HoursRow = namedtuple('HoursRow','monday tuesday wednesday thursday friday saturday sunday')
#MarketHours = namedtuple('MarketHours','open close')

#trades should be "fire and forget" 
#these are trades from the broker that we have already placed - not TradeSignal 
LiveTrade = namedtuple('LiveTrade','trade_id entry_date close_date instrument quantity direction entry_price current_price take_profit stop_loss result')
InstrumentInfo = namedtuple('InstrumentInfo','name full_name currency margin leverage spread_ratio short_interest long_interest interest_time min_quantity exchange market_hours')
AccountStatus = namedtuple('AccountStatus','live_result free_funds blocked_funds percentage_blocked number_trades_open')

class Broker:
	
	
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
	
	def get_account_info(self) -> AccountStatus:
		"""
		Gets all account information such as capital, open trades and more 
		
		Returns 	
		-------
		An AccountStatus object that holds all information about the connected account. 
		
		Raises
		------
		NotImplementedError
			This method is abstract and needs to be overridden in a concrete class
		"""		
		raise NotImplementedError("This method must be overridden")
	
	
	def get_instrument_info(self,instrument : str) -> Optional[InstrumentInfo]:
		"""
		Gets any information about an instrument. Since this takes a long time it is recommened to get all instrument info  
		first and then storing the result before doing any advanced calculations or trade executions. The result does not 
		change that much - the spread may change over time but most other things can be considered constant. Therefore the
		data will remain valid all day. 
		
		Returns
		-------
		An InstrumentInfo object if it found the instrument, or None if it couldn't find the instrument. 
				
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
	
	def get_live_trades(self)  -> List[LiveTrade]:
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
	
	def get_historic_trades(self,trade_ids) -> List[LiveTrade]:
		"""
		Gets trades using their identifier. If the trade does not exist in the live set then the closed trades are queried. If they don't exist either then None is returned
		
		Parameters
		----------
		trade_ids : list of str
			The trade ids of the trades that we want to collect
		
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
		
	
#class for performing all trade actions on trading 212. Very exhaustive because they have no API 
class Trading212(Broker, XPathNavigator):

	#a selenium handler 
	#browser = None
	demo = True	
	config = None
	
	
	#private data containers 
	Position = namedtuple('Position','close_date instrument position_number currency entry_date')
	Result = namedtuple('Result','close_date instrument direction quantity price close_price result')
	
	def __init__(self,selenium_handler):
		t212_url = selenium_handler.config.get('trading212','demo_url' if self.demo else 'live_url')
		super().__init__(selenium_handler,t212_url)
	
	#broker functions 
	@overrides(Broker)
	def get_live_trades(self):
		
		self.__clean_dash()
		_data_table_positions = {'tag':'div','subclass1':'data-table','subclass2':'positions'}
		_data_table_rows = {'tag':'div','class':'positions-table-item'}
		
		self.__ensure_trades_view()
		
		keys = { #use as a rename - class -> our own name 
			'instrument':'instrument',
			'position-number':'trade_id',
			'quantity':'quantity',
			'position-direction':'direction',
			'price':'entry_price',
			'current-price':'current_price',
			'take-profit':'take_profit',
			'stop-loss':'stop_loss',
			'date-created':'entry_date',
			'result':'result' #wll use a converter to convert result into winning/losing 
		}
		live_trades = []
		#looks useful - perhaps move to crawler? 
		data_table = self.get_element(_data_table_positions)
		if data_table:
			data_table_rows = self.get_multiple_elements([_data_table_positions,_data_table_rows])
			live_trade_dicts = self.process_website_rows(By.CLASS_NAME, data_table_rows, keys)
			for live_trade_dict in live_trade_dicts:
				self.process_row_floating_points(live_trade_dict,['quantity','entry_price','current_price','take_profit','stop_loss','result'])
				live_trade_dict['trade_id'] = live_trade_dict['trade_id'].upper()
				live_trade_dict['entry_date'] = TimeHandler.from_str_1(live_trade_dict['entry_date'])
				
				buff = 0 #set to 0.01 or a percentage or something - get from config?
				
				live_trade_dict['result'] = TradeResult.BALANCED  #calculte the result 
				if live_trade_dict['current_price'] < live_trade_dict['entry_price'] - buff:
					live_trade_dict['result'] = TradeResult.LOSING # aww :(
				if live_trade_dict['current_price'] > live_trade_dict['entry_price'] + buff:
					live_trade_dict['result'] = TradeResult.WINNING # YAY!! :D 
					
				live_trade_dict['close_date'] = None  #we dont have a close date on these yet 
				
				live_trades.append(LiveTrade(**live_trade_dict))
		return live_trades
	
	@overrides(XPathNavigator)
	def crawl(self):
		return # don't do anything since we dont actually call crawl for Trading212 - we could do later though with get_instrument_info!
	
	@overrides(Broker)
	def place_trade(self,trade_signal):
		
		




		
	
	@overrides(Broker)
	def get_historic_trades(self,trade_ids):
		
		def xkey(x):
			return x.close_date+'-'+x.instrument
		
		def data2livetrade(data):
			pos, res = data[:2]
			#we cant get the TP and SL orders :(
			buff = 0
			result_enum = TradeResult.BALANCED
			if res.result < 0 - buff:
				result_enum = TradeDirection.LOST
			if res.result > 0 + buff:
				result_enum = TradeResult.WON
			
			entry_date = TimeHandler.from_str_1(pos.entry_date,date_delimiter='/')
			close_date = TimeHandler.from_str_1(pos.close_date,date_delimiter='/')
			
			return LiveTrade(\
				pos.position_number,\
				entry_date,\
				close_date,\
				pos.instrument,\
				res.quantity, \
				res.direction, \
				res.price, \
				res.close_price, \
				None,\
				None, \
				result_enum\
			)
		
		collected = {}
		
		live_trades = self.get_live_trades()
		for trade_id in trade_ids:
			for t in live_trades:
				if t.trade_id == trade_id:
					collected[trade_id] = t
		
		still_to_collect = [t for t in trade_ids if t not in collected]
		if still_to_collect:
			#damn... time to go to the reports modal then
			positions = self.__get_all_old_positions(leave_open=True)
			results = self.__get_all_old_results()
			
			#filter for positions we don't care about. 
			positions = [p for p in positions if p.position_number in still_to_collect]
			
			#key by similar info between position and result rows from the reports modal
			positions_keyed = {xkey(p) : [p] for p in positions}
			results_keyed = {xkey(r) : [r] for r in results}
			for pkey in positions_keyed:
				if pkey in results_keyed:
					positions_keyed[pkey].extend(results_keyed[pkey])
			
			#now key by position_number
			old_data_results = {data[0].position_number : data for pkey, data in positions_keyed.items()}
			for trade_id in still_to_collect:
				if trade_id in old_data_results:				
					collected[trade_id] = data2livetrade(old_data_results[trade_id])
			
		results = []
		for trade_id in trade_ids:
			results.append(collected.get(trade_id))
		
		#pdb.set_trace()
		return results 
		#now go to result tab and get the rest of the details, querying by close date and instrument name 

		
	@overrides(Broker)
	def get_account_info(self):
		
		_status_bar = {'tag':'div','subclass':'status-bar'}
		_status_bar_items = {'tag':'div','class':'status-bar-item'}
		
		_data_table_positions = {'tag':'div','subclass1':'data-table','subclass2':'positions'}
		_data_table_rows = {'tag':'div','class':'positions-table-item'}
		
		self.__ensure_trades_view()
		
		status_bar_items = self.get_multiple_elements([_status_bar,_status_bar_items])
		floatpoints = [self.safefloat(self.get_text(sbi)) for sbi in status_bar_items]
		
		data_table = self.get_element(_data_table_positions)
		data_table_rows = self.get_multiple_elements([_data_table_positions,_data_table_rows])
		n_trades = len(data_table_rows)
		
		live_result =  floatpoints[0]
		free_funds = floatpoints[1]
		blocked_funds = floatpoints[2]
		percent_blocked = int(floatpoints[3]) if floatpoints[3] is not None else None
		
		return AccountStatus(live_result,free_funds,blocked_funds,percent_blocked,n_trades)
		
	@overrides(Broker)
	def get_instrument_info(self,instrument_name):
		
		#stuff for the search bar
		_search_icon_parent = {'tag':'div', 'class':'sidepanel-tab-content'}
		_search_icon = {'tag':'div','subclass':'search-icon'}
		_search_bar = {'tag':'input','subclass':'search-input','placeholder':'Search all instruments'}
		_search_results = {'tag':'div','class':'search-results-content'}
		
		#stuff for getting search results 
		_instrument_row = {'tag':'div','subclass':'search-results-instrument', 'data-qa-code':instrument_name.replace('/','').upper()}
		_instrument_rows = {'tag':'div','subclass':'search-results-instrument'}
		_symbol_cell = {'tag':'div','subclass1':'search-results-instrument-cell','subclass2':'cell-symbol'}	

		#handling the popup modal 
		_instrument_modal = {'tag':'div','class':'trading-chart-layout'} 
		_instrument_modal_close = {'tag':'div','subclass':'close-button'}
		
		#getting the instrument data table 
		_instrument_additional_info = {'tag':'div','subclass':'instrument-additional-info'}
		_collapsible = {'tag':'div','subclass':'collapsible-section'}
		_instrument_info_item = {'tag':'div','class':'instrument-additional-info-item'}
		
		#finally lets click the home button to keep things in the beginning state
		_home = {'tag':'div','subclass':'home-icon'}
		
		#self.__clean_dash() #ensure start at the beginning 
		search_icon = self.get_element([_search_icon_parent,_search_icon])
		self.click_on(search_icon)
		
		search_bar = self.get_element(_search_bar)
		
		self.click_on(search_bar)
		
		#may be buggy - t212 calls on each key 
		self.type_keys_on(search_bar,instrument_name)
		self.press_enter_on(search_bar)
		
		#try to get the row by the data-qa-code first
		instrument_row = self.get_element([_instrument_row,_symbol_cell],0.5)	#data-qa-code might change one day :(
		
		if instrument_row is None:
			#get a bunch of instrument rows and search them for the instrument name
			instrument_rows = self.get_multiple_elements([_instrument_rows,_symbol_cell])  
			for instrument_row in instrument_rows:
				if instrument_name.upper() in self.get_text(instrument_row).upper():
					break #we found the right instrument
		
		if not instrument_name.upper() in self.get_text(instrument_row).upper():
			pdb.set_trace()
			print('ah, damn we know the instrument exists...')
			return None #the instrument was just the last on the list - incorrect! Therefore the instrument was not found. 
		
		self.click_on(instrument_row)
		self.get_element(_instrument_modal) #wait for modal to load
		close_modal = self.get_element([_instrument_modal,_instrument_modal_close])
		
		collapsing_view = self.get_element([_instrument_modal,_instrument_additional_info,_collapsible])
		if not ' expanded' in self.get_attribute(collapsing_view,'class'): #lets expand the instrument details
			self.click_on(collapsing_view) 
		
		row_items = self.get_multiple_elements([_instrument_modal,_instrument_additional_info,_instrument_info_item])
		#name full_name currency margin leverage spread_percentage short_interest long_interest interest_time min_quantity exchange market_hours#
		column_keys = { #label name - > our name
			'FULL NAME':'full_name',
			'CURRENCY':'currency',
			'MARGIN':'margin',
			'LEVERAGE':'leverage',
			'SHORT POSITION OVERNIGHT INTEREST':'short_interest',
			'LONG POSITION OVERNIGHT INTEREST':'long_interest',
			'OVERNIGHT INTEREST TIME':'interest_time',
			'MIN TRADED QUANTITY':'min_quantity',
			'MARKET NAME':'exchange',
			'BUY PRICE':'buy_price',
			'SELL PRICE':'sell_price'
		}
		dict_row = {}
		for text_piece in [self.get_text(row_item) for row_item in row_items]:
			text_pieces = [t for t in [tp.strip() for tp in text_piece.split('\n')] if t]
			if len(text_pieces) >= 2:
				if text_pieces[0] in column_keys:
					dict_row[column_keys[text_pieces[0]]] = text_pieces[1]
		
		levstrb = dict_row.get('leverage','').split(':')
		dict_row['leverage'] = levstrb[1] if len(levstrb) > 1 else dict_row.get('leverage')  #from a str of '1:40' get the 40
		dict_row['short_interest'] = dict_row.get('short_interest','')
		dict_row['long_interest'] = dict_row.get('long_interest','')
		
		self.process_row_floating_points(dict_row,['leverage','margin','short_interest','long_interest','min_quantity','buy_price','sell_price'])
		self.process_row_ints(dict_row,['leverage'])
		
		buy = dict_row.get('buy_price')
		sell = dict_row.get('sell_price')
		
		dict_row['spread_ratio'] = ((buy - sell) / sell) if (buy is not None and sell is not None) else None
		dict_row['margin'] = dict_row.get('margin',0) / 100 # it is percentage so convert it back
		del dict_row['buy_price']
		del dict_row['sell_price']
		
		#ensure keys
		ensure_keys = ['name','full_name','currency','margin','leverage',\
				'spread_ratio','short_interest','long_interest',\
				'interest_time','min_quantity','exchange','market_hours']
		for ek in ensure_keys:
			dict_row[ek] = dict_row.get(ek)
		
		self.click_on(close_modal) 
		home = self.get_element(_home)
		self.click_on(home) 
		
		return InstrumentInfo(**dict_row)
			
	
	@overrides(Broker)
	def pull_the_plug(self):
	
		_close_all_btn = {'tag':'div','subclass':'close-all-icon'}
		_close_all_btn_in_drop = {'tag':'div','subclass1':'quick-close-all-option','subclass2':'close-all'}
		_quick_close_all = {'tag':'div','subclass':'dropdown-quick-close-all'}
		_close_all_content = {'tag':'div','class':'quick-close-all-content'}
		_sub_button_close = {'tag':'div','class':'sliding-button'}
		
		self.__ensure_trades_view()
		
		#wait for some other elements to confirm everything has loaded
		quick_close_container = self.get_element(_quick_close_all)
		
		if ' disabled ' in quick_close_container.get_attribute('class'):
			live_trades = self.get_live_trades()
			assert len(live_trades) == 0, "We are unable to close all our trades!"
			
		else:
			close_all_btn = self.get_element(_close_all_btn)
			self.click_on(close_all_btn)
			
			close_all_btn_in_drop = self.find_element(_close_all_btn_in_drop)
			self.click_on(close_all_btn_in_drop)  #check for disabled
			
			sub_button_close = self.find_element([_close_all_content,_sub_button_close])
			self.click_on(sub_button_close) #works - we got to 
		
		
		
	
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
		home = self.get_element(_home)
		self.click_on(home) 
		
		#now wait for more stuff... 
		print('wait for chart')
		chart_elem = self.get_element(_chart_elem) 
		self.get_element(_new_order) #check all these exist
		self.get_element(_close_all)		
		
		print('click chart to close dropdowns')		
		self.click_on(chart_elem) # closes all dropdowns 
		
		print('try click close chart buttons to close all charts')
		#close all charts we don't need. 
		#chart_tab = self.get_element(_chart_tabs,expire=0.2)
		n_chart_tabs = len(self.get_multiple_elements(_chart_tabs,expire=0.5))
		
		while n_chart_tabs > 1: 
			close_button = self.get_element([_chart_tabs,_close_btns,_close_btn],expire=0.1)
			if close_button:
				self.click_on(close_button) #may need a second click?
			
			#chart_tab = self.get_element(_chart_tabs,0.2)
			n_chart_tabs -= 1
			
		print('click settings in positions table')
		#ensure all columns exist 
		settings = self.get_element([_position_data_table,_settings]) #perhaps use a wrapper?
		self.click_on(settings)
		
		#now wait for  menu to appear, then wait a bit more for the animation to stop? or just use the base methods :)
		checkboxes = self.get_multiple_elements([_checkbox_bit,_sub_checkbox_bit])
		
		for checkbox in checkboxes:
			if ' selected' not in checkbox.get_attribute('class'):
				self.click_on(checkbox)  #enable the lot for easier querying
		
		print('click chart to close dropdowns')		#re-query to prevent stale elem exception and robustness
		chart_elem = self.get_element(_chart_elem)
		self.click_on(chart_elem) # closes all dropdowns 
	
	def __ensure_trades_view(self):
		_home = {'tag':'div','subclass':'home-icon'} 
		_resizable_data_table = {'tag':'div','subclass':'data-table-resizable'}
		_data_table_switcher = {'tag':'div','class':'data-table-switcher'}
		_data_table_switcher_item = {'tag':'div','subclass':'data-table-switcher-item'}
		
		self.click_on(self.get_element(_home))

		data_table = self.get_element(_resizable_data_table)
		bottom_buttons = self.get_multiple_elements([_data_table_switcher,_data_table_switcher_item])
		open_button = bottom_buttons[0] #always the first button. 
		
		if 'collapsed' in self.get_attribute(data_table,'class') or 'active' not in self.get_attribute(open_button,'class'):
			self.click_on(open_button)
		
	
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
		

		#top right hand corner login button to open modal 
		login_button = self.get_element(_login_button) 
		login_modal = self.get_element(_login_modal)
		
		accept_cookies = self.get_element(_cookies_modal_btn)
		if accept_cookies:
			self.click_on(accept_cookies)
		
		if not login_modal:
			self.click_on(login_button)
			login_modal = self.get_element(_login_modal)   
		
		login_email = self.get_element(_login_email) 
		login_pass = self.get_element(_login_pass)
		login_remember = self.get_element(_login_remember)
		
		#actual log in button 
		login_login = self.get_element(_login_login)
		
		self.type_keys_on(login_email,self.config.get('trading212','username'))
		self.type_keys_on(login_pass,self.config.get('trading212','password'))
		
		if login_remember.is_selected():
			self.click_on(login_remember) #dont remember for the bot
		
		self.click_on(login_login) #go! 
		
		
	def __ensure_demo(self):
	
		_dropdown_acc_menu = {'tag':'div','subclass':'dropdown-account-menu'}
		
		_acc_menu_header = {'tag':'div','class':'account-menu-header'}
		_acc_menu_reveal = {'tag':'div','subclass':'arrow'}
		_acc_menu_demo_btn = {'tag':'div','subclass':'switch-to-demo-button'}
		_acc_menu_live_btn = {'tag':'div','subclass':'switch-to-live-button'}
		
		loading_wait = 15 #slightly longer since t212 can be slow to load sometimes
		
		menu_dropdown_check = self.get_element(_dropdown_acc_menu,loading_wait)
		reveal  = self.get_element([_acc_menu_header, _acc_menu_reveal])
		if 'expanded' not in self.get_attribute(menu_dropdown_check,'class'):
			self.click_on(reveal)  
		
		if self.demo:
			self.click_on(self.get_element(_acc_menu_demo_btn))
		
		if not self.demo:
			self.click_on(self.get_element(_acc_menu_live_btn))
			
				
	#logging out of T212 
	def __finish(self):	
		
		_dropdown_acc_menu = {'tag':'div','subclass':'dropdown-account-menu'}
		
		_acc_menu_header = {'tag':'div','class':'account-menu-header'}
		_acc_menu_reveal = {'tag':'div','subclass':'arrow'}
		_acc_menu_logout = {'tag':'div','class':'action-button','data-qa-action-btn':'btn-logout'}
		
		
		_modal_confirm_btn = {'tag':'div','class':'logout-dialog'}
		_logout_container = {'tag':'div','class':'logout-dialog'} 
		_logout_buttons = {'tag':'div','class':'buttons'}
		_confirm_buttons = {'tag':'div','subclass':'confirm-button'}
		
		menu_dropdown_check = self.get_element(_dropdown_acc_menu)
		
		reveal  = self.get_element([_acc_menu_header,_acc_menu_reveal])
		if 'expanded' not in menu_dropdown_check.get_attribute('class'):
			self.click_on(reveal) 
		
		logout = self.get_element(_acc_menu_logout)
		if logout:
			self.click_on(logout)
			sure_logout = self.get_element([_logout_container,_logout_buttons,_confirm_buttons])
			self.click_on(sure_logout)
	
	def __open_report_modal(self):
		
		_acc_menu_header = {'tag':'div','class':'account-menu-header'}
		_dropdown_acc_menu = {'tag':'div','subclass':'dropdown-account-menu'}
		_acc_menu_reveal = {'tag':'div','subclass':'arrow'}
		_acc_menu_button = {'tag':'div','subclass':'account-menu-item'}
		_history_button = {'tag':'div','subclass':'history-icon'}
		
		loading_wait = 15 #if it takes ages to load
		
		
		header = self.get_element(_acc_menu_header,loading_wait) 
		reveal  = self.get_element([_acc_menu_header, _acc_menu_reveal])
		
		menu_dropdown_check = self.get_element(_dropdown_acc_menu)
		if 'expanded' not in menu_dropdown_check.get_attribute('class'):
			self.click_on(reveal) 
		
		self.click_on(self.get_element([_acc_menu_button,_history_button])) #open history modal
		
	
	def __get_all_old_positions(self, leave_open=False):
		
		#checking for the presence of the popup
		_popup_wrapper = {'tag':'div','subclass':'popup-wrapper'}
		_reports_modal = {'tag':'div','class':'reports'}
		
		#getting the right result table up 
		_reports_tabs = {'tag':'div','subclass':'tab-item'}
		_positions = {'tag':'div','subclass1':'content','subclass2':'positions'}
		_positions_rows = {'tag':'div','class':'highlight-container'}
		
		#data from each row
		_positions_close = {'tag':'div','subclass1':'data-item','subclass2':'dateClosed'}
		_positions_code = {'tag':'div','subclass1':'data-item','subclass2':'code'}
		_positions_positionHumanId = {'tag':'div','subclass1':'data-item','subclass2':'positionHumanId'}
		_positions_currency = {'tag':'div','subclass1':'data-item','subclass2':'currency'}
		_positions_open = {'tag':'div','subclass1':'data-item','subclass2':'dateCreated'}
		
		_close_report = {'tag':'div','subclass':'close-button'}
		
		popup_wrapper = self.get_element(_popup_wrapper)
		if not 'active-popup-reports-popup' in self.get_attribute(popup_wrapper,'class'):
			self.__open_report_modal()
		
		#wait for modal to be loaded. 
		self.get_element([_popup_wrapper,_reports_modal])
		
		reports_tabs = self.get_multiple_elements([_popup_wrapper,_reports_modal,_reports_tabs])
		for report_tab in reports_tabs:
			if 'positions' in self.get_text(report_tab).lower():
				self.click_on(report_tab) #click positions to get the position first
				break
		
		#wait for this to load 
		self.get_element([_popup_wrapper,_reports_modal,_positions])
		
		#then grab the lot..
		positions_rows_closes = self.get_multiple_elements([_popup_wrapper,_reports_modal,_positions,_positions_rows,_positions_close])
		positions_rows_codes = self.get_multiple_elements([_popup_wrapper,_reports_modal,_positions,_positions_rows,_positions_code])
		positions_rows_ids = self.get_multiple_elements([_popup_wrapper,_reports_modal,_positions,_positions_rows,_positions_positionHumanId])
		positions_rows_currency = self.get_multiple_elements([_popup_wrapper,_reports_modal,_positions,_positions_rows,_positions_currency])
		positions_rows_opens = self.get_multiple_elements([_popup_wrapper,_reports_modal,_positions,_positions_rows,_positions_open])
		
		position_pieces = [(\
			self.get_text(pclose),\
			self.get_text(pcode).upper(),\
			self.get_text(pid).upper(),\
			self.get_text(pcur).upper(),\
			self.get_text(popen)) for (pclose,pcode,pid,pcur,popen) in \
			zip(\
				positions_rows_closes,\
				positions_rows_codes,\
				positions_rows_ids,\
				positions_rows_currency,\
				positions_rows_opens\
		)]
		
		if not leave_open:
			self.click_on(self.get_element([_popup_wrapper,_reports_modal,_close_report]))
		
		
		
		positions = [self.Position(*pp) for pp in position_pieces]
		
		return positions
		
	def __get_all_old_results(self, leave_open=False):
		
		#checking for presence of the modal
		_popup_wrapper = {'tag':'div','subclass':'popup-wrapper'}
		_reports_modal = {'tag':'div','class':'reports'}
		
		#getting to right table and getting rows
		_reports_tabs = {'tag':'div','subclass':'tab-item'}
		_results = {'tag':'div','subclass1':'content','subclass2':'result'}
		_results_rows = {'tag':'div','class':'highlight-container'}
		
		#getting the data
		_results_close = {'tag':'div','subclass1':'data-item','subclass2':'time'}
		_results_code = {'tag':'div','subclass1':'data-item','subclass2':'code'}#
		_results_direction = {'tag':'div','subclass1':'data-item','subclass2':'item-direction'}
		_results_quantity = {'tag':'div','subclass1':'data-item','subclass2':'quantity'}
		_results_price = {'tag':'div','subclass1':'data-item','subclass2':'price'}
		_results_close_price = {'tag':'div','subclass1':'data-item','subclass2':'closePrice'}
		_results_result = {'tag':'div','subclass1':'data-item','subclass2':'result'}
		
		_close_report = {'tag':'div','subclass':'close-button'}
		
		popup_wrapper = self.get_element(_popup_wrapper)
		if not 'active-popup-reports-popup' in self.get_attribute(popup_wrapper,'class'):
			self.__open_report_modal()
		
		reports_tabs = self.get_multiple_elements([_popup_wrapper,_reports_modal,_reports_tabs])
		for report_tab in reports_tabs:
			if 'result' in self.get_text(report_tab).lower():
				self.click_on(report_tab) #click positions to get the position first
				break
		#wait for this to load 
		self.get_element([_popup_wrapper,_reports_modal,_results])
		
		results_close_date = self.get_multiple_elements([_popup_wrapper,_reports_modal,_results,_results_rows,_results_close])
		results_codes = self.get_multiple_elements([_popup_wrapper,_reports_modal,_results,_results_rows,_results_code])
		results_direction = self.get_multiple_elements([_popup_wrapper,_reports_modal,_results,_results_rows,_results_direction])
		results_quantity = self.get_multiple_elements([_popup_wrapper,_reports_modal,_results,_results_rows,_results_quantity])
		results_price = self.get_multiple_elements([_popup_wrapper,_reports_modal,_results,_results_rows,_results_price])
		results_close_price = self.get_multiple_elements([_popup_wrapper,_reports_modal,_results,_results_rows,_results_close_price])
		results_result = self.get_multiple_elements([_popup_wrapper,_reports_modal,_results,_results_rows,_results_result])
	
		result_pieces = [(\
			self.get_text(rclose),\
			self.get_text(rcode).upper(),\
			self.get_text(rdir).upper(),\
			self.safefloat(self.get_text(rqty)),\
			self.safefloat(self.get_text(rop)),\
			self.safefloat(self.get_text(rcp)),\
			self.safefloat(self.get_text(rres))\
			) for (rclose,rcode,rdir,rqty,rop,rcp,rres) in \
			zip(\
				results_close_date,\
				results_codes,\
				results_direction,\
				results_quantity,\
				results_price,\
				results_close_price,\
				results_result
		)]
		
		if not leave_open:
			self.click_on(self.get_element([_popup_wrapper,_reports_modal,_close_report]))
				
		buff = 0 
		results = [self.Result(*res) for res in result_pieces]
			
		return results
		
		
		
	
	
	
	
#hopefully any other brokers will have an API, so their handling class will be tiny 	
		
		
		
		
		
		
		
		
		
		
		
		
		
		
		
		
		
		
		
		
		
		
		
		
		
		
		
		
		
		
		
		
	
	
	
	
	










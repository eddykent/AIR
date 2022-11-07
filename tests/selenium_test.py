



import pdb
from web.crawler import SeleniumHandler


##if this does not work, try updating your version of chrome! 
##chrome may require re-install for auto-detection of the version 
sh = SeleniumHandler()
pdb.set_trace()
sh.start() #start up selenium 
sh.browser.get('http://www.google.com/')  #uses the raw selenium driver object 
print('success?')

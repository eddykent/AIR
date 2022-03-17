# Reading News Archives
For a good AI system, a bunch of news is required for test samples. This subdirectory is here to be able to read news
from archives so they can be cached in the database. This directory is not intended for production code but for a tool
that a fellow trader can use to be able to load their own news archives into a database table. For any news service 
that offers an archive, it should be noted here so a scraper/crawler can be made for it. Each script in this directory
should be stand alone. I repeat - STAND ALONE. The reason is because it is a tool, not something that is relevant to 
the rest of the project. 

Modules from the main project are allowed to be used, but they must conform to the standards of these scripts (which 
is pretty low compared to the rest of the project!). An archive test should be provided. It should be ran after
anything in fundamental is changed. 

We have to re-use modules, right?

## DailyFX
To read articles from dailyfx, dailyfx.py is used. This script will read everything directly to the database iterating
using the url. It is a crawler that uses selenium (and therefore uses web/crawler).


## FXStreet





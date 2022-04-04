-- public.exchange_value_tick definition

-- Drop table

-- DROP TABLE public.exchange_value_tick;

CREATE TABLE public.exchange_value_tick (
	id bigserial NOT NULL,
	from_currency text NOT NULL,
	to_currency text NOT NULL,
	full_name text NOT NULL,
	open_price float8 NOT NULL,
	high_price float8 NOT NULL,
	low_price float8 NOT NULL,
	close_price float8 NOT NULL,
	the_date timestamp NOT NULL,
	captured_date timestamp NULL DEFAULT now(),
	note text NULL
);

--table for historical sentiment and sentiment analysis data - don't store relevant keys etc as they all must be calculated
CREATE TABLE news_article (
	guid TEXT DEFAULT uuid_generate_v4() PRIMARY KEY, --unique identifier for the database
	hash_identifier TEXT NOT NULL, --don't forget this! prevents duplicate articles being stored in the database
	published_date TIMESTAMP, --always GMT, wherever you are in the world 
	source_ref TEXT, --for human readability, keep it small 
	title_head TEXT, --for human readability, kept at around 50 chars 
	compression BYTEA --never store the FULL info IN the DATABASE because we have limited room :(
);

--table for economic calendar information 
CREATE TABLE economic_calendar (
	guid TEXT DEFAULT uuid_generate_v4() PRIMARY KEY,
	the_date TIMESTAMP NOT NULL, 
	impact INT NOT NULL,
	country TEXT NOT NULL,
	description TEXT NOT NULL,
	actual TEXT NOT NULL,  --these values must persist as text because they can have any unit or be blank! 
	previous TEXT NOT NULL, 
	consensus TEXT NOT NULL, 
	forecast TEXT NOT NULL
);

--other sentiment tables? eg client_sentiment_info? 
CREATE TABLE exchange_volume_hourly (
	id BIGSERIAL PRIMARY KEY,
	from_currency TEXT,
	to_currency TEXT,
	full_name TEXT,
	bid_volume DOUBLE PRECISION,
	ask_volume DOUBLE PRECISION,
	the_date TIMESTAMP, 
	captured_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
	note TEXT
);

CREATE INDEX exchange_volume_hourly_from_currency_idx ON exchange_volume_hourly USING btree(from_currency);
CREATE INDEX exchange_volume_hourly_to_currency_idx ON exchange_volume_hourly USING btree(to_currency);
CREATE INDEX exchange_volume_hourly_full_name_idx ON exchange_volume_hourly USING btree(full_name);
CREATE INDEX exchange_volume_hourly_the_date_idx ON exchange_volume_hourly USING btree(the_date);
CREATE INDEX exchange_volume_hourly_the_date_full_name_idx ON exchange_volume_hourly USING btree(the_date,full_name);








--CREATE TABLE trade_journal ( ... )


-- public.exchange_value_tick definition

-- Drop table

-- DROP TABLE public.exchange_value_tick; 
-- TODO: Add index creation

--DROP TABLE IF EXISTS debug_log;
CREATE TABLE debug_log (
	id BIGSERIAL PRIMARY KEY, --  DEFAULT uuid_generate_v4() PRIMARY KEY,  --id is sequential so we can always determine the log order
	created TIMESTAMP NOT NULL, --convert float to timestamp 
	log TEXT,--name
	--login TEXT, --from path? 
	level TEXT,--levelname
	file TEXT, 
	line INT,
	module TEXT, 
	process TEXT, --processName
	thread TEXT, --threadName
	funct TEXT,--funcName
	message TEXT,--msg
	exc_info TEXT,
	exc_text TEXT, 
	stack_info TEXT
);




--CREATE TABLE exchange_value_tick (
--	id bigserial NOT NULL,
--	from_currency text NOT NULL,
--	to_currency text NOT NULL,
--	full_name text NOT NULL,
--	open_price float8 NOT NULL,
--	high_price float8 NOT NULL,
--	low_price float8 NOT NULL,
--	close_price float8 NOT NULL,
--	the_date timestamp NOT NULL,
--	captured_date timestamp NULL DEFAULT now(),
--	note text NULL
--);
--
--indexs?


CREATE TABLE public.news_article (
	--useful fields 
	link TEXT NULL,
	title TEXT NULL,
	summary TEXT NULL,
	published_date timestamp NULL,
	author TEXT NULL,
	source_ref text NULL,
	full_text TEXT NULL,
	instruments TEXT[] NULL,
	--utility fields 
	captured_date TIMESTAMP NULL DEFAULT (NOW() AT TIME ZONE 'utc'),
	guid TEXT NOT NULL DEFAULT uuid_generate_v4(),
	last_update TIMESTAMP NULL DEFAULT (NOW() AT TIME ZONE 'utc'),
	CONSTRAINT news_article_pkey PRIMARY KEY (guid)
);

CREATE INDEX news_article_link_idx ON news_article USING btree(link);
CREATE INDEX news_article_source_ref_idx ON news_article USING btree(source_ref);
CREATE INDEX news_article_instruments_idx ON news_article USING btree(instruments);
CREATE INDEX news_article_captured_date_idx ON news_article USING btree(captured_date);

--trigger for updates
CREATE  FUNCTION update_news_article_trf()
RETURNS TRIGGER AS $$
BEGIN
    NEW.last_update = now();
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_news_article_tr
	BEFORE UPDATE 
	ON 
		news_article
	FOR EACH ROW
EXECUTE PROCEDURE update_news_article_trf();

--table for economic calendar information 
CREATE TABLE economic_calendar (
	the_date TIMESTAMP NOT NULL, 
	source_ref TEXT NOT NULL,
	impact INT NOT NULL,
	country TEXT NOT NULL,
	currency TEXT NOT NULL,
	description TEXT,
	actual TEXT, 
	previous TEXT, 
	consensus TEXT, 
	forecast TEXT,
	captured_date TIMESTAMP NULL DEFAULT (NOW() AT TIME ZONE 'utc'),
	guid TEXT NOT NULL DEFAULT uuid_generate_v4(),
	last_update TIMESTAMP NULL DEFAULT (NOW() AT TIME ZONE 'utc'),
	CONSTRAINT economic_calendar_pkey PRIMARY KEY (guid)
);


--trigger for updates
CREATE  FUNCTION update_economic_calendar_trf()
RETURNS TRIGGER AS $$
BEGIN
    NEW.last_update = now();
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_economic_calendar_tr
	BEFORE UPDATE 
	ON 
		economic_calendar
	FOR EACH ROW
EXECUTE PROCEDURE update_economic_calendar_trf();

--other sentiment tables? eg client_sentiment_info? 
--CREATE TABLE exchange_volume_hourly (
--	id BIGSERIAL PRIMARY KEY,
--	from_currency TEXT,
--	to_currency TEXT,
--	full_name TEXT,
--	bid_volume DOUBLE PRECISION,
--	ask_volume DOUBLE PRECISION,
--	the_date TIMESTAMP, 
--	captured_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
--	note TEXT
--);

--CREATE INDEX exchange_volume_hourly_from_currency_idx ON exchange_volume_hourly USING btree(from_currency);
--CREATE INDEX exchange_volume_hourly_to_currency_idx ON exchange_volume_hourly USING btree(to_currency);
--CREATE INDEX exchange_volume_hourly_full_name_idx ON exchange_volume_hourly USING btree(full_name);
--CREATE INDEX exchange_volume_hourly_the_date_idx ON exchange_volume_hourly USING btree(the_date);
--CREATE INDEX exchange_volume_hourly_the_date_full_name_idx ON exchange_volume_hourly USING btree(the_date,full_name);
--
--CREATE TABLE exchange_volume_tick (
--	id BIGSERIAL PRIMARY KEY,
--	from_currency TEXT,
--	to_currency TEXT,
--	full_name TEXT,
--	bid_volume DOUBLE PRECISION,
--	ask_volume DOUBLE PRECISION,
--	the_date TIMESTAMP, 
--	captured_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
--	note TEXT
--);
--
--CREATE INDEX exchange_volume_tick_from_currency_idx ON exchange_volume_hourly USING btree(from_currency);
--CREATE INDEX exchange_volume_tick_to_currency_idx ON exchange_volume_hourly USING btree(to_currency);
--CREATE INDEX exchange_volume_tick_full_name_idx ON exchange_volume_hourly USING btree(full_name);
--CREATE INDEX exchange_volume_tick_the_date_idx ON exchange_volume_hourly USING btree(the_date);
--CREATE INDEX exchange_volume_tick_the_date_full_name_idx ON exchange_volume_hourly USING btree(the_date,full_name);



CREATE TABLE IF NOT EXISTS raw_fx_candles_15m( --data that will come from dukascopy  
	id BIGSERIAL,
	from_currency TEXT, 
	to_currency TEXT, 
	full_name TEXT, 
	the_date TIMESTAMP,
	captured_date TIMESTAMP DEFAULT NOW(),
	bid_open DOUBLE PRECISION, 
	bid_high DOUBLE PRECISION, 
	bid_low DOUBLE PRECISION, 
	bid_close DOUBLE PRECISION, 
	bid_volume DOUBLE PRECISION, 
	ask_open DOUBLE PRECISION,
	ask_high DOUBLE PRECISION, 
	ask_low DOUBLE PRECISION, 
	ask_close DOUBLE PRECISION, 
	ask_volume DOUBLE PRECISION,
	note TEXT
);

CREATE INDEX IF NOT EXISTS raw_fx_candles_15m_from_currency_from_currency_idx ON raw_fx_candles_15m USING btree(from_currency);
CREATE INDEX IF NOT EXISTS raw_fx_candles_15m_from_currency_to_currency_idx ON raw_fx_candles_15m USING btree(to_currency);
CREATE INDEX IF NOT EXISTS raw_fx_candles_15m_from_currency_full_name_idx ON raw_fx_candles_15m USING btree(full_name);
CREATE INDEX IF NOT EXISTS raw_fx_candles_15m_from_currency_the_date_idx ON raw_fx_candles_15m USING btree(the_date);
CREATE INDEX IF NOT EXISTS raw_fx_candles_15m_from_currency_full_name_the_date_idx ON raw_fx_candles_15m USING btree(full_name,the_date);


CREATE TABLE market_snapshot_dump ( --just hold json dumps of any website data about anything in the market 
	snapshot JSONB NOT NULL,
	captured_date TIMESTAMP NULL DEFAULT (NOW() AT TIME ZONE 'utc'),
	guid TEXT NOT NULL DEFAULT uuid_generate_v4(),
	CONSTRAINT market_snapshot_dump_pkey PRIMARY KEY (guid)
);
--CREATE TABLE trade_journal ( ... )






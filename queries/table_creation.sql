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

--table for historical sentiment and sentiment analysis data?
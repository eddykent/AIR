

---find holes in raw_fx_candles_15m 
WITH settings AS (
	SELECT 
		'01 Nov 2021 T12:11'::TIMESTAMP AS start_date,
		'10 Nov 2022 T12:00'::TIMESTAMP AS end_date, 
		ARRAY['AUD/NZD','CAD/JPY','CAD/CHF'] AS instruments 
),
round_dates AS (
	SELECT TO_TIMESTAMP (FLOOR(( EXTRACT ('EPOCH' FROM (s.start_date )) ) / (60*15) ) * (60*15)) AT TIME ZONE 'UTC' AS start_date, --fix date
	TO_TIMESTAMP (FLOOR(( EXTRACT ('EPOCH' FROM (s.end_date )) ) / (60*15) ) * (60*15)) AT TIME ZONE 'UTC' AS end_date,
	instruments
	FROM settings s
),
--SELECT * FROM round_dates 
--,
timeline_dates AS (
	SELECT generate_series('01 Nov 2021'::TIMESTAMP,'10 Nov 2023'::TIMESTAMP,'15 min'::INTERVAL) AS the_date 
	FROM round_dates rd 
),
all_instruments AS (
	SELECT UNNEST(instruments) as instrument FROM settings
),
all_fields AS (
	SELECT the_date, instrument
	FROM timeline_dates, all_instruments 
),
filtered_trading_hours AS (
	WITH all_dates_dow AS (
		SELECT the_date, 
		EXTRACT(ISODOW FROM the_date) AS weekday,--1 = mon, 7 = sun (check)
		EXTRACT(HOUR FROM the_date) AS hour,
		EXTRACT(MINUTE FROM the_date) AS minute
		FROM timeline_dates
	)
	SELECT ad.the_date AS non_fx_trading_day
	--, ad.weekday, ad.hour, ad.minute,
	--
	--here is the tricky constraints! 
	--CASE 
	--	WHEN ad.weekday = 6 THEN FALSE 
	--	WHEN ad.weekday = 7 AND ad.hour < 22 THEN FALSE 
	--	WHEN ad.weekday = 5 AND ad.hour > 21 THEN FALSE 
	--	ELSE TRUE
	--END AS trading_day
	FROM all_dates_dow ad --, all_instruments ai
	WHERE (ad.weekday = 6 OR  --saturday
	ad.weekday = 7 AND ad.hour < 22 OR --sunday before 10pm
	ad.weekday = 5 AND ad.hour > 21 ) --friday after 10pm 
),
filtered_bank_holidays AS (
	SELECT NOW() AS bank_hol LIMIT 0
),
general_filters AS (
	SELECT 
	fth.non_fx_trading_day AS excempt
	FROM filtered_trading_hours fth 
	UNION 
	SELECT 
	bank_hol AS excempt
	FROM filtered_bank_holidays fbh 
),
specific_filters AS ( --remove anything that is specific to any instrument (eg maybe there is a missing value for CAD/JPY on the queens birthday)
	SELECT 'blah' AS instrument, 
	NOW() AS the_date
)
SELECT af.* FROM all_fields af
LEFT JOIN raw_fx_candles_15m rfc ON rfc.the_date = af.the_date 
LEFT JOIN specific_filters sf ON sf.the_date = rfc.the_date AND sf.instrument = rfc.full_name 
WHERE af.the_date NOT IN (SELECT excempt FROM general_filters)
AND sf IS NULL --filter specific stuff 
AND (
	rfc.bid_open IS NULL 
	OR 
	rfc.ask_open IS NULL
	OR 
	rfc.bid_volume IS NULL 
	OR 
	rfc.ask_volume IS NULL
) 



SELECT dd
FROM generate_series
        ( '2007-02-01'::timestamp 
        , '2008-04-01'::timestamp
        , '1 minutes'::interval) dd




SELECT * FROM raw_fx_candles_15m rfcm WHERE full_name  = 'AUD/NZD' AND the_date >= '04 Nov 2022 20:00' AND the_date <= '04 Nov 2022 22:00'



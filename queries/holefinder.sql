---find holes in raw_fx_candles_15m 
WITH settings AS (
	SELECT 
		%(start_date)s::TIMESTAMP AS start_date,
		%(end_date)s::TIMESTAMP AS end_date, 
		%(instruments)s AS instruments 
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
	SELECT generate_series(rd.start_date,rd.end_date,'15 min'::INTERVAL) AS the_date 
	FROM round_dates rd 
),
all_instruments AS (
	SELECT UNNEST(instruments) as instrument FROM settings
),
all_fields AS (
	SELECT the_date, instrument
	FROM timeline_dates, all_instruments 
),
bank_holidays AS (
	SELECT %(bank_holidays)s AS bank_hol 
),
non_working_datetimes AS (
	WITH all_dates_dow AS (
		SELECT the_date, the_date::DATE AS as_date, 
		EXTRACT(ISODOW FROM the_date) AS weekday,--1 = mon, 7 = sun (check)
		EXTRACT(HOUR FROM the_date) AS hour,
		EXTRACT(MINUTE FROM the_date) AS minute
		FROM timeline_dates
	)
	SELECT ad.the_date AS excempt
	--, ad.weekday, ad.hour, ad.minute,
	--
	--here is the tricky constraints! 
	--CASE 
	--	WHEN ad.weekday = 6 THEN FALSE 
	--	WHEN ad.weekday = 7 AND ad.hour < 22 THEN FALSE 
	--	WHEN ad.weekday = 5 AND ad.hour > 21 THEN FALSE 
	--	ELSE TRUE
	--END AS trading_day
	FROM all_dates_dow ad, bank_holidays bh --, all_instruments ai
	WHERE (ad.weekday = 6 OR  --saturday
	ad.weekday = 7 AND ad.hour < 22 OR --sunday before 10pm
	ad.weekday = 5 AND ad.hour > 21 ) --friday after 10pm 
	OR ad.as_date = ANY(bh.bank_hol)
),
specific_filters AS ( --remove anything that is specific to any instrument (eg maybe there is a missing value for CAD/JPY on the queens birthday)
	SELECT 'blah' AS instrument,  --TODO
	NOW() AS the_date
)
SELECT af.instrument, af.the_date FROM all_fields af
LEFT JOIN %(table_name)s %(table_alias)s ON rfc.the_date = af.the_date 
LEFT JOIN specific_filters sf ON sf.the_date = rfc.the_date AND sf.instrument = rfc.full_name 
WHERE af.the_date NOT IN (SELECT excempt FROM non_working_datetimes)
AND sf IS NULL --filter specific stuff 
AND ((
	%(column_null_checks)s
) OR (
	%(check_volumes)s::BOOLEAN AND rfc.the_date < CURRENT_DATE AND (rfc.bid_volume < 0.01 OR rfc.ask_volume < 0.01)
));

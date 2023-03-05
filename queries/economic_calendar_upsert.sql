

WITH new_rows AS (
	SELECT * FROM (VALUES 
		%(calendar_events)s
	) AS rows(the_date,source_ref,impact,country,currency,description,actual,previous,consensus,forecast)
),
update_old AS ( --update to persist the guid in the database
	UPDATE economic_calendar AS ec
	SET 
	impact = nr.impact,
	currency = nr.currency,
	actual = nr.actual,
	previous = nr.previous,
	consensus = nr.consensus,	
	forecast = nr.forecast
	FROM new_rows nr
	WHERE 
		ec.source_ref = nr.source_ref AND 
		ec.the_date = nr.the_date AND 
		ec.country = nr.country AND 
		ec.description = nr.description
	RETURNING ec.source_ref, ec.the_date, ec.country, ec.description
)
INSERT INTO economic_calendar(the_date,source_ref,impact,country,currency,description,actual,previous,consensus,forecast)
SELECT the_date,source_ref,impact,country,currency,description,actual,previous,consensus,forecast 
FROM new_rows nr
WHERE NOT EXISTS (
	SELECT 1 FROM update_old uo
	WHERE nr.source_ref = uo.source_ref AND
	nr.the_date = uo.the_date AND
	nr.country = uo.country AND
	nr.description = uo.description
)






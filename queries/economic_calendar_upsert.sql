

WITH new_rows AS (
	SELECT * FROM (VALUES 
		%(calendar_events)s
	) AS rows(the_date,impact,country,description,actual,previous,consensus,forecast)
),
delete_old AS (
	DELETE FROM economic_calendar ec USING new_rows nr
	WHERE ec.the_date = nr.the_date AND ec.country = nr.country AND ec.description = nr.description
)
INSERT INTO economic_calendar(the_date,impact,country,description,actual,previous,consensus,forecast)
SELECT the_date,impact,country,description,actual,previous,consensus,forecast 
FROM new_rows 
RETURNING the_date,country,description
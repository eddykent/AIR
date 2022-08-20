WITH these_events AS (
	SELECT ROW_NUMBER() OVER () AS id, * FROM (
		VALUES %(events)s
	) AS tt(countries,the_time)
)
SELECT te.id, SUM(CASE WHEN ec.guid IS NULL THEN 0 ELSE 1 END) AS n_events, ARRAY_REMOVE(ARRAY_AGG(ec.guid),NULL) AS event_guids FROM these_events te 
LEFT JOIN economic_calendar ec 
ON ec.country = ANY(te.countries) AND (
	te.the_time >= ec.the_date - INTERVAL '%(before)s mins'
	AND 
	te.the_time <= ec.the_date + INTERVAL '%(after)s mins'
)
AND impact >= 3
GROUP BY te.id
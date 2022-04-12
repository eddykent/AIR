--query to get the fucntion register from the database. 
WITH user_defined_functions AS (
	SELECT routines.routine_name, parameters.ordinal_position, parameters.parameter_mode, parameters.data_type, parameters.parameter_name, parameters.parameter_default--, parameters.*
	FROM information_schema.routines
	LEFT JOIN information_schema.parameters ON routines.specific_name=parameters.specific_name
	WHERE routines.specific_schema='trading'
	ORDER BY routines.routine_name, parameters.ordinal_position
),
function_names AS (
	SELECT DISTINCT udf.routine_name,
	CASE WHEN udf.routine_name LIKE 'candles_%' THEN 
			SUBSTRING(udf.routine_name,9)
		WHEN udf.routine_name LIKE 'values_%' THEN 
			SUBSTRING(udf.routine_name,8)
		ELSE udf.routine_name
	END AS function_name FROM user_defined_functions udf
),
in_params AS (
	SELECT udf.routine_name, 
	jsonb_agg(
		jsonb_build_object(
			'name',CASE WHEN udf.parameter_name LIKE '_%' THEN SUBSTRING(udf.parameter_name,2) ELSE udf.parameter_name END, --remove annoying _ 
			'type',upper(udf.data_type)
		) 	|| 
		CASE WHEN udf.parameter_default IS NULL THEN 
			jsonb_build_object()
		ELSE 
			jsonb_build_object('default',udf.parameter_default)
		END
		ORDER BY ordinal_position ASC
	) AS ins
	FROM user_defined_functions udf 
	WHERE udf.parameter_mode = 'IN'
	AND (udf.routine_name LIKE 'values_%' OR udf.routine_name LIKE 'candles_%' OR udf.routine_name LIKE 'get_candles_%' OR udf.routine_name LIKE 'get_values_%')
	GROUP BY udf.routine_name 
),
out_params AS (
	SELECT udf.routine_name, 
	jsonb_agg(
		jsonb_build_object(
			'name',udf.parameter_name,
			'type',upper(udf.data_type)
		) 	|| 
		CASE WHEN udf.parameter_default IS NULL THEN 
			jsonb_build_object()
		ELSE 
			jsonb_build_object('default',udf.parameter_default)
		END
		ORDER BY ordinal_position ASC
	) AS outs
	FROM user_defined_functions udf 
	WHERE udf.parameter_mode = 'OUT'
	AND (udf.routine_name LIKE 'values_%' OR udf.routine_name LIKE 'candles_%' OR udf.routine_name LIKE 'get_candles_%' OR udf.routine_name LIKE 'get_values_%')
	GROUP BY udf.routine_name 
)
SELECT json_object_agg(
	fn.function_name,
	json_build_object(
		'routine_name',fn.routine_name,
		'parameters',COALESCE(ins.ins,'[]'),
		'returns',COALESCE(outs.outs,'[]')
	) 
)
FROM function_names fn 
LEFT JOIN in_params ins ON fn.routine_name = ins.routine_name
LEFT JOIN out_params outs ON fn.routine_name = outs.routine_name

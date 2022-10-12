

DROP TABLE IF EXISTS backtest_parameters;
CREATE TEMPORARY TABLE backtest_parameters 
AS SELECT 
%(profit_lock_activation)s::FLOAT8 AS profit_lock_activation, 
%(profit_lock_adjustment)s::FLOAT8 AS profit_lock_adjustment, 
%(profit_lock_extra)s::FLOAT8 AS profit_lock_extra
;


--DROP TABLE IF EXISTS backtest_parameters;
--CREATE TEMPORARY TABLE backtest_parameters 
--AS SELECT 
--0 AS profit_lock_activation, 
--0 AS profit_lock_adjustment, 
--0 AS profit_lock_extra
--;


DROP TABLE IF EXISTS trade_signals; 
CREATE TEMPORARY TABLE trade_signals 
AS SELECT * FROM (VALUES 
	%(trade_signals)s
) AS ts(signal_id, strategy_ref, the_date, instrument, direction, entry_price, entry_cutoff, entry_expiry, take_profit_difference, stop_loss_difference, duration);


DROP TABLE IF EXISTS exit_signals;
CREATE TEMPORARY TABLE exit_signals 
AS SELECT * FROM (VALUES  
	 %(exit_signals)s
) AS te(signal_id, strategy_ref, the_date, instrument, direction);

DROP TABLE IF EXISTS candle_selection;
CREATE TEMPORARY TABLE candle_selection 
AS SELECT * FROM (
	WITH trades AS (
		SELECT 
		ts.signal_id,
		ts.the_date AS start_date, 
		ts.the_date +(ts.duration || ' minutes')::INTERVAL AS end_date,
		ts.the_date +(ts.entry_expiry || ' minutes')::INTERVAL AS expire_date,
		ts.instrument
		FROM trade_signals ts
	)
	--sort weekend here
	SELECT 
	signal_id,
	instrument,
	start_date,
	end_date,
	tsrange(start_date,end_date,'[)') AS the_range,
	expire_date
FROM trades 
) ts; 

CREATE INDEX IF NOT EXISTS candle_selection_the_range_idx ON candle_selection USING gist(the_range);
CREATE INDEX IF NOT EXISTS candle_selection_instrument_idx ON candle_selection USING btree(instrument);

DROP TABLE IF EXISTS trade_reels; 
CREATE TEMPORARY TABLE trade_reels 
AS SELECT * FROM (
	WITH date_range AS (
		SELECT 
		min(the_date) as start_date,
		max(the_date) + (max(duration) || ' minutes')::INTERVAL AS end_date,
		tsrange(min(the_date),max(the_date) + (max(duration) || ' minutes')::INTERVAL) AS d FROM trade_signals 
	),
	exchange_value_tick_sub AS (
		SELECT evt.*  
		FROM exchange_value_tick evt, date_range dr
		WHERE dr.d @> evt.the_date 
		AND evt.the_date >= dr.start_date 
		AND evt.the_date < dr.end_date
	)
	SELECT 
	cs.signal_id, 
	LAG(evt.close_price) OVER (PARTITION BY cs.signal_id ORDER BY evt.the_date ASC) AS prev_close,  --slows it down a BIT? 
	evt.open_price,
	evt.high_price,
	evt.low_price,
	evt.close_price,
	evt.the_date,
	ROW_NUMBER() OVER (PARTITION BY cs.signal_id ORDER BY evt.the_date ASC) AS candle_number,
	evt.the_date < cs.expire_date AS not_expired--,
	--tsrange(evt.the_date,LEAD(evt.the_date) OVER (PARTITION BY cs.signal_id ORDER BY evt.the_date ASC)) AS candle_trange 
	FROM candle_selection cs 
	JOIN exchange_value_tick_sub evt ON evt.full_name = cs.instrument 
	WHERE cs.the_range @> evt.the_date
	AND evt.the_date >= cs.start_date 
	AND evt.the_date < cs.end_date
) ranged_select;


--determine all events - then we can build timelines for each trade. Should be easier from there onwards 
--ENTRY PRICES - These come either from the data or from the signals if there is one defined
DROP TABLE IF EXISTS trade_entry_cross;
CREATE TEMPORARY TABLE trade_entry_cross AS 
SELECT ts.signal_id,
1 AS candle_number,
(tr.high_price + tr.low_price + tr.close_price) / 3.0 AS entry_price,--typical price 
'instant' AS status
FROM trade_signals ts
JOIN trade_reels tr ON ts.signal_id = tr.signal_id 
WHERE tr.candle_number = 1
AND ts.entry_price IS NULL  --enter straight away if the entry price was NULL 
UNION
SELECT ts.signal_id,
tr.candle_number,
ts.entry_price::DOUBLE PRECISION,
'between' AS status
FROM trade_signals ts  --enter at the entry price if it has been crossed by the candles 
JOIN trade_reels tr ON ts.signal_id = tr.signal_id 
WHERE ts.entry_price::DOUBLE PRECISION > tr.low_price 
AND ts.entry_price::DOUBLE PRECISION < tr.high_price
AND ts.entry_price IS NOT NULL;

--catch any sudden moves 
INSERT INTO trade_entry_cross
SELECT tr.signal_id,
tr.candle_number,
tr.open_price AS entry_price, --we have open as entry since price has skipped from close to open 
'pco skip' AS status
FROM trade_signals ts
JOIN trade_reels tr ON ts.signal_id = tr.signal_id 
WHERE ts.entry_price IS NOT NULL AND (
	ts.entry_price::DOUBLE PRECISION > tr.prev_close  
	AND ts.entry_price::DOUBLE PRECISION <= tr.open_price
) OR (
	ts.entry_price::DOUBLE PRECISION < tr.prev_close 
	AND ts.entry_price::DOUBLE PRECISION >= tr.open_price
)
AND NOT EXISTS (SELECT 1 FROM trade_entry_cross tsc WHERE tsc.signal_id = tr.signal_id);

DROP TABLE IF EXISTS trade_starts; 
WITH earliest_entries AS (
	SELECT DISTINCT ON (signal_id) signal_id, candle_number, entry_price, status
	FROM trade_entry_cross ORDER BY signal_id, candle_number ASC --anything NOT IN here IS 
)
SELECT ee.signal_id, ee.candle_number, ee.entry_price, ee.status 
INTO TEMPORARY TABLE trade_starts
FROM earliest_entries ee 
JOIN trade_reels tr ON tr.signal_id = ee.signal_id AND tr.candle_number = ee.candle_number
WHERE tr.not_expired; --NOTE: whatever isnt in trade_start is stagnant 

--DETERMINE ALL TRADE TARGET PRICES 
DROP TABLE IF EXISTS trade_targets; 
SELECT st.signal_id,
st.candle_number AS start_candle_number,
ts.direction,
st.entry_price,
CASE 
	WHEN ts.direction = 'BUY' THEN st.entry_price + ts.take_profit_difference 
	WHEN ts.direction = 'SELL' THEN st.entry_price - ts.take_profit_difference 
	ELSE NULL 
END AS take_profit_price,
CASE 
	WHEN ts.direction = 'BUY' AND NULLIF(params.profit_lock_activation,0) IS NOT NULL THEN st.entry_price + (ts.take_profit_difference * params.profit_lock_activation)
	WHEN ts.direction = 'SELL' AND NULLIF(params.profit_lock_activation,0) IS NOT NULL THEN st.entry_price - (ts.take_profit_difference * params.profit_lock_activation)
	ELSE NULL 
END AS profit_lock_activation_price,
CASE  --new profit lock stop loss 
	WHEN ts.direction = 'BUY' AND NULLIF(params.profit_lock_adjustment,0) IS NOT NULL THEN st.entry_price + (ts.take_profit_difference * params.profit_lock_adjustment)
	WHEN ts.direction = 'SELL' AND NULLIF(params.profit_lock_adjustment,0) IS NOT NULL THEN st.entry_price - (ts.take_profit_difference * params.profit_lock_adjustment)
	ELSE NULL 
END AS profit_lock_adjustment_price,
CASE  --new profit lock take profit 
	WHEN ts.direction = 'BUY' AND NULLIF(params.profit_lock_activation,0) IS NOT NULL THEN st.entry_price + (ts.take_profit_difference * (1.0 + COALESCE(params.profit_lock_extra,0.0)))
	WHEN ts.direction = 'SELL' AND NULLIF(params.profit_lock_activation,0) IS NOT NULL THEN st.entry_price - (ts.take_profit_difference * (1.0 + COALESCE(params.profit_lock_extra,0.0)))
	ELSE NULL 
END AS profit_lock_extra_price,
CASE 
	WHEN ts.direction = 'BUY' THEN st.entry_price - ts.stop_loss_difference 
	WHEN ts.direction = 'SELL' THEN st.entry_price + ts.stop_loss_difference 
	ELSE NULL 
END AS stop_loss_price
INTO TEMPORARY TABLE trade_targets
FROM backtest_parameters params, trade_starts st
JOIN trade_signals ts ON st.signal_id = ts.signal_id;

--=======NOW BUILD EVENT TABLE - for everything that can happen lets record it and the candle number in an event table along with the signal ID 
--CUTOFF EVENTS 
DROP TABLE IF EXISTS trade_cutoff_cross;
CREATE TEMPORARY TABLE trade_cutoff_cross AS 
SELECT ts.signal_id,
tr.candle_number,
'low->price->high' AS status
FROM trade_signals ts  --enter at the entry price if it has been crossed by the candles 
JOIN trade_reels tr ON ts.signal_id = tr.signal_id 
WHERE ts.entry_cutoff::DOUBLE PRECISION > tr.low_price 
AND ts.entry_cutoff::DOUBLE PRECISION < tr.high_price
AND ts.entry_cutoff IS NOT NULL;

INSERT INTO trade_cutoff_cross
SELECT tr.signal_id,
tr.candle_number,
'close->price->open' AS status
FROM trade_signals ts
JOIN trade_reels tr ON ts.signal_id = tr.signal_id 
WHERE ts.entry_cutoff IS NOT NULL AND (
	ts.entry_cutoff::DOUBLE PRECISION > tr.prev_close  --is this wrong? - need to make the case for BUY and SELL separately? 
	AND ts.entry_cutoff::DOUBLE PRECISION < tr.open_price
) OR (
	ts.entry_cutoff::DOUBLE PRECISION < tr.prev_close 
	AND ts.entry_cutoff::DOUBLE PRECISION > tr.open_price
);

--TP 
DROP TABLE IF EXISTS trade_take_profit_cross;
CREATE TEMPORARY TABLE trade_take_profit_cross AS 
SELECT ts.signal_id,
tr.candle_number,
'low->price->high' AS status
FROM trade_signals ts  --enter at the entry price if it has been crossed by the candles 
JOIN trade_reels tr ON ts.signal_id = tr.signal_id
JOIN trade_targets tt ON ts.signal_id = tt.signal_id
WHERE tt.take_profit_price > tr.low_price 
AND tt.take_profit_price < tr.high_price;

INSERT INTO trade_take_profit_cross
SELECT tr.signal_id,
tr.candle_number,
'close->price->open' AS status
FROM trade_signals ts
JOIN trade_reels tr ON ts.signal_id = tr.signal_id 
JOIN trade_targets tt ON ts.signal_id = tt.signal_id
WHERE tt.take_profit_price IS NOT NULL AND (
	tt.take_profit_price > tr.prev_close  
	AND tt.take_profit_price < tr.open_price
) OR (
	tt.take_profit_price < tr.prev_close 
	AND tt.take_profit_price > tr.open_price
);

--PROFIT LOCK (- if this is hit, the TP and SL values are adjusted)
DROP TABLE IF EXISTS trade_profit_lock_cross;
CREATE TEMPORARY TABLE trade_profit_lock_cross AS 
SELECT ts.signal_id,
tr.candle_number,
'low->price->high' AS status
FROM trade_signals ts  --enter at the entry price if it has been crossed by the candles 
JOIN trade_reels tr ON ts.signal_id = tr.signal_id
JOIN trade_targets tt ON ts.signal_id = tt.signal_id
WHERE tt.profit_lock_activation_price > tr.low_price 
AND tt.profit_lock_activation_price < tr.high_price;

INSERT INTO trade_profit_lock_cross
SELECT tr.signal_id,
tr.candle_number,
'close->price->open' AS status
FROM trade_signals ts
JOIN trade_reels tr ON ts.signal_id = tr.signal_id 
JOIN trade_targets tt ON ts.signal_id = tt.signal_id
WHERE tt.profit_lock_activation_price IS NOT NULL AND (
	tt.profit_lock_activation_price > tr.prev_close  
	AND tt.profit_lock_activation_price < tr.open_price
) OR (
	tt.profit_lock_activation_price < tr.prev_close 
	AND tt.profit_lock_activation_price > tr.open_price
);

--PROFIT LOCKED (- hit the stop loss that has been adjusted)
DROP TABLE IF EXISTS trade_profit_adjust_cross;
CREATE TEMPORARY TABLE trade_profit_adjust_cross AS 
SELECT ts.signal_id,
tr.candle_number,
'low->price->high' AS status
FROM trade_signals ts  --enter at the entry price if it has been crossed by the candles 
JOIN trade_reels tr ON ts.signal_id = tr.signal_id
JOIN trade_targets tt ON ts.signal_id = tt.signal_id
WHERE tt.profit_lock_adjustment_price > tr.low_price 
AND tt.profit_lock_adjustment_price < tr.high_price;

INSERT INTO trade_profit_adjust_cross
SELECT tr.signal_id,
tr.candle_number,
'close->price->open' AS status
FROM trade_signals ts
JOIN trade_reels tr ON ts.signal_id = tr.signal_id 
JOIN trade_targets tt ON ts.signal_id = tt.signal_id
WHERE tt.profit_lock_adjustment_price IS NOT NULL AND (
	tt.profit_lock_adjustment_price > tr.prev_close  
	AND tt.profit_lock_adjustment_price < tr.open_price
) OR (
	tt.profit_lock_adjustment_price < tr.prev_close 
	AND tt.profit_lock_adjustment_price > tr.open_price
);

--EXTRA PROFIT (- hit the adjusted take profit, resulting in more profit)
DROP TABLE IF EXISTS trade_profit_extra_cross;
CREATE TEMPORARY TABLE trade_profit_extra_cross AS 
SELECT ts.signal_id,
tr.candle_number,
'low->price->high' AS status
FROM trade_signals ts  --enter at the entry price if it has been crossed by the candles 
JOIN trade_reels tr ON ts.signal_id = tr.signal_id
JOIN trade_targets tt ON ts.signal_id = tt.signal_id
WHERE tt.profit_lock_extra_price > tr.low_price 
AND tt.profit_lock_extra_price < tr.high_price;

INSERT INTO trade_profit_extra_cross
SELECT tr.signal_id,
tr.candle_number,
'close->price->open' AS status
FROM trade_signals ts
JOIN trade_reels tr ON ts.signal_id = tr.signal_id 
JOIN trade_targets tt ON ts.signal_id = tt.signal_id
WHERE tt.profit_lock_extra_price IS NOT NULL AND (
	tt.profit_lock_extra_price > tr.prev_close  
	AND tt.profit_lock_extra_price < tr.open_price
) OR (
	tt.profit_lock_extra_price < tr.prev_close 
	AND tt.profit_lock_extra_price > tr.open_price
);

--STOP LOSS (- hit the stop loss value and exited the trade)
DROP TABLE IF EXISTS trade_stop_loss_cross;
CREATE TEMPORARY TABLE trade_stop_loss_cross AS 
SELECT ts.signal_id,
tr.candle_number,
'low->price->high' AS status
FROM trade_signals ts  --enter at the entry price if it has been crossed by the candles 
JOIN trade_reels tr ON ts.signal_id = tr.signal_id
JOIN trade_targets tt ON ts.signal_id = tt.signal_id
WHERE tt.stop_loss_price > tr.low_price 
AND tt.stop_loss_price < tr.high_price;

INSERT INTO trade_stop_loss_cross
SELECT tr.signal_id,
tr.candle_number,
'close->price->open' AS status
FROM trade_signals ts
JOIN trade_reels tr ON ts.signal_id = tr.signal_id 
JOIN trade_targets tt ON ts.signal_id = tt.signal_id
WHERE tt.stop_loss_price IS NOT NULL AND (
	tt.stop_loss_price > tr.prev_close  
	AND tt.stop_loss_price < tr.open_price
) OR (
	tt.stop_loss_price < tr.prev_close 
	AND tt.stop_loss_price > tr.open_price
);

DROP TABLE IF EXISTS trades_cut; 
SELECT DISTINCT ON (tcc.signal_id) tcc.signal_id, tcc.candle_number, 'cutoff' AS evt 
INTO TEMPORARY TABLE trades_cut
FROM trade_cutoff_cross tcc
JOIN trade_starts ts ON ts.signal_id = tcc.signal_id 
WHERE tcc.candle_number < ts.candle_number
ORDER BY signal_id, candle_number ASC;


DROP TABLE IF EXISTS trade_events;
CREATE TEMPORARY TABLE trade_events 
AS SELECT * FROM (
	SELECT signal_id, candle_number, 'entry' AS evt, FALSE AS is_exit FROM trade_starts ts
	WHERE NOT EXISTS (SELECT 1 FROM trades_cut cut WHERE cut.signal_id = ts.signal_id)
) te1;

INSERT INTO trade_events 
SELECT * FROM ( 
	(
		SELECT DISTINCT ON (ttpc.signal_id) ttpc.signal_id, ttpc.candle_number, 'take_profit' AS evt, TRUE AS is_exit FROM backtest_parameters, trade_take_profit_cross ttpc
		JOIN trade_starts ts ON ttpc.signal_id = ts.signal_id 
		WHERE NOT EXISTS (SELECT 1 FROM trades_cut cut WHERE cut.signal_id = ttpc.signal_id)
		AND NULLIF(backtest_parameters.profit_lock_extra,0) IS NULL 
		AND ttpc.candle_number > ts.candle_number
		ORDER BY ttpc.signal_id, ttpc.candle_number ASC
	)
	UNION
	(
		SELECT DISTINCT ON (tplc.signal_id) tplc.signal_id, tplc.candle_number, 'profit_lock' AS evt, FALSE AS is_exit FROM trade_profit_lock_cross tplc 
		JOIN trade_starts ts ON tplc.signal_id = ts.signal_id 
		WHERE NOT EXISTS (SELECT 1 FROM trades_cut cut WHERE cut.signal_id = tplc.signal_id)
		AND tplc.candle_number > ts.candle_number
		ORDER BY tplc.signal_id, tplc.candle_number ASC
	)
	UNION
	(
		SELECT DISTINCT ON (tslc.signal_id) tslc.signal_id, tslc.candle_number, 'stop_loss' AS evt, TRUE AS is_exit FROM trade_stop_loss_cross tslc
		JOIN trade_starts ts ON tslc.signal_id = ts.signal_id 
		WHERE NOT EXISTS (SELECT 1 FROM trades_cut cut WHERE cut.signal_id = tslc.signal_id)
		AND tslc.candle_number > ts.candle_number
		ORDER BY tslc.signal_id, tslc.candle_number ASC
	)
) te2;

INSERT INTO trade_events 
SELECT * FROM (
	(	
		SELECT DISTINCT ON (tpac.signal_id) tpac.signal_id, tpac.candle_number, 'profit_stop_loss' AS evt, TRUE AS is_exit FROM trade_profit_adjust_cross tpac
		LEFT JOIN trade_events stop_loss ON stop_loss.signal_id = tpac.signal_id AND stop_loss.evt = 'stop_loss'
		LEFT JOIN trade_events profit_lock ON profit_lock.signal_id = tpac.signal_id AND profit_lock.evt = 'profit_lock'
		WHERE COALESCE(stop_loss.candle_number,999) > COALESCE(profit_lock.candle_number ,1000)
		AND profit_lock.candle_number < tpac.candle_number
		AND COALESCE(stop_loss.candle_number,999)  > tpac.candle_number
		ORDER BY tpac.signal_id, tpac.candle_number ASC
	)
	UNION
	(
		SELECT DISTINCT ON (tpec.signal_id) tpec.signal_id, tpec.candle_number, 'take_profit_extra' AS evt, TRUE AS is_exit FROM backtest_parameters, trade_profit_extra_cross tpec
		LEFT JOIN trade_events take_profit ON take_profit.signal_id = tpec.signal_id 
		LEFT JOIN trade_events profit_lock ON profit_lock.signal_id = tpec.signal_id 
		WHERE COALESCE(take_profit.candle_number,999) > COALESCE(profit_lock.candle_number ,1000)
		AND profit_lock.candle_number < tpec.candle_number 
		AND NULLIF(backtest_parameters.profit_lock_extra,0) IS NOT NULL 
		ORDER BY tpec.signal_id, tpec.candle_number ASC
	)
) te3;

--insert into trade events where there is an exit signal that matches something in the trade reels. 
INSERT INTO trade_events --ADD the cutoffs 
SELECT *, TRUE AS is_exit FROM trades_cut;

--inserto into trade events the ending candles incase any trades elapse their whole length
INSERT INTO trade_events 
SELECT DISTINCT ON (tr.signal_id) tr.signal_id, tr.candle_number, 'trade_end' AS evt, TRUE AS is_exit
FROM trade_reels tr 
WHERE EXISTS (SELECT 1 FROM trade_starts ts WHERE ts.signal_id = tr.signal_id) --esnure it actually started
ORDER BY tr.signal_id, tr.candle_number DESC;

INSERT INTO trade_events
SELECT signal_id, NULL AS candle_number, 'stagnated' AS evt, TRUE AS is_exit FROM 
trade_signals ts WHERE NOT EXISTS (SELECT 1 FROM trade_events te WHERE te.signal_id = ts.signal_id);

--inssert into trade events any exit signals that lie on the open trades 
WITH candle_start_end AS (
	SELECT signal_id, 
	candle_number,
	the_date AS start_date,
	LEAD(the_date) OVER (PARTITION BY signal_id ORDER BY the_date) AS end_date
	FROM trade_reels
),
candle_periods AS (
	SELECT signal_id,
	candle_number, 
	tsrange(start_date,end_date) AS candle_range 
	FROM candle_start_end 
	WHERE end_date IS NOT NULL
)
INSERT INTO trade_events
SELECT ts.signal_id,
cp.candle_number + 1 AS candle_number, --detected ON prev candle so EXIT ON this candle?
'exit_signal' AS evt, 
TRUE AS is_exit
FROM exit_signals es 
JOIN trade_signals ts ON es.strategy_ref = ts.strategy_ref AND es.instrument = ts.instrument AND es.direction = ts.direction --matched to start signal
JOIN candle_periods cp ON ts.signal_id = cp.signal_id AND  cp.candle_range @> es.the_date;

DROP TABLE IF EXISTS trade_ends; 
SELECT DISTINCT ON (signal_id) * 
INTO TEMPORARY TABLE trade_ends 
FROM trade_events 
WHERE is_exit--drops trades whose time elapsed - add these back IN & WORK OUT IF they won up OR lost down
ORDER BY signal_id, candle_number ASC;

---results 
DROP TABLE IF EXISTS trade_results; 
WITH results_pre AS (
	SELECT te.signal_id,
	tsig.direction,
	trs.the_date AS entry_date,
	ts.entry_price,
	ts.candle_number AS entry_candle,
	tre.the_date AS exit_date,
--	tre.high_price, 
--	tre.low_price,
	((tre.high_price + tre.low_price + tre.close_price) / 3.0) AS typical_exit_price,
	te.candle_number AS exit_candle, 
	te.evt AS status,
	CASE 
			WHEN tsig.direction = 'BUY' THEN ((tre.high_price + tre.low_price + tre.close_price) / 3.0) - ts.entry_price
			WHEN tsig.direction = 'SELL' THEN ts.entry_price - ((tre.high_price + tre.low_price + tre.close_price) / 3.0)
			ELSE NULL
	END AS result_movement
	FROM trade_ends te
	JOIN trade_signals tsig ON te.signal_id = tsig.signal_id 
	LEFT JOIN trade_starts ts ON te.signal_id = ts.signal_id
	LEFT JOIN trade_reels trs ON trs.signal_id = te.signal_id AND trs.candle_number = ts.candle_number 
	LEFT JOIN trade_reels tre ON tre.signal_id = te.signal_id AND tre.candle_number = te.candle_number 
)
SELECT signal_id, 
entry_date,
entry_price, 
entry_candle,
exit_date,
typical_exit_price AS exit_price,
exit_candle, 
result_movement,
(result_movement / entry_price) * 100 AS result_percent,
CASE 
	WHEN status = 'stagnated' THEN 'STAGNATED'
	WHEN status = 'take_profit' THEN 'WON'
	WHEN status = 'stop_loss' THEN 'LOST'
	WHEN status = 'trade_end' AND result_movement <= 0 THEN 'LOSING'
	WHEN status = 'trade_end' AND result_movement > 0 THEN 'WINNING'
	WHEN status = 'cutoff' THEN 'VOID'
	WHEN status = 'exit_signal' AND result_movement <= 0 THEN 'EXIT_DOWN'
	WHEN status = 'exit_signal' AND result_movement > 0 THEN 'EXIT_UP'
	WHEN status = 'profit_stop_loss' THEN 'PROFIT_LOCK'
	WHEN status = 'take_profit_extra' THEN 'WON_EXTRA'
	ELSE 'INVALID'
END AS result_status, 
NULL AS profit_path
INTO TEMPORARY TABLE trade_results
FROM results_pre;

WITH profit_path_prices AS (
	SELECT tr.signal_id,
	tr.candle_number,
	ts.direction,
	CASE 
		WHEN ts.direction = 'BUY' THEN tr.high_price 
		WHEN ts.direction = 'SELL' THEN tr.low_price 
		ELSE NULL
	END AS optimistic_price,
	CASE 
		WHEN ts.direction = 'BUY' THEN tr.low_price 
		WHEN ts.direction = 'SELL' THEN tr.high_price 
		ELSE NULL
	END AS pessimistic_price,
	(tr.high_price + tr.low_price + tr.close_price ) / 3.0 AS typical_price
	FROM trade_reels tr
	JOIN trade_signals ts ON tr.signal_id = ts.signal_id 
),
profit_price_normed AS (
	SELECT pps.signal_id, 
	pps.direction,
	pps.candle_number,
	CASE 
		WHEN pps.direction = 'BUY' THEN pps.optimistic_price - ts.entry_price 
		WHEN pps.direction = 'SELL' THEN ts.entry_price - pps.optimistic_price
		ELSE NULL 
	END / tsigs.take_profit_difference AS optimistic,
	CASE 
		WHEN pps.direction = 'BUY' THEN pps.pessimistic_price - ts.entry_price 
		WHEN pps.direction = 'SELL' THEN ts.entry_price - pps.pessimistic_price
		ELSE NULL 
	END / tsigs.take_profit_difference AS pessimistic,
	CASE 
		WHEN pps.direction = 'BUY' THEN pps.typical_price - ts.entry_price 
		WHEN pps.direction = 'SELL' THEN ts.entry_price - pps.typical_price
		ELSE NULL 
	END / tsigs.take_profit_difference AS typical
	FROM profit_path_prices pps
	JOIN trade_starts ts ON pps.signal_id = ts.signal_id 
	JOIN trade_ends te ON pps.signal_id = te.signal_id 
	JOIN trade_signals tsigs ON tsigs.signal_id = ts.signal_id
	WHERE pps.candle_number >= ts.candle_number 
	AND pps.candle_number <= te.candle_number
)
SELECT 
pps.signal_id,
ARRAY_AGG(pps.optimistic ORDER BY pps.candle_number ASC) AS optimistic,
ARRAY_AGG(pps.pessimistic ORDER BY pps.candle_number ASC) AS pessimistic,
ARRAY_AGG(pps.typical ORDER BY pps.candle_number ASC) AS typical
INTO TEMPORARY TABLE profit_paths 
FROM profit_price_normed pps
JOIN trade_starts ts ON pps.signal_id = ts.signal_id 
JOIN trade_ends te ON pps.signal_id = te.signal_id 
WHERE pps.candle_number >= ts.candle_number 
AND pps.candle_number <= te.candle_number
GROUP BY pps.signal_id;

SELECT 
to_json(tr) AS trade_result, --json OBJECT 
json_build_object(
	'optimistic',pp.optimistic,
	'pessimistic',pp.pessimistic,
	'typical',pp.typical
) AS profit_path
FROM trade_results tr
LEFT JOIN profit_paths pp ON tr.signal_id = pp.signal_id















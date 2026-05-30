-- =========================================================
-- testing_checks.sql
-- Проверки корректности БД для курсового проекта
-- =========================================================

-- ---------------------------------------------------------
-- 1. Объёмы данных по основным таблицам
-- ---------------------------------------------------------
SELECT 'import_files' AS object_name, COUNT(*) AS row_count FROM import_files
UNION ALL
SELECT 'raw_market_archive', COUNT(*) FROM raw_market_archive
UNION ALL
SELECT 'issuers', COUNT(*) FROM issuers
UNION ALL
SELECT 'instruments', COUNT(*) FROM instruments
UNION ALL
SELECT 'trading_calendar', COUNT(*) FROM trading_calendar
UNION ALL
SELECT 'market_daily_stats', COUNT(*) FROM market_daily_stats
ORDER BY object_name;


-- ---------------------------------------------------------
-- 2. Проверка пустых и некорректных значений
-- Ожидается: везде issue_count = 0
-- ---------------------------------------------------------
SELECT 'blank_file_name' AS check_name, COUNT(*) AS issue_count
FROM import_files
WHERE btrim(file_name) = ''

UNION ALL
SELECT 'blank_source_type', COUNT(*)
FROM import_files
WHERE btrim(source_type) = ''

UNION ALL
SELECT 'blank_issuer_name', COUNT(*)
FROM issuers
WHERE btrim(issuer_name) = ''

UNION ALL
SELECT 'blank_ticker', COUNT(*)
FROM instruments
WHERE btrim(ticker) = ''

UNION ALL
SELECT 'blank_currency_code', COUNT(*)
FROM instruments
WHERE btrim(currency_code) = ''

UNION ALL
SELECT 'negative_price_min', COUNT(*)
FROM market_daily_stats
WHERE price_min < 0

UNION ALL
SELECT 'negative_price_avg_weighted', COUNT(*)
FROM market_daily_stats
WHERE price_avg_weighted < 0

UNION ALL
SELECT 'negative_price_aux', COUNT(*)
FROM market_daily_stats
WHERE price_aux < 0

UNION ALL
SELECT 'negative_turnover_value', COUNT(*)
FROM market_daily_stats
WHERE turnover_value < 0

UNION ALL
SELECT 'negative_turnover_qty', COUNT(*)
FROM market_daily_stats
WHERE turnover_qty < 0

UNION ALL
SELECT 'negative_deals_count', COUNT(*)
FROM market_daily_stats
WHERE deals_count < 0

UNION ALL
SELECT 'negative_term_days', COUNT(*)
FROM market_daily_stats
WHERE term_days < 0;


-- ---------------------------------------------------------
-- 3. Проверка дубликатов
-- Ожидается: везде issue_count = 0
-- ---------------------------------------------------------
SELECT 'duplicate_tickers' AS check_name, COUNT(*) AS issue_count
FROM (
    SELECT ticker
    FROM instruments
    GROUP BY ticker
    HAVING COUNT(*) > 1
) t

UNION ALL
SELECT 'duplicate_issuer_names', COUNT(*)
FROM (
    SELECT issuer_name
    FROM issuers
    GROUP BY issuer_name
    HAVING COUNT(*) > 1
) t

UNION ALL
SELECT 'duplicate_market_daily_stats_pairs', COUNT(*)
FROM (
    SELECT instrument_id, trade_date
    FROM market_daily_stats
    GROUP BY instrument_id, trade_date
    HAVING COUNT(*) > 1
) t

UNION ALL
SELECT 'duplicate_raw_file_row_pairs', COUNT(*)
FROM (
    SELECT file_id, row_num
    FROM raw_market_archive
    GROUP BY file_id, row_num
    HAVING COUNT(*) > 1
) t;


-- ---------------------------------------------------------
-- 4. Проверка ссылочной целостности логическими запросами
-- Ожидается: везде issue_count = 0
-- ---------------------------------------------------------
SELECT 'raw_without_import_file' AS check_name, COUNT(*) AS issue_count
FROM raw_market_archive r
LEFT JOIN import_files f ON f.file_id = r.file_id
WHERE f.file_id IS NULL

UNION ALL
SELECT 'instrument_without_issuer', COUNT(*)
FROM instruments i
LEFT JOIN issuers s ON s.issuer_id = i.issuer_id
WHERE s.issuer_id IS NULL

UNION ALL
SELECT 'stats_without_instrument', COUNT(*)
FROM market_daily_stats m
LEFT JOIN instruments i ON i.instrument_id = m.instrument_id
WHERE i.instrument_id IS NULL

UNION ALL
SELECT 'stats_without_calendar_date', COUNT(*)
FROM market_daily_stats m
LEFT JOIN trading_calendar c ON c.trade_date = m.trade_date
WHERE c.trade_date IS NULL

UNION ALL
SELECT 'stats_with_invalid_file_id', COUNT(*)
FROM market_daily_stats m
LEFT JOIN import_files f ON f.file_id = m.file_id
WHERE m.file_id IS NOT NULL
  AND f.file_id IS NULL;


-- ---------------------------------------------------------
-- 5. Диапазон дат и распределение по инструментам
-- ---------------------------------------------------------
SELECT
    MIN(trade_date) AS min_trade_date,
    MAX(trade_date) AS max_trade_date,
    COUNT(*) AS total_rows
FROM market_daily_stats;

SELECT
    i.ticker,
    s.issuer_name,
    COUNT(*) AS stats_rows,
    MIN(m.trade_date) AS first_trade_date,
    MAX(m.trade_date) AS last_trade_date
FROM market_daily_stats m
JOIN instruments i ON i.instrument_id = m.instrument_id
JOIN issuers s ON s.issuer_id = i.issuer_id
GROUP BY i.ticker, s.issuer_name
ORDER BY stats_rows DESC, i.ticker;


-- ---------------------------------------------------------
-- 6. Проверка торгового календаря
-- Ожидается: issue_count = 0
-- ---------------------------------------------------------
SELECT COUNT(*) AS issue_count
FROM market_daily_stats m
LEFT JOIN trading_calendar c ON c.trade_date = m.trade_date
WHERE c.trade_date IS NULL;

SELECT
    COUNT(*) AS trading_days_count,
    MIN(trade_date) AS min_calendar_date,
    MAX(trade_date) AS max_calendar_date
FROM trading_calendar
WHERE is_trading_day = TRUE;


-- ---------------------------------------------------------
-- 7. Проверка аналитических объектов
-- ---------------------------------------------------------

-- 7.1. Количество строк в аналитических объектах
SELECT 'vw_instrument_daily_metrics' AS object_name, COUNT(*) AS row_count
FROM vw_instrument_daily_metrics
UNION ALL
SELECT 'mv_instrument_summary', COUNT(*)
FROM mv_instrument_summary
UNION ALL
SELECT 'vw_market_anomalies', COUNT(*)
FROM vw_market_anomalies
ORDER BY object_name;

-- 7.2. Ожидается: количество строк в vw_instrument_daily_metrics
-- совпадает с market_daily_stats
SELECT
    (SELECT COUNT(*) FROM market_daily_stats) AS market_daily_stats_count,
    (SELECT COUNT(*) FROM vw_instrument_daily_metrics) AS vw_daily_metrics_count;

-- 7.3. Ожидается: количество строк в mv_instrument_summary
-- равно числу инструментов, по которым есть история торгов
SELECT
    COUNT(DISTINCT instrument_id) AS instruments_with_stats
FROM market_daily_stats;

SELECT
    COUNT(*) AS rows_in_mv_summary
FROM mv_instrument_summary;

-- 7.4. Проверка last_active_trade_date
-- Ожидается: 0 строк
WITH actual_last_active AS (
    SELECT
        instrument_id,
        MAX(trade_date) AS actual_last_active_trade_date
    FROM vw_instrument_daily_metrics
    WHERE is_active_day = TRUE
    GROUP BY instrument_id
)
SELECT
    mv.instrument_id,
    mv.ticker,
    mv.last_active_trade_date,
    a.actual_last_active_trade_date
FROM mv_instrument_summary mv
JOIN actual_last_active a
    ON a.instrument_id = mv.instrument_id
WHERE mv.last_active_trade_date IS DISTINCT FROM a.actual_last_active_trade_date;

-- 7.5. Проверка наличия аномалий по допустимым типам
-- Ожидается: 0 строк
SELECT *
FROM vw_market_anomalies
WHERE anomaly_type NOT IN ('price_jump', 'turnover_spike', 'deals_spike');

-- 7.6. Примеры данных из аналитических объектов
SELECT *
FROM vw_instrument_daily_metrics
ORDER BY trade_date DESC, ticker
LIMIT 10;

SELECT *
FROM mv_instrument_summary
ORDER BY return_pct_all_period DESC NULLS LAST
LIMIT 10;

SELECT *
FROM vw_market_anomalies
ORDER BY trade_date DESC, ABS(anomaly_value_pct) DESC
LIMIT 10;


-- ---------------------------------------------------------
-- 8. Проверка согласованности агрегатов
-- ---------------------------------------------------------

-- 8.1. Сверка суммарного оборота raw -> normalized по файлам
SELECT
    f.file_id,
    f.file_name,
    COALESCE(r.raw_turnover_sum, 0) AS raw_turnover_sum,
    COALESCE(m.stats_turnover_sum, 0) AS stats_turnover_sum,
    ROUND(
        COALESCE(r.raw_turnover_sum, 0) - COALESCE(m.stats_turnover_sum, 0),
        2
    ) AS difference
FROM import_files f
LEFT JOIN (
    SELECT
        file_id,
        SUM(turnover_value_raw) AS raw_turnover_sum
    FROM raw_market_archive
    GROUP BY file_id
) r ON r.file_id = f.file_id
LEFT JOIN (
    SELECT
        file_id,
        SUM(turnover_value) AS stats_turnover_sum
    FROM market_daily_stats
    GROUP BY file_id
) m ON m.file_id = f.file_id
ORDER BY f.file_id;

-- 8.2. Сверка количества уникальных инструмент-дата в нормализованной таблице
SELECT
    COUNT(*) AS market_daily_stats_rows,
    COUNT(DISTINCT (instrument_id, trade_date)) AS distinct_instrument_date_pairs
FROM market_daily_stats;


-- ---------------------------------------------------------
-- 9. EXPLAIN ANALYZE для ключевых запросов
-- Выполнять по одному запросу отдельно
-- ---------------------------------------------------------

EXPLAIN ANALYZE
SELECT
    m.trade_date,
    i.ticker,
    m.price_avg_weighted,
    m.turnover_value
FROM market_daily_stats m
JOIN instruments i ON i.instrument_id = m.instrument_id
WHERE i.ticker = 'BERN-S0001'
  AND m.trade_date BETWEEN DATE '2024-01-01' AND DATE '2026-01-30'
ORDER BY m.trade_date;

EXPLAIN ANALYZE
SELECT
    ticker,
    issuer_name,
    return_pct_all_period,
    avg_turnover_value,
    volatility_pct
FROM mv_instrument_summary
WHERE avg_turnover_value >= 10000
ORDER BY return_pct_all_period DESC NULLS LAST
LIMIT 10;

EXPLAIN ANALYZE
SELECT
    trade_date,
    ticker,
    anomaly_type,
    anomaly_value_pct
FROM vw_market_anomalies
WHERE trade_date BETWEEN DATE '2025-01-01' AND DATE '2026-01-30'
ORDER BY trade_date DESC, ABS(anomaly_value_pct) DESC
LIMIT 20;
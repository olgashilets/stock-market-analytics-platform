HOME_SUMMARY_QUERY = """
SELECT
    current_database() AS database_name,
    COUNT(DISTINCT instrument_id) AS instruments_count,
    COUNT(*) AS market_daily_stats_rows,
    MIN(trade_date) AS min_trade_date,
    MAX(trade_date) AS max_trade_date,
    COALESCE(SUM(turnover_value), 0) AS total_turnover_value
FROM market_daily_stats;
"""

SCREENER_DEFAULT_DATES_QUERY = """
SELECT
    MIN(trade_date) AS min_trade_date,
    MAX(trade_date) AS max_trade_date
FROM trading_calendar
WHERE is_trading_day = TRUE;
"""

SCREEN_REQUERY = """
WITH calendar AS (
    SELECT COUNT(*)::INTEGER AS period_trading_days
    FROM trading_calendar
    WHERE is_trading_day = TRUE
      AND trade_date BETWEEN %(date_from)s AND %(date_to)s
),
period_data AS (
    SELECT
        v.instrument_id,
        v.ticker,
        v.issuer_name,
        v.trade_date,
        v.price_avg_weighted,
        v.turnover_value,
        v.deals_count,
        v.daily_return_pct
    FROM vw_instrument_daily_metrics v
    WHERE v.trade_date BETWEEN %(date_from)s AND %(date_to)s
),
ranked AS (
    SELECT
        p.*,
        ROW_NUMBER() OVER (
            PARTITION BY p.instrument_id
            ORDER BY p.trade_date ASC
        ) AS rn_first,
        ROW_NUMBER() OVER (
            PARTITION BY p.instrument_id
            ORDER BY p.trade_date DESC
        ) AS rn_last,
        MAX(p.price_avg_weighted) OVER (
            PARTITION BY p.instrument_id
            ORDER BY p.trade_date
            ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
        ) AS running_peak_price
    FROM period_data p
),
drawdowns AS (
    SELECT
        r.*,
        CASE
            WHEN r.running_peak_price IS NULL
                 OR r.running_peak_price = 0
                 OR r.price_avg_weighted IS NULL
            THEN NULL
            ELSE ((r.price_avg_weighted - r.running_peak_price) / r.running_peak_price) * 100
        END AS drawdown_pct
    FROM ranked r
),
agg AS (
    SELECT
        d.instrument_id,
        d.ticker,
        d.issuer_name,
        MAX(d.price_avg_weighted) FILTER (WHERE d.rn_first = 1) AS first_price,
        MAX(d.price_avg_weighted) FILTER (WHERE d.rn_last = 1) AS last_price,
        AVG(d.turnover_value) AS avg_turnover_value,
        AVG(d.deals_count) AS avg_deals_count,
        COUNT(*) AS active_days_count,
        STDDEV_SAMP(d.daily_return_pct) AS volatility_pct,
        MIN(d.drawdown_pct) AS max_drawdown_pct,
        MAX(d.trade_date) AS last_active_trade_date
    FROM drawdowns d
    GROUP BY
        d.instrument_id,
        d.ticker,
        d.issuer_name
)
SELECT
    a.ticker,
    a.issuer_name,
    ROUND(a.last_price::NUMERIC, 4) AS last_price,
    ROUND(
        CASE
            WHEN a.first_price IS NULL
                 OR a.first_price = 0
                 OR a.last_price IS NULL
            THEN NULL
            ELSE ((a.last_price - a.first_price) / a.first_price) * 100
        END::NUMERIC,
        2
    ) AS return_pct_period,
    ROUND(a.avg_turnover_value::NUMERIC, 2) AS avg_turnover_value,
    ROUND(a.avg_deals_count::NUMERIC, 2) AS avg_deals_count,
    a.active_days_count,
    c.period_trading_days,
    ROUND(
        CASE
            WHEN c.period_trading_days = 0 THEN NULL
            ELSE (a.active_days_count::NUMERIC / c.period_trading_days) * 100
        END,
        2
    ) AS active_days_share_pct,
    ROUND(a.volatility_pct::NUMERIC, 2) AS volatility_pct,
    ROUND(a.max_drawdown_pct::NUMERIC, 2) AS max_drawdown_pct,
    a.last_active_trade_date
FROM agg a
CROSS JOIN calendar c
WHERE (%(min_return_pct)s IS NULL OR
       (
           CASE
               WHEN a.first_price IS NULL OR a.first_price = 0 OR a.last_price IS NULL
               THEN NULL
               ELSE ((a.last_price - a.first_price) / a.first_price) * 100
           END
       ) >= %(min_return_pct)s)
  AND (%(max_volatility_pct)s IS NULL OR a.volatility_pct <= %(max_volatility_pct)s)
  AND (%(min_avg_turnover_value)s IS NULL OR a.avg_turnover_value >= %(min_avg_turnover_value)s)
  AND (%(min_avg_deals_count)s IS NULL OR a.avg_deals_count >= %(min_avg_deals_count)s)
  AND (%(min_active_days_share_pct)s IS NULL OR
       (
           CASE
               WHEN c.period_trading_days = 0 THEN NULL
               ELSE (a.active_days_count::NUMERIC / c.period_trading_days) * 100
           END
       ) >= %(min_active_days_share_pct)s)
  AND (%(max_abs_drawdown_pct)s IS NULL OR ABS(a.max_drawdown_pct) <= %(max_abs_drawdown_pct)s)
ORDER BY
    return_pct_period DESC NULLS LAST,
    avg_turnover_value DESC NULLS LAST,
    ticker;
"""

TICKER_OPTIONS_QUERY = """
SELECT ticker
FROM instruments
ORDER BY ticker;
"""

CARD_TICKER_DATE_BOUNDS_QUERY = """
SELECT
    MIN(trade_date) AS min_trade_date,
    MAX(trade_date) AS max_trade_date
FROM vw_instrument_daily_metrics
WHERE ticker = %(ticker)s;
"""

CARD_STATUS_QUERY = """
WITH thresholds AS (
    SELECT
        percentile_cont(0.33) WITHIN GROUP (ORDER BY avg_turnover_value) AS turnover_p33,
        percentile_cont(0.67) WITHIN GROUP (ORDER BY avg_turnover_value) AS turnover_p67,
        percentile_cont(0.33) WITHIN GROUP (ORDER BY volatility_pct) AS vol_p33,
        percentile_cont(0.67) WITHIN GROUP (ORDER BY volatility_pct) AS vol_p67
    FROM mv_instrument_summary
),
current_instrument AS (
    SELECT *
    FROM mv_instrument_summary
    WHERE ticker = %(ticker)s
)
SELECT
    CASE
        WHEN c.avg_turnover_value >= t.turnover_p67 THEN 'Высокая ликвидность'
        WHEN c.avg_turnover_value >= t.turnover_p33 THEN 'Средняя ликвидность'
        ELSE 'Низкая ликвидность'
    END AS liquidity_status,
    CASE
        WHEN c.volatility_pct >= t.vol_p67 THEN 'Высокий риск'
        WHEN c.volatility_pct >= t.vol_p33 THEN 'Средний риск'
        ELSE 'Низкий риск'
    END AS risk_status
FROM current_instrument c
CROSS JOIN thresholds t;
"""

CARD_KPI_QUERY = """
WITH period_data AS (
    SELECT *
    FROM vw_instrument_daily_metrics
    WHERE ticker = %(ticker)s
      AND trade_date BETWEEN %(date_from)s AND %(date_to)s
),
ranked AS (
    SELECT
        p.*,
        ROW_NUMBER() OVER (ORDER BY p.trade_date DESC) AS rn_desc,
        MAX(p.price_avg_weighted) OVER (
            ORDER BY p.trade_date
            ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
        ) AS running_peak_price
    FROM period_data p
),
drawdowns AS (
    SELECT
        r.*,
        CASE
            WHEN r.running_peak_price IS NULL
                 OR r.running_peak_price = 0
                 OR r.price_avg_weighted IS NULL
            THEN NULL
            ELSE ((r.price_avg_weighted - r.running_peak_price) / r.running_peak_price) * 100
        END AS drawdown_pct
    FROM ranked r
),
last_row AS (
    SELECT *
    FROM ranked
    WHERE rn_desc = 1
),
price_30 AS (
    SELECT price_avg_weighted AS price_30d
    FROM period_data
    WHERE trade_date <= (%(date_to)s::date - 30)
    ORDER BY trade_date DESC
    LIMIT 1
),
price_90 AS (
    SELECT price_avg_weighted AS price_90d
    FROM period_data
    WHERE trade_date <= (%(date_to)s::date - 90)
    ORDER BY trade_date DESC
    LIMIT 1
),
calendar AS (
    SELECT COUNT(*)::INTEGER AS period_trading_days
    FROM trading_calendar
    WHERE is_trading_day = TRUE
      AND trade_date BETWEEN %(date_from)s AND %(date_to)s
),
agg AS (
    SELECT
        MIN(issuer_name) AS issuer_name,
        MIN(currency_code) AS currency_code,
        MIN(instrument_type) AS instrument_type,
        AVG(turnover_value) AS avg_turnover_value,
        AVG(deals_count) AS avg_deals_count,
        COUNT(*) AS active_days_count,
        STDDEV_SAMP(daily_return_pct) AS volatility_pct,
        MIN(drawdown_pct) AS max_drawdown_pct
    FROM drawdowns
)
SELECT
    %(ticker)s::TEXT AS ticker,
    a.issuer_name,
    a.currency_code,
    a.instrument_type,
    l.trade_date AS last_trade_date,
    l.price_avg_weighted AS last_price,
    CASE
        WHEN l.prev_price_avg_weighted IS NULL
             OR l.prev_price_avg_weighted = 0
             OR l.price_avg_weighted IS NULL
        THEN NULL
        ELSE ((l.price_avg_weighted - l.prev_price_avg_weighted) / l.prev_price_avg_weighted) * 100
    END AS change_day_pct,
    CASE
        WHEN p30.price_30d IS NULL
             OR p30.price_30d = 0
             OR l.price_avg_weighted IS NULL
        THEN NULL
        ELSE ((l.price_avg_weighted - p30.price_30d) / p30.price_30d) * 100
    END AS change_30d_pct,
    CASE
        WHEN p90.price_90d IS NULL
             OR p90.price_90d = 0
             OR l.price_avg_weighted IS NULL
        THEN NULL
        ELSE ((l.price_avg_weighted - p90.price_90d) / p90.price_90d) * 100
    END AS change_90d_pct,
    a.avg_turnover_value,
    a.avg_deals_count,
    a.active_days_count,
    c.period_trading_days,
    CASE
        WHEN c.period_trading_days = 0 THEN NULL
        ELSE (a.active_days_count::NUMERIC / c.period_trading_days) * 100
    END AS active_days_share_pct,
    a.volatility_pct,
    a.max_drawdown_pct
FROM agg a
CROSS JOIN calendar c
LEFT JOIN last_row l ON TRUE
LEFT JOIN price_30 p30 ON TRUE
LEFT JOIN price_90 p90 ON TRUE;
"""

CARD_PRICE_HISTORY_QUERY = """
SELECT
    trade_date,
    price_avg_weighted
FROM vw_instrument_daily_metrics
WHERE ticker = %(ticker)s
  AND trade_date BETWEEN %(date_from)s AND %(date_to)s
ORDER BY trade_date;
"""

CARD_ACTIVITY_HISTORY_QUERY = """
SELECT
    trade_date,
    turnover_value,
    deals_count
FROM vw_instrument_daily_metrics
WHERE ticker = %(ticker)s
  AND trade_date BETWEEN %(date_from)s AND %(date_to)s
ORDER BY trade_date;
"""

CARD_ANOMALIES_QUERY = """
SELECT
    trade_date,
    anomaly_type,
    anomaly_value_pct,
    price_avg_weighted,
    turnover_value,
    deals_count
FROM vw_market_anomalies
WHERE ticker = %(ticker)s
  AND trade_date BETWEEN %(date_from)s AND %(date_to)s
ORDER BY trade_date DESC, anomaly_type
LIMIT 20;
"""

COMPARISON_SUMMARY_QUERY = """
WITH calendar AS (
    SELECT COUNT(*)::INTEGER AS period_trading_days
    FROM trading_calendar
    WHERE is_trading_day = TRUE
      AND trade_date BETWEEN %(date_from)s AND %(date_to)s
),
period_data AS (
    SELECT
        v.instrument_id,
        v.ticker,
        v.issuer_name,
        v.trade_date,
        v.price_avg_weighted,
        v.turnover_value,
        v.deals_count,
        v.daily_return_pct
    FROM vw_instrument_daily_metrics v
    WHERE v.ticker = ANY(%(tickers)s)
      AND v.trade_date BETWEEN %(date_from)s AND %(date_to)s
),
ranked AS (
    SELECT
        p.*,
        ROW_NUMBER() OVER (
            PARTITION BY p.instrument_id
            ORDER BY p.trade_date ASC
        ) AS rn_first,
        ROW_NUMBER() OVER (
            PARTITION BY p.instrument_id
            ORDER BY p.trade_date DESC
        ) AS rn_last,
        MAX(p.price_avg_weighted) OVER (
            PARTITION BY p.instrument_id
            ORDER BY p.trade_date
            ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
        ) AS running_peak_price
    FROM period_data p
),
drawdowns AS (
    SELECT
        r.*,
        CASE
            WHEN r.running_peak_price IS NULL
                 OR r.running_peak_price = 0
                 OR r.price_avg_weighted IS NULL
            THEN NULL
            ELSE ((r.price_avg_weighted - r.running_peak_price) / r.running_peak_price) * 100
        END AS drawdown_pct
    FROM ranked r
)
SELECT
    d.ticker,
    MIN(d.issuer_name) AS issuer_name,
    MAX(d.price_avg_weighted) FILTER (WHERE d.rn_first = 1) AS first_price,
    MAX(d.price_avg_weighted) FILTER (WHERE d.rn_last = 1) AS last_price,
    CASE
        WHEN MAX(d.price_avg_weighted) FILTER (WHERE d.rn_first = 1) IS NULL
             OR MAX(d.price_avg_weighted) FILTER (WHERE d.rn_first = 1) = 0
             OR MAX(d.price_avg_weighted) FILTER (WHERE d.rn_last = 1) IS NULL
        THEN NULL
        ELSE (
            (
                MAX(d.price_avg_weighted) FILTER (WHERE d.rn_last = 1)
                - MAX(d.price_avg_weighted) FILTER (WHERE d.rn_first = 1)
            )
            / MAX(d.price_avg_weighted) FILTER (WHERE d.rn_first = 1)
        ) * 100
    END AS return_pct_period,
    AVG(d.turnover_value) AS avg_turnover_value,
    AVG(d.deals_count) AS avg_deals_count,
    COUNT(*) AS active_days_count,
    c.period_trading_days,
    CASE
        WHEN c.period_trading_days = 0 THEN NULL
        ELSE (COUNT(*)::NUMERIC / c.period_trading_days) * 100
    END AS active_days_share_pct,
    STDDEV_SAMP(d.daily_return_pct) AS volatility_pct,
    MIN(d.drawdown_pct) AS max_drawdown_pct
FROM drawdowns d
CROSS JOIN calendar c
GROUP BY
    d.ticker,
    c.period_trading_days
ORDER BY d.ticker;
"""

COMPARISON_HISTORY_QUERY = """
SELECT
    trade_date,
    ticker,
    price_avg_weighted,
    daily_return_pct
FROM vw_instrument_daily_metrics
WHERE ticker = ANY(%(tickers)s)
  AND trade_date BETWEEN %(date_from)s AND %(date_to)s
ORDER BY trade_date, ticker;
"""

ANOMALIES_PAGE_QUERY = """
SELECT
    trade_date,
    ticker,
    issuer_name,
    anomaly_type,
    anomaly_value_pct,
    price_avg_weighted,
    turnover_value,
    deals_count
FROM vw_market_anomalies
WHERE trade_date BETWEEN %(date_from)s AND %(date_to)s
  AND (%(ticker)s IS NULL OR ticker = %(ticker)s)
  AND anomaly_type = ANY(%(anomaly_types)s)
  AND ABS(anomaly_value_pct) >= %(min_abs_anomaly_pct)s
ORDER BY trade_date DESC, ABS(anomaly_value_pct) DESC, ticker;
"""

SQL_DEMO_TABLE_COUNTS_QUERY = """
SELECT 'import_files' AS table_name, COUNT(*) AS row_count FROM import_files
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
ORDER BY table_name;
"""

SQL_DEMO_INDEXES_QUERY = """
SELECT
    tablename,
    indexname,
    indexdef
FROM pg_indexes
WHERE schemaname = 'public'
  AND tablename IN (
      'import_files',
      'raw_market_archive',
      'issuers',
      'instruments',
      'trading_calendar',
      'market_daily_stats',
      'mv_instrument_summary'
  )
ORDER BY tablename, indexname;
"""

SQL_DEMO_DAILY_METRICS_SAMPLE_QUERY = """
SELECT
    ticker,
    issuer_name,
    trade_date,
    price_avg_weighted,
    prev_price_avg_weighted,
    price_change_abs,
    daily_return_pct,
    intraday_range_pct,
    is_active_day
FROM vw_instrument_daily_metrics
ORDER BY trade_date DESC, ticker
LIMIT 20;
"""

SQL_DEMO_SUMMARY_SAMPLE_QUERY = """
SELECT
    ticker,
    issuer_name,
    first_trade_date,
    last_trade_date,
    first_price,
    last_price,
    return_pct_all_period,
    avg_turnover_value,
    avg_deals_count,
    active_days_share_pct,
    volatility_pct,
    max_drawdown_pct,
    last_active_trade_date
FROM mv_instrument_summary
ORDER BY return_pct_all_period DESC NULLS LAST
LIMIT 20;
"""

SQL_DEMO_ANOMALIES_SAMPLE_QUERY = """
SELECT
    trade_date,
    ticker,
    issuer_name,
    anomaly_type,
    anomaly_value_pct,
    price_avg_weighted,
    turnover_value,
    deals_count
FROM vw_market_anomalies
ORDER BY trade_date DESC, ABS(anomaly_value_pct) DESC
LIMIT 20;
"""

SQL_DEMO_COMPLEX_QUERY = """
WITH ranked AS (
    SELECT
        ticker,
        issuer_name,
        return_pct_all_period,
        avg_turnover_value,
        volatility_pct,
        max_drawdown_pct,
        NTILE(3) OVER (ORDER BY avg_turnover_value DESC NULLS LAST) AS liquidity_group,
        RANK() OVER (ORDER BY return_pct_all_period DESC NULLS LAST) AS return_rank
    FROM mv_instrument_summary
)
SELECT
    ticker,
    issuer_name,
    return_pct_all_period,
    avg_turnover_value,
    volatility_pct,
    max_drawdown_pct,
    liquidity_group,
    return_rank
FROM ranked
ORDER BY return_rank, ticker
LIMIT 15;
"""

SQL_DEMO_EXPLAIN_QUERY = """
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
"""
BEGIN;

DROP VIEW IF EXISTS vw_market_anomalies CASCADE;
DROP MATERIALIZED VIEW IF EXISTS mv_instrument_summary CASCADE;
DROP VIEW IF EXISTS vw_instrument_daily_metrics CASCADE;

CREATE VIEW vw_instrument_daily_metrics AS
WITH base AS (
    SELECT
        m.stat_id,
        m.instrument_id,
        i.ticker,
        iss.issuer_id,
        iss.issuer_name,
        i.currency_code,
        i.instrument_type,
        m.trade_date,
        m.price_min,
        m.price_avg_weighted,
        m.price_aux,
        m.yield_min_pct,
        m.yield_max_pct,
        m.yield_avg_pct,
        m.turnover_value,
        m.turnover_qty,
        m.deals_count,
        m.term_days,
        COALESCE(m.market_segment, 'shares') AS market_segment,
        m.file_id,
        m.created_at,
        LAG(m.price_avg_weighted) OVER (
            PARTITION BY m.instrument_id
            ORDER BY m.trade_date
        ) AS prev_price_avg_weighted
    FROM market_daily_stats m
    JOIN instruments i
        ON i.instrument_id = m.instrument_id
    JOIN issuers iss
        ON iss.issuer_id = i.issuer_id
)
SELECT
    stat_id,
    instrument_id,
    ticker,
    issuer_id,
    issuer_name,
    currency_code,
    instrument_type,
    trade_date,
    price_min,
    price_avg_weighted,
    price_aux,
    yield_min_pct,
    yield_max_pct,
    yield_avg_pct,
    turnover_value,
    turnover_qty,
    deals_count,
    term_days,
    market_segment,
    file_id,
    created_at,
    prev_price_avg_weighted,
    CASE
        WHEN prev_price_avg_weighted IS NULL OR price_avg_weighted IS NULL THEN NULL
        ELSE price_avg_weighted - prev_price_avg_weighted
    END AS price_change_abs,
    CASE
        WHEN prev_price_avg_weighted IS NULL
             OR prev_price_avg_weighted = 0
             OR price_avg_weighted IS NULL
        THEN NULL
        ELSE ((price_avg_weighted - prev_price_avg_weighted) / prev_price_avg_weighted) * 100
    END AS daily_return_pct,
    CASE
        WHEN COALESCE(turnover_value, 0) > 0 OR COALESCE(deals_count, 0) > 0 THEN TRUE
        ELSE FALSE
    END AS is_active_day,
    CASE
        WHEN price_min IS NULL OR price_aux IS NULL OR price_min = 0 THEN NULL
        ELSE ((price_aux - price_min) / price_min) * 100
    END AS intraday_range_pct
FROM base;

CREATE MATERIALIZED VIEW mv_instrument_summary AS
WITH daily AS (
    SELECT *
    FROM vw_instrument_daily_metrics
),
ranked AS (
    SELECT
        d.*,
        ROW_NUMBER() OVER (
            PARTITION BY d.instrument_id
            ORDER BY d.trade_date ASC
        ) AS rn_first,
        ROW_NUMBER() OVER (
            PARTITION BY d.instrument_id
            ORDER BY d.trade_date DESC
        ) AS rn_last,
        MAX(d.price_avg_weighted) OVER (
            PARTITION BY d.instrument_id
            ORDER BY d.trade_date
            ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
        ) AS running_peak_price
    FROM daily d
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
    instrument_id,
    ticker,
    issuer_id,
    issuer_name,
    currency_code,
    instrument_type,
    MIN(trade_date) AS first_trade_date,
    MAX(trade_date) AS last_trade_date,
    MAX(price_avg_weighted) FILTER (WHERE rn_first = 1) AS first_price,
    MAX(price_avg_weighted) FILTER (WHERE rn_last = 1) AS last_price,
    CASE
        WHEN MAX(price_avg_weighted) FILTER (WHERE rn_first = 1) IS NULL
             OR MAX(price_avg_weighted) FILTER (WHERE rn_first = 1) = 0
             OR MAX(price_avg_weighted) FILTER (WHERE rn_last = 1) IS NULL
        THEN NULL
        ELSE (
            (
                MAX(price_avg_weighted) FILTER (WHERE rn_last = 1)
                - MAX(price_avg_weighted) FILTER (WHERE rn_first = 1)
            )
            / MAX(price_avg_weighted) FILTER (WHERE rn_first = 1)
        ) * 100
    END AS return_pct_all_period,
    AVG(turnover_value) AS avg_turnover_value,
    AVG(deals_count) AS avg_deals_count,
    SUM(CASE WHEN is_active_day THEN 1 ELSE 0 END) AS active_days_count,
    COUNT(*) AS total_days_count,
    CASE
        WHEN COUNT(*) = 0 THEN NULL
        ELSE (SUM(CASE WHEN is_active_day THEN 1 ELSE 0 END)::NUMERIC / COUNT(*)) * 100
    END AS active_days_share_pct,
    STDDEV_SAMP(daily_return_pct) AS volatility_pct,
    MIN(drawdown_pct) AS max_drawdown_pct,
    MAX(trade_date) FILTER (WHERE is_active_day) AS last_active_trade_date
FROM drawdowns
GROUP BY
    instrument_id,
    ticker,
    issuer_id,
    issuer_name,
    currency_code,
    instrument_type;

CREATE UNIQUE INDEX idx_mv_instrument_summary_instrument_id
    ON mv_instrument_summary(instrument_id);

CREATE INDEX idx_mv_instrument_summary_ticker
    ON mv_instrument_summary(ticker);

CREATE VIEW vw_market_anomalies AS
WITH metrics AS (
    SELECT
        v.*,
        AVG(v.turnover_value) OVER (
            PARTITION BY v.instrument_id
            ORDER BY v.trade_date
            ROWS BETWEEN 20 PRECEDING AND 1 PRECEDING
        ) AS avg_turnover_prev20,
        AVG(v.deals_count) OVER (
            PARTITION BY v.instrument_id
            ORDER BY v.trade_date
            ROWS BETWEEN 20 PRECEDING AND 1 PRECEDING
        ) AS avg_deals_prev20,
        STDDEV_SAMP(v.daily_return_pct) OVER (
            PARTITION BY v.instrument_id
            ORDER BY v.trade_date
            ROWS BETWEEN 20 PRECEDING AND 1 PRECEDING
        ) AS std_return_prev20
    FROM vw_instrument_daily_metrics v
)
SELECT
    instrument_id,
    ticker,
    issuer_name,
    trade_date,
    'price_jump'::TEXT AS anomaly_type,
    daily_return_pct AS anomaly_value_pct,
    price_avg_weighted,
    turnover_value,
    deals_count
FROM metrics
WHERE daily_return_pct IS NOT NULL
  AND ABS(daily_return_pct) >= GREATEST(1.5::NUMERIC, 2.5 * COALESCE(std_return_prev20, 0))

UNION ALL

SELECT
    instrument_id,
    ticker,
    issuer_name,
    trade_date,
    'turnover_spike'::TEXT AS anomaly_type,
    ((turnover_value / avg_turnover_prev20) - 1) * 100 AS anomaly_value_pct,
    price_avg_weighted,
    turnover_value,
    deals_count
FROM metrics
WHERE avg_turnover_prev20 IS NOT NULL
  AND avg_turnover_prev20 > 0
  AND turnover_value IS NOT NULL
  AND turnover_value >= avg_turnover_prev20 * 2.5

UNION ALL

SELECT
    instrument_id,
    ticker,
    issuer_name,
    trade_date,
    'deals_spike'::TEXT AS anomaly_type,
    ((deals_count / avg_deals_prev20) - 1) * 100 AS anomaly_value_pct,
    price_avg_weighted,
    turnover_value,
    deals_count
FROM metrics
WHERE avg_deals_prev20 IS NOT NULL
  AND avg_deals_prev20 > 0
  AND deals_count IS NOT NULL
  AND deals_count >= avg_deals_prev20 * 2.5;

COMMIT;
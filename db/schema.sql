BEGIN;

CREATE TABLE IF NOT EXISTS import_files (
    file_id          BIGSERIAL PRIMARY KEY,
    file_name        TEXT NOT NULL,
    source_type      TEXT NOT NULL DEFAULT 'archive_demo',
    loaded_at        TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    rows_count       INTEGER NOT NULL DEFAULT 0,
    notes            TEXT,
    CONSTRAINT chk_import_files_file_name_not_blank
        CHECK (btrim(file_name) <> ''),
    CONSTRAINT chk_import_files_source_type_not_blank
        CHECK (btrim(source_type) <> ''),
    CONSTRAINT chk_import_files_rows_count_nonnegative
        CHECK (rows_count >= 0)
);

CREATE TABLE IF NOT EXISTS raw_market_archive (
    raw_id               BIGSERIAL PRIMARY KEY,
    file_id              BIGINT NOT NULL REFERENCES import_files(file_id) ON DELETE CASCADE,
    row_num              INTEGER NOT NULL,
    ticker_raw           TEXT,
    issuer_name_raw      TEXT,
    currency_code_raw    TEXT,
    price_min_raw        NUMERIC(18,6),
    price_avg_raw        NUMERIC(18,6),
    price_aux_raw        NUMERIC(18,6),
    yield_min_raw        NUMERIC(12,6),
    yield_max_raw        NUMERIC(12,6),
    yield_avg_raw        NUMERIC(12,6),
    turnover_value_raw   NUMERIC(20,2),
    turnover_qty_raw     NUMERIC(20,6),
    deals_count_raw      INTEGER,
    term_days_raw        INTEGER,
    trade_datetime_raw   TIMESTAMP,
    market_segment_raw   TEXT,
    CONSTRAINT uq_raw_file_row UNIQUE (file_id, row_num),
    CONSTRAINT chk_raw_market_archive_row_num_positive
        CHECK (row_num > 0)
);

CREATE TABLE IF NOT EXISTS issuers (
    issuer_id            BIGSERIAL PRIMARY KEY,
    issuer_name          TEXT NOT NULL,
    issuer_short_name    TEXT,
    is_active            BOOLEAN NOT NULL DEFAULT TRUE,
    CONSTRAINT uq_issuer_name UNIQUE (issuer_name),
    CONSTRAINT chk_issuers_issuer_name_not_blank
        CHECK (btrim(issuer_name) <> '')
);

CREATE TABLE IF NOT EXISTS instruments (
    instrument_id        BIGSERIAL PRIMARY KEY,
    ticker               TEXT NOT NULL,
    issuer_id            BIGINT NOT NULL REFERENCES issuers(issuer_id) ON DELETE RESTRICT,
    currency_code        VARCHAR(10) NOT NULL,
    instrument_type      TEXT NOT NULL DEFAULT 'share',
    term_days            INTEGER,
    is_active            BOOLEAN NOT NULL DEFAULT TRUE,
    CONSTRAINT uq_instrument_ticker UNIQUE (ticker),
    CONSTRAINT chk_instruments_ticker_not_blank
        CHECK (btrim(ticker) <> ''),
    CONSTRAINT chk_instruments_currency_code_not_blank
        CHECK (btrim(currency_code) <> ''),
    CONSTRAINT chk_instrument_type
        CHECK (instrument_type IN ('share', 'bond', 'depositary_receipt', 'other')),
    CONSTRAINT chk_instruments_term_days_nonnegative
        CHECK (term_days IS NULL OR term_days >= 0)
);

CREATE TABLE IF NOT EXISTS trading_calendar (
    trade_date           DATE PRIMARY KEY,
    year_num             INTEGER NOT NULL,
    month_num            INTEGER NOT NULL,
    quarter_num          INTEGER NOT NULL,
    week_num             INTEGER NOT NULL,
    is_trading_day       BOOLEAN NOT NULL DEFAULT TRUE,
    CONSTRAINT chk_trading_calendar_year_num
        CHECK (year_num >= 2000),
    CONSTRAINT chk_trading_calendar_month_num
        CHECK (month_num BETWEEN 1 AND 12),
    CONSTRAINT chk_trading_calendar_quarter_num
        CHECK (quarter_num BETWEEN 1 AND 4),
    CONSTRAINT chk_trading_calendar_week_num
        CHECK (week_num BETWEEN 1 AND 53)
);

CREATE TABLE IF NOT EXISTS market_daily_stats (
    stat_id              BIGSERIAL PRIMARY KEY,
    instrument_id        BIGINT NOT NULL REFERENCES instruments(instrument_id) ON DELETE RESTRICT,
    trade_date           DATE NOT NULL REFERENCES trading_calendar(trade_date) ON DELETE RESTRICT,
    price_min            NUMERIC(18,6),
    price_avg_weighted   NUMERIC(18,6),
    price_aux            NUMERIC(18,6),
    yield_min_pct        NUMERIC(12,6),
    yield_max_pct        NUMERIC(12,6),
    yield_avg_pct        NUMERIC(12,6),
    turnover_value       NUMERIC(20,2),
    turnover_qty         NUMERIC(20,6),
    deals_count          INTEGER,
    term_days            INTEGER,
    market_segment       TEXT,
    file_id              BIGINT REFERENCES import_files(file_id) ON DELETE SET NULL,
    created_at           TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_market_daily_stats UNIQUE (instrument_id, trade_date),
    CONSTRAINT chk_market_daily_stats_price_min_nonnegative
        CHECK (price_min IS NULL OR price_min >= 0),
    CONSTRAINT chk_market_daily_stats_price_avg_weighted_nonnegative
        CHECK (price_avg_weighted IS NULL OR price_avg_weighted >= 0),
    CONSTRAINT chk_market_daily_stats_price_aux_nonnegative
        CHECK (price_aux IS NULL OR price_aux >= 0),
    CONSTRAINT chk_market_daily_stats_turnover_value_nonnegative
        CHECK (turnover_value IS NULL OR turnover_value >= 0),
    CONSTRAINT chk_market_daily_stats_turnover_qty_nonnegative
        CHECK (turnover_qty IS NULL OR turnover_qty >= 0),
    CONSTRAINT chk_market_daily_stats_deals_count_nonnegative
        CHECK (deals_count IS NULL OR deals_count >= 0),
    CONSTRAINT chk_market_daily_stats_term_days_nonnegative
        CHECK (term_days IS NULL OR term_days >= 0)
);

CREATE INDEX IF NOT EXISTS idx_raw_market_archive_file_id
    ON raw_market_archive(file_id);

CREATE INDEX IF NOT EXISTS idx_instruments_ticker
    ON instruments(ticker);

CREATE INDEX IF NOT EXISTS idx_instruments_issuer_id
    ON instruments(issuer_id);

CREATE INDEX IF NOT EXISTS idx_market_daily_stats_instrument_date
    ON market_daily_stats(instrument_id, trade_date);

CREATE INDEX IF NOT EXISTS idx_market_daily_stats_trade_date
    ON market_daily_stats(trade_date);

CREATE INDEX IF NOT EXISTS idx_market_daily_stats_file_id
    ON market_daily_stats(file_id);

COMMIT;
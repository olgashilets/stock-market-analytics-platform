from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import Iterable

import pandas as pd
import psycopg2
from psycopg2.extras import execute_values


RAW_COLUMNS = [
    "ticker_raw",
    "issuer_name_raw",
    "currency_code_raw",
    "price_min_raw",
    "price_avg_raw",
    "price_aux_raw",
    "yield_min_raw",
    "yield_max_raw",
    "yield_avg_raw",
    "turnover_value_raw",
    "turnover_qty_raw",
    "deals_count_raw",
    "term_days_raw",
    "trade_datetime_raw",
    "market_segment_raw",
]

HEADER_MAP = {
    "Тикер": "ticker_raw",
    "Краткое наименование эмитента": "issuer_name_raw",
    "Валюта ценообразования": "currency_code_raw",
    "Цена, вал.обр. (мин.)": "price_min_raw",
    "Цена, вал.обр. (срвз.)": "price_avg_raw",
    "Доходность (мин., %)": "yield_min_raw",
    "Доходность (макс., %)": "yield_max_raw",
    "Доходность (срвз., %)": "yield_avg_raw",
    "Оборот (в вал.ценообр.)": "turnover_value_raw",
    "Оборот (в шт.)": "turnover_qty_raw",
    "Количество сделок": "deals_count_raw",
    "Срок": "term_days_raw",
    "Время сделки": "trade_datetime_raw",
}

NUMERIC_COLUMNS = [
    "price_min_raw",
    "price_avg_raw",
    "price_aux_raw",
    "yield_min_raw",
    "yield_max_raw",
    "yield_avg_raw",
    "turnover_value_raw",
    "turnover_qty_raw",
    "deals_count_raw",
    "term_days_raw",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Загрузка демо-архивов БВФБ-формата в PostgreSQL"
    )
    parser.add_argument(
        "--input-dir",
        required=True,
        help="Папка с xlsx-архивами, например data/generated_archives",
    )
    parser.add_argument(
        "--sheet-name",
        default="MarketStockResult",
        help="Имя листа в xlsx-файлах",
    )
    parser.add_argument(
        "--market-segment",
        default="shares",
        help="Значение по умолчанию для market_segment_raw, если его нет в файле",
    )
    parser.add_argument(
        "--source-type",
        default="archive_demo_xlsx",
        help="Значение source_type для import_files",
    )
    parser.add_argument(
        "--replace-existing",
        action="store_true",
        help="Перед загрузкой удалить старые записи import_files с таким же file_name",
    )
    parser.add_argument(
        "--refresh-materialized-view",
        action="store_true",
        help="Обновить mv_instrument_summary после загрузки всех файлов, если она уже создана",
    )
    parser.add_argument("--host", default=os.getenv("PGHOST", "localhost"))
    parser.add_argument("--port", type=int, default=int(os.getenv("PGPORT", "5432")))
    parser.add_argument("--dbname", default=os.getenv("PGDATABASE", "investment_sbd"))
    parser.add_argument("--user", default=os.getenv("PGUSER", "postgres"))
    parser.add_argument("--password", default=os.getenv("PGPASSWORD"))
    return parser.parse_args()


def connect_db(args: argparse.Namespace):
    return psycopg2.connect(
        host=args.host,
        port=args.port,
        dbname=args.dbname,
        user=args.user,
        password=args.password,
    )


def normalize_text(value):
    if pd.isna(value):
        return None
    text = str(value).strip()
    return text if text else None


def load_archive_dataframe(
    file_path: Path,
    *,
    sheet_name: str,
    market_segment: str,
) -> pd.DataFrame:
    try:
        df = pd.read_excel(file_path, sheet_name=sheet_name)
    except ValueError:
        df = pd.read_excel(file_path)

    if df.empty:
        result = pd.DataFrame(columns=RAW_COLUMNS)
        result["market_segment_raw"] = []
        return result

    original_columns = list(df.columns)
    rename_map: dict[str, str] = {}

    for idx, col in enumerate(original_columns):
        if idx == 5:
            rename_map[col] = "price_aux_raw"
        elif col in HEADER_MAP:
            rename_map[col] = HEADER_MAP[col]

    df = df.rename(columns=rename_map)

    missing = [col for col in RAW_COLUMNS if col not in df.columns and col != "market_segment_raw"]
    if missing:
        raise ValueError(f"В файле {file_path.name} не найдены ожидаемые столбцы: {missing}")

    df["market_segment_raw"] = market_segment
    df = df[RAW_COLUMNS].copy()
    df = df.dropna(how="all")

    for text_col in ["ticker_raw", "issuer_name_raw", "currency_code_raw", "market_segment_raw"]:
        df[text_col] = df[text_col].apply(normalize_text)

    for col in NUMERIC_COLUMNS:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    if "trade_datetime_raw" in df.columns:
        df["trade_datetime_raw"] = pd.to_datetime(df["trade_datetime_raw"], errors="coerce")

    return df


def dataframe_to_raw_tuples(df: pd.DataFrame, file_id: int) -> list[tuple]:
    records: list[tuple] = []

    for row_num, row in enumerate(df.itertuples(index=False), start=1):
        row_dict = row._asdict()
        records.append(
            (
                file_id,
                row_num,
                row_dict["ticker_raw"],
                row_dict["issuer_name_raw"],
                row_dict["currency_code_raw"],
                to_python_number(row_dict["price_min_raw"]),
                to_python_number(row_dict["price_avg_raw"]),
                to_python_number(row_dict["price_aux_raw"]),
                to_python_number(row_dict["yield_min_raw"]),
                to_python_number(row_dict["yield_max_raw"]),
                to_python_number(row_dict["yield_avg_raw"]),
                to_python_number(row_dict["turnover_value_raw"]),
                to_python_number(row_dict["turnover_qty_raw"]),
                to_python_int(row_dict["deals_count_raw"]),
                to_python_int(row_dict["term_days_raw"]),
                row_dict["trade_datetime_raw"].to_pydatetime() if pd.notna(row_dict["trade_datetime_raw"]) else None,
                row_dict["market_segment_raw"],
            )
        )

    return records


def to_python_number(value):
    if pd.isna(value):
        return None
    return float(value)


def to_python_int(value):
    if pd.isna(value):
        return None
    return int(value)


def delete_existing_imports(cur, file_name: str) -> None:
    cur.execute("DELETE FROM import_files WHERE file_name = %s", (file_name,))


def get_existing_import_id(cur, file_name: str):
    cur.execute(
        """
        SELECT file_id
        FROM import_files
        WHERE file_name = %s
        ORDER BY loaded_at DESC, file_id DESC
        LIMIT 1
        """,
        (file_name,),
    )
    row = cur.fetchone()
    return row[0] if row else None


def insert_import_file(cur, file_name: str, source_type: str, rows_count: int, notes: str | None) -> int:
    cur.execute(
        """
        INSERT INTO import_files (file_name, source_type, rows_count, notes)
        VALUES (%s, %s, %s, %s)
        RETURNING file_id
        """,
        (file_name, source_type, rows_count, notes),
    )
    return cur.fetchone()[0]


def bulk_insert_raw(cur, rows: Iterable[tuple]) -> None:
    rows = list(rows)
    if not rows:
        return

    execute_values(
        cur,
        """
        INSERT INTO raw_market_archive (
            file_id,
            row_num,
            ticker_raw,
            issuer_name_raw,
            currency_code_raw,
            price_min_raw,
            price_avg_raw,
            price_aux_raw,
            yield_min_raw,
            yield_max_raw,
            yield_avg_raw,
            turnover_value_raw,
            turnover_qty_raw,
            deals_count_raw,
            term_days_raw,
            trade_datetime_raw,
            market_segment_raw
        ) VALUES %s
        """,
        rows,
        page_size=1000,
    )


def populate_issuers(cur, file_id: int) -> None:
    cur.execute(
        """
        INSERT INTO issuers (issuer_name)
        SELECT DISTINCT btrim(issuer_name_raw)
        FROM raw_market_archive
        WHERE file_id = %s
          AND issuer_name_raw IS NOT NULL
          AND btrim(issuer_name_raw) <> ''
        ON CONFLICT (issuer_name) DO NOTHING
        """,
        (file_id,),
    )


def populate_instruments(cur, file_id: int, instrument_type: str = "share") -> None:
    cur.execute(
        """
        INSERT INTO instruments (
            ticker,
            issuer_id,
            currency_code,
            instrument_type,
            term_days
        )
        SELECT DISTINCT
            btrim(r.ticker_raw) AS ticker,
            i.issuer_id,
            COALESCE(NULLIF(btrim(r.currency_code_raw), ''), 'BYN') AS currency_code,
            %s AS instrument_type,
            r.term_days_raw
        FROM raw_market_archive r
        JOIN issuers i
          ON i.issuer_name = btrim(r.issuer_name_raw)
        WHERE r.file_id = %s
          AND r.ticker_raw IS NOT NULL
          AND btrim(r.ticker_raw) <> ''
        ON CONFLICT (ticker) DO UPDATE
        SET issuer_id = EXCLUDED.issuer_id,
            currency_code = EXCLUDED.currency_code,
            instrument_type = EXCLUDED.instrument_type,
            term_days = COALESCE(EXCLUDED.term_days, instruments.term_days)
        """,
        (instrument_type, file_id),
    )


def populate_trading_calendar(cur, file_id: int) -> None:
    cur.execute(
        """
        INSERT INTO trading_calendar (
            trade_date,
            year_num,
            month_num,
            quarter_num,
            week_num,
            is_trading_day
        )
        SELECT DISTINCT
            DATE(r.trade_datetime_raw) AS trade_date,
            EXTRACT(YEAR FROM DATE(r.trade_datetime_raw))::INTEGER AS year_num,
            EXTRACT(MONTH FROM DATE(r.trade_datetime_raw))::INTEGER AS month_num,
            EXTRACT(QUARTER FROM DATE(r.trade_datetime_raw))::INTEGER AS quarter_num,
            EXTRACT(WEEK FROM DATE(r.trade_datetime_raw))::INTEGER AS week_num,
            TRUE AS is_trading_day
        FROM raw_market_archive r
        WHERE r.file_id = %s
          AND r.trade_datetime_raw IS NOT NULL
        ON CONFLICT (trade_date) DO NOTHING
        """,
        (file_id,),
    )


def populate_market_daily_stats(cur, file_id: int, default_market_segment: str) -> None:
    cur.execute(
        """
        WITH grouped AS (
            SELECT
                ins.instrument_id,
                DATE(r.trade_datetime_raw) AS trade_date,
                MIN(r.price_min_raw) AS price_min,
                CASE
                    WHEN SUM(
                        CASE
                            WHEN r.price_avg_raw IS NOT NULL
                             AND COALESCE(r.turnover_qty_raw, 0) > 0
                            THEN r.turnover_qty_raw
                            ELSE 0
                        END
                    ) > 0
                    THEN SUM(r.price_avg_raw * r.turnover_qty_raw)
                         / SUM(
                            CASE
                                WHEN r.price_avg_raw IS NOT NULL
                                 AND COALESCE(r.turnover_qty_raw, 0) > 0
                                THEN r.turnover_qty_raw
                                ELSE 0
                            END
                         )
                    ELSE AVG(r.price_avg_raw)
                END AS price_avg_weighted,
                AVG(r.price_aux_raw) AS price_aux,
                MIN(r.yield_min_raw) AS yield_min_pct,
                MAX(r.yield_max_raw) AS yield_max_pct,
                CASE
                    WHEN SUM(
                        CASE
                            WHEN r.yield_avg_raw IS NOT NULL
                             AND COALESCE(r.turnover_qty_raw, 0) > 0
                            THEN r.turnover_qty_raw
                            ELSE 0
                        END
                    ) > 0
                    THEN SUM(r.yield_avg_raw * r.turnover_qty_raw)
                         / SUM(
                            CASE
                                WHEN r.yield_avg_raw IS NOT NULL
                                 AND COALESCE(r.turnover_qty_raw, 0) > 0
                                THEN r.turnover_qty_raw
                                ELSE 0
                            END
                         )
                    ELSE AVG(r.yield_avg_raw)
                END AS yield_avg_pct,
                SUM(COALESCE(r.turnover_value_raw, 0)) AS turnover_value,
                SUM(COALESCE(r.turnover_qty_raw, 0)) AS turnover_qty,
                SUM(COALESCE(r.deals_count_raw, 0))::INTEGER AS deals_count,
                MAX(r.term_days_raw) AS term_days,
                COALESCE(
                    MAX(NULLIF(btrim(r.market_segment_raw), '')),
                    %s
                ) AS market_segment,
                %s::BIGINT AS file_id
            FROM raw_market_archive r
            JOIN issuers iss
              ON iss.issuer_name = btrim(r.issuer_name_raw)
            JOIN instruments ins
              ON ins.ticker = btrim(r.ticker_raw)
             AND ins.issuer_id = iss.issuer_id
            WHERE r.file_id = %s
              AND r.trade_datetime_raw IS NOT NULL
              AND r.ticker_raw IS NOT NULL
              AND btrim(r.ticker_raw) <> ''
            GROUP BY
                ins.instrument_id,
                DATE(r.trade_datetime_raw)
        )
        INSERT INTO market_daily_stats (
            instrument_id,
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
            file_id
        )
        SELECT
            instrument_id,
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
            file_id
        FROM grouped
        ON CONFLICT (instrument_id, trade_date) DO UPDATE
        SET price_min = EXCLUDED.price_min,
            price_avg_weighted = EXCLUDED.price_avg_weighted,
            price_aux = EXCLUDED.price_aux,
            yield_min_pct = EXCLUDED.yield_min_pct,
            yield_max_pct = EXCLUDED.yield_max_pct,
            yield_avg_pct = EXCLUDED.yield_avg_pct,
            turnover_value = EXCLUDED.turnover_value,
            turnover_qty = EXCLUDED.turnover_qty,
            deals_count = EXCLUDED.deals_count,
            term_days = EXCLUDED.term_days,
            market_segment = EXCLUDED.market_segment,
            file_id = EXCLUDED.file_id,
            created_at = CURRENT_TIMESTAMP
        """,
        (default_market_segment, file_id, file_id),
    )


def refresh_materialized_view_if_exists(cur) -> bool:
    cur.execute("SELECT to_regclass('public.mv_instrument_summary')")
    exists = cur.fetchone()[0]
    if exists is None:
        return False

    cur.execute("REFRESH MATERIALIZED VIEW public.mv_instrument_summary")
    return True


def process_archive(conn, file_path: Path, args: argparse.Namespace) -> tuple[int, int]:
    df = load_archive_dataframe(
        file_path,
        sheet_name=args.sheet_name,
        market_segment=args.market_segment,
    )
    rows_count = len(df)

    with conn:
        with conn.cursor() as cur:
            if args.replace_existing:
                delete_existing_imports(cur, file_path.name)
            else:
                existing_file_id = get_existing_import_id(cur, file_path.name)
                if existing_file_id is not None:
                    print(f"[SKIP] {file_path.name}: уже загружен как file_id={existing_file_id}")
                    return 0, 0

            file_id = insert_import_file(
                cur,
                file_name=file_path.name,
                source_type=args.source_type,
                rows_count=rows_count,
                notes="Loaded from ETL script load_archives_to_postgres.py",
            )

            raw_rows = dataframe_to_raw_tuples(df, file_id)
            bulk_insert_raw(cur, raw_rows)
            populate_issuers(cur, file_id)
            populate_instruments(cur, file_id)
            populate_trading_calendar(cur, file_id)
            populate_market_daily_stats(cur, file_id, args.market_segment)

            print(f"[OK] {file_path.name}: file_id={file_id}, raw_rows={rows_count}")
            return 1, rows_count


def main() -> None:
    args = parse_args()
    input_dir = Path(args.input_dir)

    if not input_dir.exists() or not input_dir.is_dir():
        raise FileNotFoundError(f"Папка не найдена: {input_dir}")

    files = sorted(input_dir.glob("*.xlsx"))
    if not files:
        raise FileNotFoundError(f"В папке {input_dir} не найдено xlsx-файлов")

    loaded_files = 0
    loaded_rows = 0

    conn = connect_db(args)
    try:
        for file_path in files:
            file_loaded, row_count = process_archive(conn, file_path, args)
            loaded_files += file_loaded
            loaded_rows += row_count

        if args.refresh_materialized_view:
            with conn:
                with conn.cursor() as cur:
                    refreshed = refresh_materialized_view_if_exists(cur)
                    if refreshed:
                        print("[OK] mv_instrument_summary обновлена")
                    else:
                        print("[INFO] mv_instrument_summary ещё не создана, обновление пропущено")

    finally:
        conn.close()

    print("=" * 60)
    print(f"Загружено файлов: {loaded_files}")
    print(f"Загружено raw-строк: {loaded_rows}")


if __name__ == "__main__":
    main()

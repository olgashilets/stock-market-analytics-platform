from __future__ import annotations

import pandas as pd
import psycopg2
from psycopg2.extras import RealDictCursor

from app.db_config import DB_CONFIG


def fetch_df(query: str, params: dict | None = None) -> pd.DataFrame:
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(query, params or {})
            rows = cur.fetchall()
            return pd.DataFrame(rows)


def fetch_one(query: str, params: dict | None = None) -> dict:
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(query, params or {})
            row = cur.fetchone()
            return dict(row) if row else {}
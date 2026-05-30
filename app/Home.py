from __future__ import annotations

from pathlib import Path

import streamlit as st

from app.db import fetch_one
from app.queries import HOME_SUMMARY_QUERY


APP_DIR = Path(__file__).resolve().parent
PAGES_DIR = APP_DIR / "pages"


def format_date(value) -> str:
    if value is None:
        return "—"
    if hasattr(value, "strftime"):
        return value.strftime("%Y-%m-%d")
    return str(value)


def render_home() -> None:
    st.title("Анализ акций белорусских компаний")

    summary = fetch_one(HOME_SUMMARY_QUERY)

    st.subheader("Состояние базы данных")

    col1, col2, col3 = st.columns(3)
    col1.metric("Инструментов", summary.get("instruments_count", 0))
    col2.metric("Строк в market_daily_stats", summary.get("market_daily_stats_rows", 0))
    col3.metric("Суммарный оборот", f"{summary.get('total_turnover_value', 0):,.2f}")

    period_value = f"{format_date(summary.get('min_trade_date'))} — {format_date(summary.get('max_trade_date'))}"
    period_col, _ = st.columns([2, 3])
    period_col.metric("Период", period_value)

    st.success(
        f"Подключение к базе данных установлено. Текущая база: {summary.get('database_name')}"
    )

    st.markdown(
        """
Белорусский фондовый рынок остаётся сравнительно компактным, поэтому для инвестора особенно важны прозрачная история торгов, ликвидность бумаг и своевременное выявление необычных движений цены и оборота.

Это приложение помогает быстро оценить доступные инструменты, сравнить их между собой и заметить аномальные события на основе данных из базы, чтобы использовать сервис как практический инструмент для первичного анализа рынка.
"""
    )


st.set_page_config(
    page_title="Анализ акций белорусских компаний",
    page_icon="📈",
    layout="wide",
)

navigation = st.navigation(
    [
        st.Page(render_home, title="Главная", icon="🏠", default=True),
        st.Page(str(PAGES_DIR / "1_market_overview.py"), title="Обзор рынка", icon="📊"),
        st.Page(str(PAGES_DIR / "2_instrument_card.py"), title="Карточка инструмента", icon="📄"),
        st.Page(str(PAGES_DIR / "3_instruments_comparison.py"), title="Сравнение инструментов", icon="📈"),
        st.Page(str(PAGES_DIR / "4_market_anomalies.py"), title="Аномалии рынка", icon="⚠️"),
    ]
)

navigation.run()

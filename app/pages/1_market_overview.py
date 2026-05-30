from __future__ import annotations

import math

import streamlit as st

from app.db import fetch_df, fetch_one
from app.queries import SCREENER_DEFAULT_DATES_QUERY, SCREEN_REQUERY

st.title("Обзор рынка")

st.markdown(
    """
    <style>
    div[data-testid="stMetricValue"] {
        font-size: 1.1rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

default_dates = fetch_one(SCREENER_DEFAULT_DATES_QUERY)

min_trade_date = default_dates.get("min_trade_date")
max_trade_date = default_dates.get("max_trade_date")

if not min_trade_date or not max_trade_date:
    st.error("В trading_calendar нет данных. Сначала проверь загрузку ETL.")
    st.stop()

with st.sidebar:
    st.header("Фильтры")

    date_from = st.date_input(
        "Дата начала периода",
        value=min_trade_date,
        min_value=min_trade_date,
        max_value=max_trade_date
    )

    date_to = st.date_input(
        "Дата конца периода",
        value=max_trade_date,
        min_value=min_trade_date,
        max_value=max_trade_date
    )

    min_return_pct = st.number_input(
        "Минимальная доходность, %",
        value=0.0,
        step=1.0
    )

    max_volatility_pct = st.number_input(
        "Максимальная волатильность, %",
        value=1000.0,
        step=1.0
    )

    min_avg_turnover_value = st.number_input(
        "Минимальный средний оборот",
        value=0.0,
        step=1000.0
    )

    min_avg_deals_count = st.number_input(
        "Минимальное среднее число сделок",
        value=0.0,
        step=1.0
    )

    min_active_days_share_pct = st.number_input(
        "Минимальная доля активных дней, %",
        value=0.0,
        step=1.0
    )

    max_abs_drawdown_pct = st.number_input(
        "Максимально допустимая просадка, %",
        value=100.0,
        step=1.0
    )

    run_query = st.button("Применить фильтры", use_container_width=True)

if date_from > date_to:
    st.error("Дата начала периода не может быть больше даты конца периода.")
    st.stop()

params = {
    "date_from": date_from,
    "date_to": date_to,
    "min_return_pct": min_return_pct,
    "max_volatility_pct": max_volatility_pct,
    "min_avg_turnover_value": min_avg_turnover_value,
    "min_avg_deals_count": min_avg_deals_count,
    "min_active_days_share_pct": min_active_days_share_pct,
    "max_abs_drawdown_pct": max_abs_drawdown_pct,
}

if run_query or True:
    df = fetch_df(SCREEN_REQUERY, params)

    st.subheader("Результаты скрининга")

    mean_return = 0.0
    if not df.empty and "return_pct_period" in df.columns:
        mean_value = df["return_pct_period"].mean()
        if mean_value is not None and not math.isnan(float(mean_value)):
            mean_return = float(mean_value)

    col1, col2, col3 = st.columns([1, 2.4, 1.2])
    col1.metric("Найдено инструментов", len(df))
    col2.metric("Период", f"{date_from:%Y-%m-%d} — {date_to:%Y-%m-%d}")
    col3.metric("Среднее по результатам", f"{mean_return:.2f} %")

    if df.empty:
        st.warning("По заданным фильтрам инструменты не найдены.")
    else:
        st.dataframe(
            df,
            use_container_width=True,
            hide_index=True,
            column_config={
                "ticker": st.column_config.TextColumn("Тикер"),
                "issuer_name": st.column_config.TextColumn("Эмитент"),
                "last_price": st.column_config.NumberColumn("Последняя цена", format="%.4f"),
                "return_pct_period": st.column_config.NumberColumn("Доходность, %", format="%.2f"),
                "avg_turnover_value": st.column_config.NumberColumn("Средний оборот", format="%.2f"),
                "avg_deals_count": st.column_config.NumberColumn("Среднее число сделок", format="%.2f"),
                "active_days_count": st.column_config.NumberColumn("Активных дней", format="%d"),
                "period_trading_days": st.column_config.NumberColumn("Торговых дней в периоде", format="%d"),
                "active_days_share_pct": st.column_config.NumberColumn("Доля активных дней, %", format="%.2f"),
                "volatility_pct": st.column_config.NumberColumn("Волатильность, %", format="%.2f"),
                "max_drawdown_pct": st.column_config.NumberColumn("Макс. просадка, %", format="%.2f"),
                "last_active_trade_date": st.column_config.DateColumn("Дата последней сделки"),
            }
        )

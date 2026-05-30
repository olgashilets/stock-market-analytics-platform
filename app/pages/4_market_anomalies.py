from __future__ import annotations

import pandas as pd
import streamlit as st

from app.db import fetch_df, fetch_one
from app.queries import (
    ANOMALIES_PAGE_QUERY,
    SCREENER_DEFAULT_DATES_QUERY,
    TICKER_OPTIONS_QUERY,
)


ANOMALY_LABELS = {
    "price_jump": "Скачок цены",
    "turnover_spike": "Всплеск оборота",
    "deals_spike": "Всплеск числа сделок",
}


st.title("Аномалии рынка")

ticker_df = fetch_df(TICKER_OPTIONS_QUERY)
default_dates = fetch_one(SCREENER_DEFAULT_DATES_QUERY)

min_trade_date = default_dates.get("min_trade_date")
max_trade_date = default_dates.get("max_trade_date")

if not min_trade_date or not max_trade_date:
    st.error("В trading_calendar нет данных. Проверь загрузку ETL.")
    st.stop()

ticker_options = ["Все"] + ticker_df["ticker"].tolist()
anomaly_type_options = list(ANOMALY_LABELS.keys())

with st.sidebar:
    st.header("Фильтры")

    date_from = st.date_input(
        "Дата начала периода",
        value=min_trade_date,
        min_value=min_trade_date,
        max_value=max_trade_date,
        key="anomaly_date_from",
    )

    date_to = st.date_input(
        "Дата конца периода",
        value=max_trade_date,
        min_value=min_trade_date,
        max_value=max_trade_date,
        key="anomaly_date_to",
    )

    selected_ticker = st.selectbox(
        "Тикер",
        options=ticker_options,
        index=0,
    )

    selected_anomaly_types = st.multiselect(
        "Типы аномалий",
        options=anomaly_type_options,
        default=anomaly_type_options,
        format_func=lambda x: ANOMALY_LABELS.get(x, x),
    )

    min_abs_anomaly_pct = st.number_input(
        "Минимальное абсолютное отклонение, %",
        value=0.0,
        step=1.0,
    )

if date_from > date_to:
    st.error("Дата начала периода не может быть больше даты конца периода.")
    st.stop()

if not selected_anomaly_types:
    st.warning("Выбери хотя бы один тип аномалии.")
    st.stop()

params = {
    "date_from": date_from,
    "date_to": date_to,
    "ticker": None if selected_ticker == "Все" else selected_ticker,
    "anomaly_types": selected_anomaly_types,
    "min_abs_anomaly_pct": min_abs_anomaly_pct,
}

df = fetch_df(ANOMALIES_PAGE_QUERY, params)

st.subheader("Список аномалий")

col1, col2, col3 = st.columns(3)
col1.metric("Найдено аномалий", len(df))
col2.metric("Уникальных инструментов", df["ticker"].nunique() if not df.empty else 0)
col3.metric(
    "Макс. отклонение, %",
    f"{df['anomaly_value_pct'].abs().max():.2f}" if not df.empty else "0.00"
)

if df.empty:
    st.info("За выбранный период аномалии не найдены.")
    st.stop()

display_df = df.copy()
display_df["anomaly_type"] = display_df["anomaly_type"].map(ANOMALY_LABELS).fillna(display_df["anomaly_type"])

st.dataframe(
    display_df,
    use_container_width=True,
    hide_index=True,
    column_config={
        "trade_date": st.column_config.DateColumn("Дата"),
        "ticker": st.column_config.TextColumn("Тикер"),
        "issuer_name": st.column_config.TextColumn("Эмитент"),
        "anomaly_type": st.column_config.TextColumn("Тип аномалии"),
        "anomaly_value_pct": st.column_config.NumberColumn("Отклонение, %", format="%.2f"),
        "price_avg_weighted": st.column_config.NumberColumn("Цена", format="%.4f"),
        "turnover_value": st.column_config.NumberColumn("Оборот", format="%.2f"),
        "deals_count": st.column_config.NumberColumn("Число сделок", format="%d"),
    },
)

st.subheader("Распределение аномалий по типам")
type_counts = (
    display_df.groupby("anomaly_type", as_index=False)
    .size()
    .rename(columns={"size": "count"})
    .set_index("anomaly_type")
)

st.bar_chart(type_counts)

st.subheader("Инструменты с наибольшим числом аномалий")
ticker_counts = (
    display_df.groupby("ticker", as_index=False)
    .size()
    .rename(columns={"size": "count"})
    .sort_values(["count", "ticker"], ascending=[False, True])
    .head(10)
    .set_index("ticker")
)

st.bar_chart(ticker_counts)

with st.expander("Показать данные аномалий"):
    st.dataframe(display_df, use_container_width=True, hide_index=True)

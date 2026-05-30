from __future__ import annotations

import streamlit as st

from app.db import fetch_df, fetch_one
from app.queries import (
    CARD_ACTIVITY_HISTORY_QUERY,
    CARD_ANOMALIES_QUERY,
    CARD_KPI_QUERY,
    CARD_STATUS_QUERY,
    CARD_TICKER_DATE_BOUNDS_QUERY,
    CARD_PRICE_HISTORY_QUERY,
    TICKER_OPTIONS_QUERY,
)


def format_date(value) -> str:
    if value is None:
        return "—"
    if hasattr(value, "strftime"):
        return value.strftime("%Y-%m-%d")
    return str(value)


def format_number(value, decimals: int = 2, suffix: str = "") -> str:
    if value is None:
        return "—"
    try:
        return f"{float(value):,.{decimals}f}{suffix}"
    except (TypeError, ValueError):
        return str(value)


st.title("Карточка инструмента")

ticker_df = fetch_df(TICKER_OPTIONS_QUERY)

if ticker_df.empty:
    st.error("Справочник instruments пуст. Проверь загрузку ETL.")
    st.stop()

ticker_options = ticker_df["ticker"].tolist()

with st.sidebar:
    st.header("Параметры")
    selected_ticker = st.selectbox("Инструмент", ticker_options)

date_bounds = fetch_one(CARD_TICKER_DATE_BOUNDS_QUERY, {"ticker": selected_ticker})

min_trade_date = date_bounds.get("min_trade_date")
max_trade_date = date_bounds.get("max_trade_date")

if not min_trade_date or not max_trade_date:
    st.error("Для выбранного инструмента нет данных.")
    st.stop()

with st.sidebar:
    date_from = st.date_input(
        "Дата начала периода",
        value=min_trade_date,
        min_value=min_trade_date,
        max_value=max_trade_date,
        key="card_date_from",
    )

    date_to = st.date_input(
        "Дата конца периода",
        value=max_trade_date,
        min_value=min_trade_date,
        max_value=max_trade_date,
        key="card_date_to",
    )

if date_from > date_to:
    st.error("Дата начала периода не может быть больше даты конца периода.")
    st.stop()

params = {
    "ticker": selected_ticker,
    "date_from": date_from,
    "date_to": date_to,
}

kpi = fetch_one(CARD_KPI_QUERY, params)
status = fetch_one(CARD_STATUS_QUERY, {"ticker": selected_ticker})
price_history = fetch_df(CARD_PRICE_HISTORY_QUERY, params)
activity_history = fetch_df(CARD_ACTIVITY_HISTORY_QUERY, params)
anomalies = fetch_df(CARD_ANOMALIES_QUERY, params)

if not kpi or kpi.get("last_price") is None:
    st.warning("За выбранный период по инструменту нет данных.")
    st.stop()

st.subheader(f"{kpi.get('ticker')} — {kpi.get('issuer_name')}")
st.caption(
    f"Валюта: {kpi.get('currency_code')} | "
    f"Тип инструмента: {kpi.get('instrument_type')} | "
    f"Последняя дата сделки: {format_date(kpi.get('last_trade_date'))}"
)

col_status_1, col_status_2 = st.columns(2)
col_status_1.info(status.get("liquidity_status", "Статус ликвидности не определён"))
col_status_2.info(status.get("risk_status", "Статус риска не определён"))

st.subheader("KPI по выбранному периоду")

col1, col2, col3 = st.columns(3)
col1.metric("Последняя цена", format_number(kpi.get("last_price"), 4))
col2.metric("Изменение за день, %", format_number(kpi.get("change_day_pct"), 2))
col3.metric("Изменение за 30 дней, %", format_number(kpi.get("change_30d_pct"), 2))

col4, col5, col6 = st.columns(3)
col4.metric("Изменение за 90 дней, %", format_number(kpi.get("change_90d_pct"), 2))
col5.metric("Волатильность, %", format_number(kpi.get("volatility_pct"), 2))
col6.metric("Максимальная просадка, %", format_number(kpi.get("max_drawdown_pct"), 2))

col7, col8, col9 = st.columns(3)
col7.metric("Средний оборот", format_number(kpi.get("avg_turnover_value"), 2))
col8.metric("Среднее число сделок", format_number(kpi.get("avg_deals_count"), 2))
col9.metric("Доля активных дней, %", format_number(kpi.get("active_days_share_pct"), 2))

st.subheader("Динамика цены")
if price_history.empty:
    st.warning("Нет данных для графика цены.")
else:
    price_chart_df = price_history.copy()
    price_chart_df["trade_date"] = price_chart_df["trade_date"].astype(str)
    st.line_chart(price_chart_df.set_index("trade_date")[["price_avg_weighted"]], height=350)

st.subheader("Торговая активность")

col_chart_1, col_chart_2 = st.columns(2)

with col_chart_1:
    st.markdown("**Оборот**")
    if activity_history.empty:
        st.warning("Нет данных по обороту.")
    else:
        turnover_chart_df = activity_history.copy()
        turnover_chart_df["trade_date"] = turnover_chart_df["trade_date"].astype(str)
        st.line_chart(turnover_chart_df.set_index("trade_date")[["turnover_value"]], height=300)

with col_chart_2:
    st.markdown("**Число сделок**")
    if activity_history.empty:
        st.warning("Нет данных по числу сделок.")
    else:
        deals_chart_df = activity_history.copy()
        deals_chart_df["trade_date"] = deals_chart_df["trade_date"].astype(str)
        st.line_chart(deals_chart_df.set_index("trade_date")[["deals_count"]], height=300)

st.subheader("Последние аномальные дни")

if anomalies.empty:
    st.info("Аномалии за выбранный период не найдены.")
else:
    st.dataframe(
        anomalies,
        use_container_width=True,
        hide_index=True,
        column_config={
            "trade_date": st.column_config.DateColumn("Дата"),
            "anomaly_type": st.column_config.TextColumn("Тип аномалии"),
            "anomaly_value_pct": st.column_config.NumberColumn("Отклонение, %", format="%.2f"),
            "price_avg_weighted": st.column_config.NumberColumn("Цена", format="%.4f"),
            "turnover_value": st.column_config.NumberColumn("Оборот", format="%.2f"),
            "deals_count": st.column_config.NumberColumn("Число сделок", format="%d"),
        },
    )

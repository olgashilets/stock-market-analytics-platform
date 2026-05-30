from __future__ import annotations

import pandas as pd
import streamlit as st

from app.db import fetch_df, fetch_one
from app.queries import (
    COMPARISON_HISTORY_QUERY,
    COMPARISON_SUMMARY_QUERY,
    SCREENER_DEFAULT_DATES_QUERY,
    TICKER_OPTIONS_QUERY,
)


def prepare_normalized_chart(history_df: pd.DataFrame) -> pd.DataFrame:
    if history_df.empty:
        return pd.DataFrame()

    chart_df = history_df[["trade_date", "ticker", "price_avg_weighted"]].copy()
    chart_df["trade_date"] = pd.to_datetime(chart_df["trade_date"], errors="coerce")
    chart_df["price_avg_weighted"] = pd.to_numeric(chart_df["price_avg_weighted"], errors="coerce")

    chart_df = chart_df.dropna(subset=["trade_date", "ticker", "price_avg_weighted"])

    if chart_df.empty:
        return pd.DataFrame()

    pivot_df = (
        chart_df
        .pivot_table(
            index="trade_date",
            columns="ticker",
            values="price_avg_weighted",
            aggfunc="mean"
        )
        .sort_index()
    )

    if pivot_df.empty:
        return pd.DataFrame()

    # Для графика сравнения протягиваем последнюю известную цену вперёд.
    # Это влияет только на визуализацию, а не на расчёт метрик.
    filled_df = pivot_df.ffill()

    normalized_df = pd.DataFrame(index=filled_df.index)

    for column in filled_df.columns:
        series = pd.to_numeric(filled_df[column], errors="coerce")
        first_valid = series.dropna()

        if first_valid.empty:
            normalized_df[column] = pd.NA
            continue

        base_value = first_valid.iloc[0]

        if pd.isna(base_value) or base_value == 0:
            normalized_df[column] = pd.NA
            continue

        normalized_df[column] = (series / base_value) * 100

    normalized_df = normalized_df.dropna(how="all")

    for col in normalized_df.columns:
        normalized_df[col] = pd.to_numeric(normalized_df[col], errors="coerce")

    return normalized_df

def prepare_correlation_matrix(history_df: pd.DataFrame) -> pd.DataFrame:
    if history_df.empty:
        return pd.DataFrame()

    corr_df = history_df[["trade_date", "ticker", "daily_return_pct"]].copy()
    corr_df["trade_date"] = pd.to_datetime(corr_df["trade_date"], errors="coerce")
    corr_df["daily_return_pct"] = pd.to_numeric(corr_df["daily_return_pct"], errors="coerce")

    corr_df = corr_df.dropna(subset=["trade_date", "ticker"])

    if corr_df.empty:
        return pd.DataFrame()

    pivot_df = (
        corr_df
        .pivot_table(
            index="trade_date",
            columns="ticker",
            values="daily_return_pct",
            aggfunc="mean"
        )
        .sort_index()
    )

    if pivot_df.shape[1] < 2:
        return pd.DataFrame()

    return pivot_df.corr().round(3)


st.title("Сравнение инструментов")

ticker_df = fetch_df(TICKER_OPTIONS_QUERY)
default_dates = fetch_one(SCREENER_DEFAULT_DATES_QUERY)

if ticker_df.empty:
    st.error("Справочник instruments пуст. Проверь загрузку ETL.")
    st.stop()

min_trade_date = default_dates.get("min_trade_date")
max_trade_date = default_dates.get("max_trade_date")

if not min_trade_date or not max_trade_date:
    st.error("В trading_calendar нет данных. Проверь загрузку ETL.")
    st.stop()

ticker_options = ticker_df["ticker"].tolist()

with st.sidebar:
    st.header("Параметры")

    default_selection = ticker_options[:2] if len(ticker_options) >= 2 else ticker_options

    selected_tickers = st.multiselect(
        "Выбери 2–5 инструментов",
        options=ticker_options,
        default=default_selection,
        max_selections=5,
    )

    date_from = st.date_input(
        "Дата начала периода",
        value=min_trade_date,
        min_value=min_trade_date,
        max_value=max_trade_date,
        key="comparison_date_from",
    )

    date_to = st.date_input(
        "Дата конца периода",
        value=max_trade_date,
        min_value=min_trade_date,
        max_value=max_trade_date,
        key="comparison_date_to",
    )

if len(selected_tickers) < 2:
    st.warning("Для сравнения нужно выбрать минимум 2 инструмента.")
    st.stop()

if date_from > date_to:
    st.error("Дата начала периода не может быть больше даты конца периода.")
    st.stop()

params = {
    "tickers": selected_tickers,
    "date_from": date_from,
    "date_to": date_to,
}

summary_df = fetch_df(COMPARISON_SUMMARY_QUERY, params)
history_df = fetch_df(COMPARISON_HISTORY_QUERY, params)

if summary_df.empty or history_df.empty:
    st.warning("За выбранный период по выбранным инструментам нет данных.")
    st.stop()

st.subheader("Нормированная динамика цены")
normalized_df = prepare_normalized_chart(history_df)

if normalized_df.empty:
    st.warning("Недостаточно данных для графика.")
else:
    chart_df = normalized_df.copy()

    for col in chart_df.columns:
        chart_df[col] = pd.to_numeric(chart_df[col], errors="coerce")

    chart_df = chart_df.dropna(how="all")

    if chart_df.empty:
        st.warning("После нормализации не осталось числовых данных для построения графика.")
    else:
        st.line_chart(chart_df, height=380)
        with st.expander("Показать данные графика"):
            st.dataframe(chart_df, use_container_width=True)

st.subheader("Сравнительная таблица")

display_df = summary_df.copy()
numeric_columns = [
    "first_price",
    "last_price",
    "return_pct_period",
    "avg_turnover_value",
    "avg_deals_count",
    "active_days_share_pct",
    "volatility_pct",
    "max_drawdown_pct",
]

for col in numeric_columns:
    if col in display_df.columns:
        display_df[col] = pd.to_numeric(display_df[col], errors="coerce")

st.dataframe(
    display_df,
    use_container_width=True,
    hide_index=True,
    column_config={
        "ticker": st.column_config.TextColumn("Тикер"),
        "issuer_name": st.column_config.TextColumn("Эмитент"),
        "first_price": st.column_config.NumberColumn("Первая цена", format="%.4f"),
        "last_price": st.column_config.NumberColumn("Последняя цена", format="%.4f"),
        "return_pct_period": st.column_config.NumberColumn("Доходность, %", format="%.2f"),
        "avg_turnover_value": st.column_config.NumberColumn("Средний оборот", format="%.2f"),
        "avg_deals_count": st.column_config.NumberColumn("Среднее число сделок", format="%.2f"),
        "active_days_count": st.column_config.NumberColumn("Активных дней", format="%d"),
        "period_trading_days": st.column_config.NumberColumn("Торговых дней в периоде", format="%d"),
        "active_days_share_pct": st.column_config.NumberColumn("Доля активных дней, %", format="%.2f"),
        "volatility_pct": st.column_config.NumberColumn("Волатильность, %", format="%.2f"),
        "max_drawdown_pct": st.column_config.NumberColumn("Макс. просадка, %", format="%.2f"),
    },
)

st.subheader("Компактная корреляционная матрица")
corr_df = prepare_correlation_matrix(history_df)

if corr_df.empty:
    st.info("Недостаточно данных для расчёта корреляции.")
else:
    st.dataframe(corr_df, use_container_width=True)

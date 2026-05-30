# Аналитическая платформа фондового рынка

[English version](README.md)

## Обзор

Проект представляет собой аналитическую платформу на PostgreSQL и Streamlit для данных по акциям белорусских компаний. Он демонстрирует проектирование базы данных, ETL, SQL-аналитику, проверки качества данных и разработку аналитического интерфейса.

Проект подготовлен как портфолио для позиций BI Analyst, Data Analyst и FinTech Data Analyst.

## Бизнес-задача

Аналитику нужен надёжный способ загружать, очищать и анализировать архивы торгов. Система должна сохранять исходные строки, строить нормализованные таблицы и предоставлять аналитические витрины для скрининга, сравнения инструментов и поиска аномалий.

## Что показывает проект

- проектирование реляционной базы данных;
- raw-слой и нормализованный слой;
- транзакционная ETL-загрузка Excel-архивов;
- SQL-представления и материализованная витрина;
- проверки качества данных;
- Streamlit-дашборд;
- скрининг рынка, карточка инструмента, сравнение и поиск аномалий.

## Архитектура

```text
Excel source data → generator demo archives → ETL → PostgreSQL raw layer
                                               → PostgreSQL normalized layer
                                               → SQL views / materialized view
                                               → Streamlit dashboard
```

Подробнее: [`docs/architecture.md`](docs/architecture.md) и [`docs/data_model.md`](docs/data_model.md).

## Структура

```text
stock-market-analytics-platform/
├── app/                         # Streamlit и слой SQL-запросов
├── data/
│   ├── source/                  # исходный файл с данными
│   └── generated_archives/      # сгенерированные демо-архивы
├── db/
│   ├── schema.sql               # таблицы, ограничения, индексы
│   ├── analytics_objects.sql    # представления и материализованная витрина
│   └── testing_checks.sql       # проверки качества и производительности
├── etl/
│   ├── generate_demo_archives.py
│   └── load_archives_to_postgres.py
├── docs/
├── docker-compose.yml
├── requirements.txt
├── .env.example
├── README.md
└── README.ru.md
```

## Быстрый запуск

### 1. Установить зависимости

```bash
pip install -r requirements.txt
```

### 2. Запустить PostgreSQL

Через Docker:

```bash
docker compose up -d
```

Или использовать локальный PostgreSQL, указав переменные окружения по примеру `.env.example`.

### 3. Создать объекты базы данных

```bash
psql -h localhost -U postgres -d investment_sbd -f db/schema.sql
psql -h localhost -U postgres -d investment_sbd -f db/analytics_objects.sql
```

### 4. Сгенерировать demo-архивы

```bash
python etl/generate_demo_archives.py \
  --input data/source/data.xlsx \
  --output data/generated_archives
```

### 5. Загрузить архивы в PostgreSQL

```bash
python etl/load_archives_to_postgres.py \
  --input-dir data/generated_archives \
  --replace-existing \
  --refresh-materialized-view
```

### 6. Выполнить проверки качества

```bash
psql -h localhost -U postgres -d investment_sbd -f db/testing_checks.sql
```

### 7. Запустить Streamlit

```bash
streamlit run app/Home.py
```

## Пользовательские сценарии

1. **Обзор рынка** — фильтр инструментов по доходности, риску, ликвидности и просадке.
2. **Карточка инструмента** — KPI, история цены, торговая активность и последние аномалии.
3. **Сравнение инструментов** — нормированная динамика цен и сравнительные метрики.
4. **Аномалии рынка** — скачки цены, всплески оборота и всплески числа сделок.

## Примечание по данным

Сгенерированные архивы являются демонстрационными файлами на основе месячных исходных данных. Они используются для проверки ETL, структуры БД и сценариев интерфейса. Не является инвестиционной рекомендацией.

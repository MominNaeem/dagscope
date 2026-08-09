from datetime import datetime, timedelta

from airflow import DAG
from airflow.providers.postgres.operators.postgres import PostgresOperator

default_args = {
    "owner": "data-platform",
    "retries": 1,
    "retry_delay": timedelta(minutes=2),
}

with DAG(
    dag_id="fx_rates_ingest",
    description="Ingest FX rates from vendor feed into raw.fx_rates",
    default_args=default_args,
    start_date=datetime(2024, 1, 1),
    schedule_interval="0 17 * * 1-5",
    catchup=False,
    tags=["ingestion", "fx"],
) as dag:

    load_fx_rates = PostgresOperator(
        task_id="load_fx_rates",
        postgres_conn_id="postgres_default",
        sql="""
            INSERT INTO raw.fx_rates (rate_date, from_currency, to_currency, rate)
            SELECT
                src.rate_date,
                src.from_currency,
                src.to_currency,
                src.rate
            FROM staging.fx_rates_staging src
            ON CONFLICT (rate_date, from_currency, to_currency) DO UPDATE
                SET rate       = EXCLUDED.rate,
                    updated_at = NOW()
        """,
    )

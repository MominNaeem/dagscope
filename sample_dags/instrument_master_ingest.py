from datetime import datetime, timedelta

from airflow import DAG
from airflow.providers.postgres.operators.postgres import PostgresOperator

default_args = {
    "owner": "data-platform",
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}

with DAG(
    dag_id="instrument_master_ingest",
    description="Sync instrument master data from Bloomberg into raw.instrument_master",
    default_args=default_args,
    start_date=datetime(2024, 1, 1),
    schedule_interval="0 8 * * 1-5",
    catchup=False,
    tags=["ingestion", "reference-data"],
) as dag:

    load_instrument_master = PostgresOperator(
        task_id="load_instrument_master",
        postgres_conn_id="postgres_default",
        sql="""
            INSERT INTO raw.instrument_master (
                instrument_id, isin, ticker, sector, currency, asset_class
            )
            SELECT
                src.instrument_id,
                src.isin,
                src.ticker,
                src.sector,
                src.currency,
                src.asset_class
            FROM staging.instrument_master_staging src
            ON CONFLICT (instrument_id) DO UPDATE
                SET isin        = EXCLUDED.isin,
                    ticker      = EXCLUDED.ticker,
                    sector      = EXCLUDED.sector,
                    currency    = EXCLUDED.currency,
                    asset_class = EXCLUDED.asset_class,
                    updated_at  = NOW()
        """,
    )

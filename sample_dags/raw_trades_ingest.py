from datetime import datetime, timedelta

from airflow import DAG
from airflow.providers.postgres.operators.postgres import PostgresOperator

default_args = {
    "owner": "data-platform",
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
}

with DAG(
    dag_id="raw_trades_ingest",
    description="Ingest raw trade records from staging into raw.trades",
    default_args=default_args,
    start_date=datetime(2024, 1, 1),
    schedule_interval="0 18 * * 1-5",
    catchup=False,
    tags=["ingestion", "trades"],
) as dag:

    load_trades = PostgresOperator(
        task_id="load_trades",
        postgres_conn_id="postgres_default",
        sql="sql/load_trades.sql",
    )

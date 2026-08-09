from datetime import datetime, timedelta

from airflow import DAG
from airflow.providers.postgres.operators.postgres import PostgresOperator

default_args = {
    "owner": "data-platform",
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
}

with DAG(
    dag_id="positions_usd",
    description="Convert positions to USD using daily FX rates",
    default_args=default_args,
    start_date=datetime(2024, 1, 1),
    schedule_interval="0 19 * * 1-5",
    catchup=False,
    tags=["positions", "fx", "eod"],
) as dag:

    build_positions_usd = PostgresOperator(
        task_id="build_positions_usd",
        postgres_conn_id="postgres_default",
        sql="sql/build_positions_usd.sql",
    )

from datetime import datetime, timedelta

from airflow import DAG
from airflow.providers.postgres.operators.postgres import PostgresOperator

default_args = {
    "owner": "data-platform",
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
}

with DAG(
    dag_id="pnl_daily",
    description="Compute daily P&L from USD positions",
    default_args=default_args,
    start_date=datetime(2024, 1, 1),
    schedule_interval="30 19 * * 1-5",
    catchup=False,
    tags=["pnl", "eod"],
) as dag:

    build_pnl = PostgresOperator(
        task_id="build_pnl",
        postgres_conn_id="postgres_default",
        sql="sql/build_pnl_daily.sql",
    )

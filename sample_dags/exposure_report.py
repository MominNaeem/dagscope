from datetime import datetime, timedelta

from airflow import DAG
from airflow.providers.postgres.operators.postgres import PostgresOperator

default_args = {
    "owner": "data-platform",
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
}

with DAG(
    dag_id="exposure_report",
    description="Aggregate P&L by sector for the risk exposure report",
    default_args=default_args,
    start_date=datetime(2024, 1, 1),
    schedule_interval="0 20 * * 1-5",
    catchup=False,
    tags=["risk", "reporting", "eod"],
) as dag:

    generate_report = PostgresOperator(
        task_id="generate_report",
        postgres_conn_id="postgres_default",
        sql="sql/build_exposure_report.sql",
    )

from datetime import datetime, timedelta

from airflow import DAG
from airflow.providers.postgres.operators.postgres import PostgresOperator

default_args = {
    "owner": "data-platform",
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
}

with DAG(
    dag_id="positions_daily",
    description="Build end-of-day position snapshot from trades and instrument master",
    default_args=default_args,
    start_date=datetime(2024, 1, 1),
    schedule_interval="30 18 * * 1-5",
    catchup=False,
    tags=["positions", "eod"],
) as dag:

    clear_stale = PostgresOperator(
        task_id="clear_stale",
        postgres_conn_id="postgres_default",
        sql="""
            DELETE FROM public.positions_daily
            WHERE position_date = CURRENT_DATE
        """,
    )

    build_positions = PostgresOperator(
        task_id="build_positions",
        postgres_conn_id="postgres_default",
        sql="sql/build_positions_daily.sql",
    )

    clear_stale >> build_positions

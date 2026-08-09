from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.bash import BashOperator
from airflow.providers.postgres.operators.postgres import PostgresOperator

default_args = {
    "owner": "data-platform",
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}

with DAG(
    dag_id="risk_dashboard_export",
    description="Populate the risk dashboard table and trigger downstream export",
    default_args=default_args,
    start_date=datetime(2024, 1, 1),
    schedule_interval="30 20 * * 1-5",
    catchup=False,
    tags=["risk", "dashboard", "export"],
) as dag:

    build_risk_dashboard = PostgresOperator(
        task_id="build_risk_dashboard",
        postgres_conn_id="postgres_default",
        sql="sql/build_risk_dashboard.sql",
    )

    export_to_s3 = BashOperator(
        task_id="export_to_s3",
        bash_command="echo 'Exporting risk_dashboard_ext snapshot to s3://data-lake/risk/{{ ds }}'",
    )

    build_risk_dashboard >> export_to_s3

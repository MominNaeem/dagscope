from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.python import PythonOperator

default_args = {
    "owner": "data-platform",
    "retries": 1,
    "retry_delay": timedelta(minutes=10),
}


def compute_settlement_breaks(**context):
    """
    Compares expected settlement (from trades) against confirmed positions
    to surface breaks that need investigation.

    dagscope note: SQL inside a PythonOperator is extracted via regex
    and marked as low-confidence since the callable is opaque to static analysis.
    """
    from airflow.providers.postgres.hooks.postgres import PostgresHook

    hook = PostgresHook(postgres_conn_id="postgres_default")
    sql = """
        INSERT INTO public.settlement_breaks (
            break_date,
            instrument_id,
            break_amount,
            break_currency
        )
        SELECT
            t.settle_date                                             AS break_date,
            t.instrument_id,
            SUM(t.quantity) - COALESCE(SUM(p.quantity), 0)          AS break_amount,
            t.currency                                               AS break_currency
        FROM raw.trades t
        LEFT JOIN public.positions_daily p
            ON  t.instrument_id = p.instrument_id
            AND t.settle_date   = p.position_date + INTERVAL '1 day'
        GROUP BY t.settle_date, t.instrument_id, t.currency
        HAVING ABS(SUM(t.quantity) - COALESCE(SUM(p.quantity), 0)) > 0.01
        ON CONFLICT (break_date, instrument_id) DO UPDATE
            SET break_amount   = EXCLUDED.break_amount,
                updated_at     = NOW()
    """
    hook.run(sql)


with DAG(
    dag_id="settlement_breaks",
    description="Detect settlement breaks between expected and confirmed positions",
    default_args=default_args,
    start_date=datetime(2024, 1, 1),
    schedule_interval="0 21 * * 1-5",
    catchup=False,
    tags=["settlement", "breaks", "eod"],
) as dag:

    compute_breaks = PythonOperator(
        task_id="compute_breaks",
        python_callable=compute_settlement_breaks,
    )

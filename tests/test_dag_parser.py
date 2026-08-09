from dagscope.dag_parser import parse_dag_folder


def test_parses_all_nine_dags(task_nodes):
    dag_ids = {n.dag_id for n in task_nodes}
    expected = {
        "raw_trades_ingest",
        "fx_rates_ingest",
        "instrument_master_ingest",
        "positions_daily",
        "positions_usd",
        "pnl_daily",
        "exposure_report",
        "settlement_breaks",
        "risk_dashboard_export",
    }
    assert dag_ids == expected


def test_sql_file_reference_extracted(task_nodes):
    load_trades = next(
        n for n in task_nodes
        if n.dag_id == "raw_trades_ingest" and n.task_id == "load_trades"
    )
    assert load_trades.sql_file == "sql/load_trades.sql"
    assert load_trades.sql is None


def test_inline_sql_extracted(task_nodes):
    load_fx = next(
        n for n in task_nodes
        if n.dag_id == "fx_rates_ingest" and n.task_id == "load_fx_rates"
    )
    assert load_fx.sql is not None
    assert "raw.fx_rates" in load_fx.sql.lower()


def test_python_operator_callable_source(task_nodes):
    compute = next(
        n for n in task_nodes
        if n.dag_id == "settlement_breaks" and n.task_id == "compute_breaks"
    )
    assert compute.operator_class == "PythonOperator"
    assert compute.callable_source is not None
    assert "settlement_breaks" in compute.callable_source.lower()


def test_intra_dag_dependency(task_nodes):
    build = next(
        n for n in task_nodes
        if n.dag_id == "positions_daily" and n.task_id == "build_positions"
    )
    assert "clear_stale" in build.upstream_task_ids


def test_bash_operator_ignored(task_nodes):
    node_ids = {n.task_id for n in task_nodes if n.dag_id == "risk_dashboard_export"}
    # BashOperator export_to_s3 should not appear — not a known SQL/Python operator
    assert "export_to_s3" not in node_ids
    assert "build_risk_dashboard" in node_ids

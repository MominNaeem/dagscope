import pytest
from dagscope.sql_extractor import SQLSource
from dagscope.sql_parser import parse_sql_sources, _normalize, _extract_tables
import sqlglot


def _src(sql: str, confidence="high") -> SQLSource:
    return SQLSource(dag_id="test", task_id="t", node_id="test.t", sql=sql, confidence=confidence)


# ---------------------------------------------------------------------------
# Normalization
# ---------------------------------------------------------------------------

def test_normalize_qualified_table():
    stmt = sqlglot.parse_one("SELECT * FROM raw.trades", dialect="postgres")
    table = next(stmt.find_all(sqlglot.exp.Table))
    assert _normalize(table) == "raw.trades"


def test_normalize_unqualified_defaults_to_public():
    stmt = sqlglot.parse_one("SELECT * FROM positions", dialect="postgres")
    table = next(stmt.find_all(sqlglot.exp.Table))
    assert _normalize(table) == "public.positions"


# ---------------------------------------------------------------------------
# Statement type handling
# ---------------------------------------------------------------------------

def test_insert_reads_and_writes():
    sql = "INSERT INTO raw.trades SELECT id FROM staging.trades_staging"
    edges, rate = parse_sql_sources([_src(sql)])
    assert rate == 1.0
    assert len(edges) == 1
    assert edges[0].writes == ["raw.trades"]
    assert "staging.trades_staging" in edges[0].reads


def test_insert_excludes_pseudo_table():
    sql = """
    INSERT INTO raw.fx_rates (id, rate)
    SELECT src.id, src.rate FROM staging.fx_rates_staging src
    ON CONFLICT (id) DO UPDATE SET rate = EXCLUDED.rate
    """
    edges, _ = parse_sql_sources([_src(sql)])
    all_reads = {r for e in edges for r in e.reads}
    assert "public.excluded" not in all_reads
    assert "raw.fx_rates" not in all_reads  # write target, not a read


def test_delete_is_a_write():
    sql = "DELETE FROM public.positions_daily WHERE position_date = CURRENT_DATE"
    edges, _ = parse_sql_sources([_src(sql)])
    assert any("public.positions_daily" in e.writes for e in edges)


def test_create_table_as_select():
    sql = "CREATE TABLE public.summary AS SELECT * FROM public.pnl_daily"
    edges, _ = parse_sql_sources([_src(sql)])
    assert any(e.writes == ["public.summary"] for e in edges)
    reads = {r for e in edges for r in e.reads}
    assert "public.pnl_daily" in reads


def test_cte_name_not_in_reads():
    sql = """
    WITH daily AS (SELECT * FROM public.positions_usd)
    INSERT INTO public.pnl_daily SELECT * FROM daily
    """
    edges, _ = parse_sql_sources([_src(sql)])
    all_reads = {r for e in edges for r in e.reads}
    assert "public.daily" not in all_reads
    assert "public.positions_usd" in all_reads


def test_self_join_deduplicated():
    sql = """
    INSERT INTO public.pnl_daily (instrument_id, total_pnl)
    SELECT curr.instrument_id, curr.book_value_usd - prev.book_value_usd
    FROM public.positions_usd curr
    LEFT JOIN public.positions_usd prev ON curr.instrument_id = prev.instrument_id
    """
    edges, _ = parse_sql_sources([_src(sql)])
    reads = [r for e in edges for r in e.reads]
    assert reads.count("public.positions_usd") == 1  # deduplicated


def test_bad_sql_does_not_crash():
    sources = [_src("this is not sql at all @@##")]
    edges, rate = parse_sql_sources(sources)
    assert isinstance(edges, list)
    assert 0.0 <= rate <= 1.0


def test_low_confidence_preserved(sql_sources, table_edges):
    low_conf_sources = [s for s in sql_sources if s.confidence == "low"]
    assert len(low_conf_sources) >= 1, "settlement_breaks PythonOperator should produce low-confidence sources"
    low_conf_edges = [e for e in table_edges if e.confidence == "low"]
    assert len(low_conf_edges) >= 1

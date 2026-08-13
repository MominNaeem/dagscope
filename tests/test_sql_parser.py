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


# ---------------------------------------------------------------------------
# Additional coverage
# ---------------------------------------------------------------------------

def test_select_only_no_write_edge():
    sql = "SELECT id, price FROM raw.trades WHERE trade_date = CURRENT_DATE"
    edges, _ = parse_sql_sources([_src(sql)])
    assert all(e.writes == [] for e in edges)


def test_multi_table_join_all_detected():
    sql = """
    INSERT INTO public.pnl_daily (instrument_id, pnl)
    SELECT p.instrument_id, p.book_value_usd * f.rate
    FROM public.positions_usd p
    JOIN raw.fx_rates f ON p.currency = f.currency_code
    JOIN raw.instrument_master im ON p.instrument_id = im.instrument_id
    """
    edges, _ = parse_sql_sources([_src(sql)])
    reads = {r for e in edges for r in e.reads}
    assert "public.positions_usd" in reads
    assert "raw.fx_rates" in reads
    assert "raw.instrument_master" in reads


def test_two_ctes_both_filtered():
    sql = """
    WITH base AS (SELECT * FROM raw.trades),
         enriched AS (SELECT b.*, im.name FROM base b JOIN raw.instrument_master im ON b.id = im.id)
    INSERT INTO public.positions_daily SELECT * FROM enriched
    """
    edges, _ = parse_sql_sources([_src(sql)])
    reads = {r for e in edges for r in e.reads}
    assert "public.base" not in reads
    assert "public.enriched" not in reads
    assert "raw.trades" in reads
    assert "raw.instrument_master" in reads


def test_pseudo_tables_constant():
    from dagscope.sql_parser import _PSEUDO_TABLES
    assert "excluded" in _PSEUDO_TABLES
    assert "old" in _PSEUDO_TABLES
    assert "new" in _PSEUDO_TABLES


def test_success_rate_all_valid():
    sources = [
        _src("INSERT INTO raw.trades SELECT id FROM staging.trades_staging"),
        _src("INSERT INTO raw.fx_rates SELECT id FROM staging.fx_rates_staging"),
        _src("DELETE FROM public.positions_daily WHERE position_date < NOW()"),
    ]
    _, rate = parse_sql_sources(sources)
    assert rate == 1.0


def test_success_rate_partial_failure():
    sources = [
        _src("INSERT INTO raw.trades SELECT id FROM staging.trades_staging"),
        _src("@@@ not sql at all $$$"),
    ]
    _, rate = parse_sql_sources(sources)
    assert 0.0 < rate < 1.0


def test_empty_source_list():
    edges, rate = parse_sql_sources([])
    assert edges == []
    assert rate == 1.0


def test_merge_writes_target():
    sql = """
    MERGE INTO public.positions_usd AS tgt
    USING (SELECT instrument_id, book_value * rate AS book_value_usd
           FROM public.positions_daily pd
           JOIN raw.fx_rates fx ON pd.currency = fx.currency_code) AS src
    ON tgt.instrument_id = src.instrument_id
    WHEN MATCHED THEN UPDATE SET book_value_usd = src.book_value_usd
    WHEN NOT MATCHED THEN INSERT (instrument_id, book_value_usd)
    VALUES (src.instrument_id, src.book_value_usd)
    """
    edges, rate = parse_sql_sources([_src(sql)])
    if rate > 0:
        writes = {w for e in edges for w in e.writes}
        assert "public.positions_usd" in writes


def test_subquery_in_from_detected():
    sql = """
    INSERT INTO public.exposure_report (instrument_id, exposure)
    SELECT sub.instrument_id, sub.pnl
    FROM (SELECT instrument_id, SUM(pnl) AS pnl FROM public.pnl_daily GROUP BY 1) sub
    """
    edges, _ = parse_sql_sources([_src(sql)])
    reads = {r for e in edges for r in e.reads}
    assert "public.pnl_daily" in reads


def test_full_pipeline_parse_rate(sql_sources):
    _, rate = parse_sql_sources(sql_sources)
    assert rate == 1.0, f"Expected 100% parse rate for sample DAGs, got {rate:.1%}"


def test_multiple_sources_independent():
    sources = [
        _src("INSERT INTO raw.trades SELECT id FROM staging.trades_staging", "high"),
        _src("INSERT INTO raw.fx_rates SELECT id FROM staging.fx_rates_staging", "high"),
        _src("DELETE FROM public.positions_daily WHERE 1=1", "high"),
    ]
    edges, _ = parse_sql_sources(sources)
    assert len(edges) == 3


def test_write_target_not_in_reads():
    sql = "INSERT INTO public.pnl_daily SELECT book_value_usd FROM public.positions_usd"
    edges, _ = parse_sql_sources([_src(sql)])
    for e in edges:
        assert "public.pnl_daily" not in e.reads

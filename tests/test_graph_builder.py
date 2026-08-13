import networkx as nx
import pytest


def test_graph_is_digraph(graph):
    assert isinstance(graph, nx.DiGraph)


def test_task_nodes_present(graph):
    task_nodes = [n for n, d in graph.nodes(data=True) if d.get("kind") == "task"]
    assert len(task_nodes) >= 9  # at least one per DAG


def test_table_nodes_present(graph):
    table_nodes = [n for n, d in graph.nodes(data=True) if d.get("kind") == "table"]
    assert len(table_nodes) >= 8  # key tables from the pipeline


def test_core_tables_exist(graph):
    for table in [
        "raw.trades",
        "raw.fx_rates",
        "raw.instrument_master",
        "public.positions_daily",
        "public.positions_usd",
        "public.pnl_daily",
        "public.exposure_report",
        "public.risk_dashboard_ext",
    ]:
        assert graph.has_node(table), f"Expected table node: {table}"


def test_cross_dag_edge_exists(graph):
    # positions_daily task writes public.positions_daily
    # positions_usd task reads it — cross-DAG edge through the table node
    assert graph.has_node("public.positions_daily")
    preds = list(graph.predecessors("public.positions_daily"))
    succs = list(graph.successors("public.positions_daily"))
    # At least one task writes it and at least one reads it
    assert len(preds) >= 1
    assert len(succs) >= 1


def test_write_edge_direction(graph):
    # Task → Table for writes
    writers = [
        u for u, v in graph.edges()
        if v == "public.positions_daily"
        and graph.nodes[u].get("kind") == "task"
    ]
    assert len(writers) >= 1


def test_read_edge_direction(graph):
    # Table → Task for reads
    readers = [
        v for u, v in graph.edges()
        if u == "public.positions_daily"
        and graph.nodes[v].get("kind") == "task"
    ]
    assert len(readers) >= 1


def test_intra_dag_task_dep(graph):
    assert graph.has_edge("positions_daily.clear_stale", "positions_daily.build_positions")


def test_low_confidence_edges_marked(graph):
    low = [(u, v) for u, v, d in graph.edges(data=True) if d.get("confidence") == "low"]
    assert len(low) >= 1


# ---------------------------------------------------------------------------
# Additional coverage
# ---------------------------------------------------------------------------

def test_exact_node_count(graph):
    assert graph.number_of_nodes() == 22


def test_exact_edge_count(graph):
    assert graph.number_of_edges() == 26


def test_task_nodes_have_dag_id_attr(graph):
    for n, attrs in graph.nodes(data=True):
        if attrs.get("kind") == "task":
            assert "dag_id" in attrs, f"Task node {n} missing dag_id"
            assert attrs["dag_id"] is not None


def test_all_nodes_have_kind_attr(graph):
    for n, attrs in graph.nodes(data=True):
        assert attrs.get("kind") in ("task", "table"), f"Node {n} has unexpected kind"


def test_staging_tables_present(graph):
    assert graph.has_node("staging.trades_staging")
    assert graph.has_node("staging.fx_rates_staging")
    assert graph.has_node("staging.instrument_master_staging")


def test_write_edges_tagged(graph):
    write_edges = [
        (u, v, d) for u, v, d in graph.edges(data=True)
        if graph.nodes[u].get("kind") == "task"
        and graph.nodes[v].get("kind") == "table"
    ]
    assert len(write_edges) > 0
    for _, _, d in write_edges:
        assert d.get("kind") == "writes", f"Expected kind=writes, got {d.get('kind')}"


def test_read_edges_tagged(graph):
    read_edges = [
        (u, v, d) for u, v, d in graph.edges(data=True)
        if graph.nodes[u].get("kind") == "table"
        and graph.nodes[v].get("kind") == "task"
    ]
    assert len(read_edges) > 0
    for _, _, d in read_edges:
        assert d.get("kind") == "reads", f"Expected kind=reads, got {d.get('kind')}"


def test_task_dep_edges_tagged(graph):
    task_dep_edges = [
        (u, v, d) for u, v, d in graph.edges(data=True)
        if graph.nodes[u].get("kind") == "task"
        and graph.nodes[v].get("kind") == "task"
    ]
    assert len(task_dep_edges) > 0
    for _, _, d in task_dep_edges:
        assert d.get("kind") == "task_dep"


def test_no_self_loops(graph):
    assert list(nx.selfloop_edges(graph)) == []


def test_settlement_breaks_table_in_graph(graph):
    assert graph.has_node("public.settlement_breaks")

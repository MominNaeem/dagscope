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

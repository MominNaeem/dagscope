import pytest
from dagscope import impact_engine


def test_downstream_positions_daily(graph):
    result = impact_engine.downstream(graph, "public.positions_daily")
    node_ids = {n.node_id for n in result.nodes}

    # Downstream of positions_daily must include positions_usd pipeline and beyond
    assert "public.positions_usd" in node_ids
    assert "public.pnl_daily" in node_ids
    assert "public.exposure_report" in node_ids
    assert "public.risk_dashboard_ext" in node_ids


def test_downstream_hop_ordering(graph):
    result = impact_engine.downstream(graph, "public.positions_daily")
    hops = {n.node_id: n.hops for n in result.nodes}

    # positions_usd task is 2 hops away (table→task→table→task...)
    # Closer nodes must have smaller hop counts
    assert hops["public.positions_usd"] > hops.get(
        next(iter([n.node_id for n in result.nodes if n.hops == 1]), "NONE"), 0
    )


def test_deep_chain_length(graph):
    # raw.trades → ... → public.risk_dashboard_ext: at least 6 hops
    result = impact_engine.downstream(graph, "raw.trades")
    max_hops = max(n.hops for n in result.nodes)
    assert max_hops >= 6, f"Expected deep chain, got max {max_hops} hops"


def test_upstream_pnl_daily(graph):
    result = impact_engine.upstream(graph, "public.pnl_daily")
    node_ids = {n.node_id for n in result.nodes}
    assert "public.positions_usd" in node_ids
    assert "public.positions_daily" in node_ids
    assert "raw.trades" in node_ids


def test_cycle_detected(graph):
    cycles = impact_engine.find_cycles(graph)
    assert len(cycles) >= 1, "Expected at least one cycle (positions_daily ↔ settlement_breaks)"

    # The cycle must involve both settlement_breaks and positions_daily tables
    all_cycle_nodes = {node for cycle in cycles for node in cycle}
    assert any("settlement_breaks" in n for n in all_cycle_nodes)
    assert any("positions_daily" in n for n in all_cycle_nodes)


def test_instrument_master_is_not_unused(graph):
    result = impact_engine.downstream(graph, "raw.instrument_master")
    node_ids = {n.node_id for n in result.nodes}
    # instrument_master feeds into exposure_report (deep downstream)
    assert "public.exposure_report" in node_ids, (
        "raw.instrument_master appears unused but is read by exposure_report"
    )


def test_node_not_found_raises(graph):
    with pytest.raises(ValueError, match="not found"):
        impact_engine.downstream(graph, "does.not.exist")


def test_graph_summary(graph):
    s = impact_engine.graph_summary(graph)
    assert s["task_count"] >= 9
    assert s["table_count"] >= 8
    assert s["dag_count"] >= 9
    assert s["low_confidence_edge_count"] >= 1


# ---------------------------------------------------------------------------
# Additional coverage
# ---------------------------------------------------------------------------

def test_result_is_impact_result_type(graph):
    result = impact_engine.downstream(graph, "public.positions_daily")
    assert isinstance(result, impact_engine.ImpactResult)


def test_downstream_direction_label(graph):
    result = impact_engine.downstream(graph, "public.positions_daily")
    assert result.direction == "downstream"


def test_upstream_direction_label(graph):
    result = impact_engine.upstream(graph, "public.pnl_daily")
    assert result.direction == "upstream"


def test_selected_node_not_in_results(graph):
    node = "public.positions_daily"
    result = impact_engine.downstream(graph, node)
    assert all(n.node_id != node for n in result.nodes)


def test_all_hops_are_positive_integers(graph):
    result = impact_engine.downstream(graph, "raw.trades")
    for n in result.nodes:
        assert isinstance(n.hops, int)
        assert n.hops >= 1


def test_staging_table_has_empty_upstream(graph):
    # staging.trades_staging has no writers — it's an external source
    result = impact_engine.upstream(graph, "staging.trades_staging")
    assert result.nodes == []


def test_leaf_table_has_empty_downstream(graph):
    # public.risk_dashboard_ext is never read by any task in the sample set
    result = impact_engine.downstream(graph, "public.risk_dashboard_ext")
    assert result.nodes == []


def test_settlement_breaks_downstream_of_positions_daily(graph):
    result = impact_engine.downstream(graph, "public.positions_daily")
    node_ids = {n.node_id for n in result.nodes}
    assert "public.settlement_breaks" in node_ids


def test_risk_dashboard_upstream_includes_pnl(graph):
    result = impact_engine.upstream(graph, "public.risk_dashboard_ext")
    node_ids = {n.node_id for n in result.nodes}
    assert "public.pnl_daily" in node_ids


def test_summary_exact_edge_count(graph):
    s = impact_engine.graph_summary(graph)
    assert s["edge_count"] == 26


def test_cycles_are_lists_of_lists(graph):
    cycles = impact_engine.find_cycles(graph)
    assert isinstance(cycles, list)
    for cycle in cycles:
        assert isinstance(cycle, list)
        assert len(cycle) >= 2


def test_nodes_sorted_ascending_by_hops(graph):
    result = impact_engine.downstream(graph, "raw.trades")
    hops = [n.hops for n in result.nodes]
    assert hops == sorted(hops)

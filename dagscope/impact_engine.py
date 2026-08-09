from typing import Literal

import networkx as nx
from pydantic import BaseModel


class ImpactNode(BaseModel):
    node_id: str
    kind: str
    hops: int


class ImpactResult(BaseModel):
    query_node: str
    direction: Literal["downstream", "upstream"]
    nodes: list[ImpactNode]


def downstream(G: nx.DiGraph, node_id: str) -> ImpactResult:
    _assert_exists(G, node_id)
    lengths = nx.single_source_shortest_path_length(G, node_id)
    return ImpactResult(
        query_node=node_id,
        direction="downstream",
        nodes=_ranked(G, lengths, exclude=node_id),
    )


def upstream(G: nx.DiGraph, node_id: str) -> ImpactResult:
    _assert_exists(G, node_id)
    lengths = nx.single_source_shortest_path_length(G.reverse(copy=False), node_id)
    return ImpactResult(
        query_node=node_id,
        direction="upstream",
        nodes=_ranked(G, lengths, exclude=node_id),
    )


def find_cycles(G: nx.DiGraph) -> list[list[str]]:
    return list(nx.simple_cycles(G))


def graph_summary(G: nx.DiGraph) -> dict:
    task_nodes = [n for n, d in G.nodes(data=True) if d.get("kind") == "task"]
    table_nodes = [n for n, d in G.nodes(data=True) if d.get("kind") == "table"]
    low_conf = [(u, v) for u, v, d in G.edges(data=True) if d.get("confidence") == "low"]
    dag_ids = {G.nodes[n].get("dag_id") for n in task_nodes} - {None}
    return {
        "task_count": len(task_nodes),
        "table_count": len(table_nodes),
        "edge_count": G.number_of_edges(),
        "low_confidence_edge_count": len(low_conf),
        "dag_count": len(dag_ids),
    }


def _ranked(G: nx.DiGraph, lengths: dict, exclude: str) -> list[ImpactNode]:
    return [
        ImpactNode(node_id=n, kind=G.nodes[n].get("kind", "unknown"), hops=h)
        for n, h in sorted(lengths.items(), key=lambda x: x[1])
        if n != exclude
    ]


def _assert_exists(G: nx.DiGraph, node_id: str) -> None:
    if not G.has_node(node_id):
        available = sorted(G.nodes())[:10]
        raise ValueError(
            f"Node not found: '{node_id}'. "
            f"Sample nodes: {available}"
        )

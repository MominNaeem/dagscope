import networkx as nx

from dagscope.dag_parser import TaskNode
from dagscope.sql_parser import TableEdge


def build_graph(task_nodes: list[TaskNode], table_edges: list[TableEdge]) -> nx.DiGraph:
    G: nx.DiGraph = nx.DiGraph()

    # Task nodes
    for node in task_nodes:
        G.add_node(
            node.node_id,
            kind="task",
            dag_id=node.dag_id,
            task_id=node.task_id,
            operator=node.operator_class,
        )

    # Task → Task edges (Airflow dependencies within a DAG)
    for node in task_nodes:
        for upstream_task_id in node.upstream_task_ids:
            upstream_node_id = f"{node.dag_id}.{upstream_task_id}"
            if G.has_node(upstream_node_id):
                G.add_edge(upstream_node_id, node.node_id, kind="task_dep", confidence="high")

    # Table nodes and read/write edges (cross-DAG edges emerge here automatically)
    for edge in table_edges:
        for table in edge.reads:
            _ensure_table_node(G, table)
            G.add_edge(
                table,
                edge.node_id,
                kind="reads",
                confidence=edge.confidence,
                statement_type=edge.statement_type,
            )

        for table in edge.writes:
            _ensure_table_node(G, table)
            G.add_edge(
                edge.node_id,
                table,
                kind="writes",
                confidence=edge.confidence,
                statement_type=edge.statement_type,
            )

    return G


def _ensure_table_node(G: nx.DiGraph, table: str) -> None:
    if G.has_node(table):
        return
    parts = table.split(".", 1)
    schema, name = (parts[0], parts[1]) if len(parts) == 2 else ("public", parts[0])
    G.add_node(table, kind="table", schema=schema, name=name)

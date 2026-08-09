from pathlib import Path

import networkx as nx
import pytest

from dagscope.dag_parser import parse_dag_folder
from dagscope.graph_builder import build_graph
from dagscope.sql_extractor import extract_sql
from dagscope.sql_parser import parse_sql_sources

SAMPLE_DAGS = Path(__file__).parent.parent / "sample_dags"


@pytest.fixture(scope="session")
def dag_folder():
    return SAMPLE_DAGS


@pytest.fixture(scope="session")
def task_nodes(dag_folder):
    return parse_dag_folder(dag_folder)


@pytest.fixture(scope="session")
def sql_sources(task_nodes, dag_folder):
    return extract_sql(task_nodes, dag_folder)


@pytest.fixture(scope="session")
def table_edges(sql_sources):
    edges, _ = parse_sql_sources(sql_sources)
    return edges


@pytest.fixture(scope="session")
def graph(task_nodes, table_edges) -> nx.DiGraph:
    return build_graph(task_nodes, table_edges)

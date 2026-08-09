import re
from pathlib import Path
from typing import Literal

from pydantic import BaseModel

from dagscope.dag_parser import TaskNode

_SQL_KEYWORDS = re.compile(
    r"\b(SELECT|INSERT\s+INTO|UPDATE|DELETE\s+FROM|CREATE\s+TABLE|MERGE\s+INTO|WITH\s+\w)",
    re.IGNORECASE,
)
_TRIPLE_DOUBLE = re.compile(r'"""(.*?)"""', re.DOTALL)
_TRIPLE_SINGLE = re.compile(r"'''(.*?)'''", re.DOTALL)


class SQLSource(BaseModel):
    dag_id: str
    task_id: str
    node_id: str
    sql: str
    confidence: Literal["high", "low"]


def extract_sql(task_nodes: list[TaskNode], dag_folder: str | Path) -> list[SQLSource]:
    folder = Path(dag_folder)
    sources: list[SQLSource] = []

    for node in task_nodes:
        if node.sql:
            sources.append(
                SQLSource(
                    dag_id=node.dag_id,
                    task_id=node.task_id,
                    node_id=node.node_id,
                    sql=node.sql,
                    confidence="high",
                )
            )

        elif node.sql_file:
            sql_path = folder / node.sql_file
            if sql_path.exists():
                sources.append(
                    SQLSource(
                        dag_id=node.dag_id,
                        task_id=node.task_id,
                        node_id=node.node_id,
                        sql=sql_path.read_text(),
                        confidence="high",
                    )
                )
            else:
                print(f"[sql_extractor] SQL file not found: {sql_path}")

        elif node.callable_source:
            for sql in _extract_from_callable(node.callable_source):
                sources.append(
                    SQLSource(
                        dag_id=node.dag_id,
                        task_id=node.task_id,
                        node_id=node.node_id,
                        sql=sql,
                        confidence="low",
                    )
                )

    return sources


def _extract_from_callable(source: str) -> list[str]:
    candidates: list[str] = []
    for pattern in (_TRIPLE_DOUBLE, _TRIPLE_SINGLE):
        for match in pattern.finditer(source):
            text = match.group(1).strip()
            if _SQL_KEYWORDS.search(text):
                candidates.append(text)
    return candidates

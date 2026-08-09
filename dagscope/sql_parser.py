import logging
from typing import Literal

import sqlglot
from sqlglot import exp
from pydantic import BaseModel

from dagscope.sql_extractor import SQLSource

logger = logging.getLogger(__name__)

# Pseudo-tables and aliases that appear in SQL but are not real tables
_PSEUDO_TABLES = {"excluded", "new", "old"}


class TableEdge(BaseModel):
    dag_id: str
    task_id: str
    node_id: str
    reads: list[str]   # "schema.table" normalized, sorted
    writes: list[str]  # "schema.table" normalized
    confidence: Literal["high", "low"]
    statement_type: str


def parse_sql_sources(
    sources: list[SQLSource],
) -> tuple[list[TableEdge], float]:
    """
    Returns (edges, parse_success_rate).
    Never raises — failed statements are logged and skipped.
    """
    edges: list[TableEdge] = []
    total = 0
    failures = 0

    for source in sources:
        try:
            stmts = sqlglot.parse(source.sql, dialect="postgres")
        except Exception as exc:
            logger.warning("[sql_parser] Parse error in %s: %s", source.node_id, exc)
            failures += 1
            total += 1
            continue

        for stmt in stmts:
            if stmt is None:
                continue
            total += 1
            try:
                reads, writes, stmt_type = _extract_tables(stmt)
                if reads or writes:
                    edges.append(
                        TableEdge(
                            dag_id=source.dag_id,
                            task_id=source.task_id,
                            node_id=source.node_id,
                            reads=reads,
                            writes=writes,
                            confidence=source.confidence,
                            statement_type=stmt_type,
                        )
                    )
            except Exception as exc:
                failures += 1
                logger.warning("[sql_parser] Extraction failed for %s: %s", source.node_id, exc)

    success_rate = (total - failures) / total if total > 0 else 1.0
    return edges, success_rate


def _extract_tables(stmt: exp.Expression) -> tuple[list[str], list[str], str]:
    stmt_type = type(stmt).__name__
    write_target: str | None = None

    if isinstance(stmt, exp.Insert):
        write_target = _normalize(stmt.this)
    elif isinstance(stmt, exp.Create):
        if str(stmt.args.get("kind", "")).upper() == "TABLE":
            write_target = _normalize(stmt.this)
    elif isinstance(stmt, exp.Merge):
        write_target = _normalize(stmt.this)
    elif isinstance(stmt, exp.Delete):
        write_target = _normalize(stmt.this)

    # Collect CTE names so we don't mistake them for real tables
    cte_names = {
        cte.alias.lower()
        for cte in stmt.find_all(exp.CTE)
        if cte.alias
    }

    all_tables: set[str] = set()
    for t in stmt.find_all(exp.Table):
        name = _normalize(t)
        if name and t.name.lower() not in cte_names and t.name.lower() not in _PSEUDO_TABLES:
            all_tables.add(name)

    reads = sorted(all_tables - {write_target} if write_target else all_tables)
    writes = [write_target] if write_target else []

    return reads, writes, stmt_type


def _normalize(node: exp.Expression | None) -> str | None:
    if node is None:
        return None
    if isinstance(node, exp.Table):
        schema = (node.db or "public").lower()
        name = node.name.lower() if node.name else ""
        return f"{schema}.{name}" if name else None
    # For Create/Insert targets that wrap a Table (e.g. Schema node)
    found = node.find(exp.Table)
    return _normalize(found) if found else None

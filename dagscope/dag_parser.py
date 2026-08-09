"""
AST-based Airflow DAG parser.

Reads .py files without executing them — works without a live Airflow
installation. DagBag integration is a planned upgrade for richer
dependency semantics (dynamic tasks, TaskGroups).
"""

import ast
import inspect
import textwrap
from pathlib import Path
from typing import Literal

from pydantic import BaseModel

SQL_OPERATOR_CLASSES = {
    "PostgresOperator",
    "SQLExecuteQueryOperator",
    "MsSqlOperator",
    "MySqlOperator",
    "SqliteOperator",
}

PYTHON_OPERATOR_CLASSES = {
    "PythonOperator",
    "PythonBranchOperator",
}

ALL_KNOWN_OPERATORS = SQL_OPERATOR_CLASSES | PYTHON_OPERATOR_CLASSES


class TaskNode(BaseModel):
    dag_id: str
    task_id: str
    node_id: str                         # "{dag_id}.{task_id}"
    operator_class: str
    upstream_task_ids: list[str] = []
    sql: str | None = None               # inline SQL string
    sql_file: str | None = None          # relative path to .sql file
    callable_source: str | None = None   # PythonOperator callable body


def parse_dag_folder(dag_folder: str | Path) -> list[TaskNode]:
    folder = Path(dag_folder)
    nodes: list[TaskNode] = []
    for py_file in sorted(folder.glob("*.py")):
        try:
            nodes.extend(_parse_dag_file(py_file))
        except SyntaxError as exc:
            print(f"[dag_parser] Syntax error in {py_file.name}: {exc}")
        except Exception as exc:
            print(f"[dag_parser] Skipping {py_file.name}: {exc}")
    return nodes


def _parse_dag_file(path: Path) -> list[TaskNode]:
    source = path.read_text()
    tree = ast.parse(source)

    dag_id = _find_dag_id(tree)
    if not dag_id:
        return []

    func_sources = _collect_function_sources(source)
    task_data: dict[str, dict] = {}
    _collect_tasks(tree, task_data, func_sources)

    var_to_task_id = {var: d["task_id"] for var, d in task_data.items()}
    deps: dict[str, list[str]] = {d["task_id"]: [] for d in task_data.values()}
    _collect_deps(tree, var_to_task_id, deps)

    return [
        TaskNode(
            dag_id=dag_id,
            task_id=d["task_id"],
            node_id=f"{dag_id}.{d['task_id']}",
            operator_class=d["operator_class"],
            upstream_task_ids=deps.get(d["task_id"], []),
            sql=d.get("sql"),
            sql_file=d.get("sql_file"),
            callable_source=d.get("callable_source"),
        )
        for d in task_data.values()
    ]


# ---------------------------------------------------------------------------
# DAG id extraction
# ---------------------------------------------------------------------------

def _find_dag_id(tree: ast.Module) -> str | None:
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and _call_name(node) == "DAG":
            for kw in node.keywords:
                if kw.arg == "dag_id" and isinstance(kw.value, ast.Constant):
                    return str(kw.value.value)
    return None


# ---------------------------------------------------------------------------
# Task extraction
# ---------------------------------------------------------------------------

def _collect_tasks(
    tree: ast.Module,
    task_data: dict[str, dict],
    func_sources: dict[str, str],
) -> None:
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        if not isinstance(node.value, ast.Call):
            continue
        if not isinstance(node.targets[0], ast.Name):
            continue

        call = node.value
        op_class = _call_name(call)
        if op_class not in ALL_KNOWN_OPERATORS:
            continue

        var_name = node.targets[0].id
        kwargs = {kw.arg: kw.value for kw in call.keywords if kw.arg}

        task_id_node = kwargs.get("task_id")
        if not isinstance(task_id_node, ast.Constant):
            continue
        task_id = str(task_id_node.value)

        data: dict = {"task_id": task_id, "operator_class": op_class}

        if op_class in SQL_OPERATOR_CLASSES:
            sql_node = kwargs.get("sql")
            if isinstance(sql_node, ast.Constant) and isinstance(sql_node.value, str):
                sql_str = sql_node.value.strip()
                if sql_str.lower().endswith(".sql"):
                    data["sql_file"] = sql_str
                else:
                    data["sql"] = sql_str

        elif op_class in PYTHON_OPERATOR_CLASSES:
            callable_node = kwargs.get("python_callable")
            if isinstance(callable_node, ast.Name):
                src = func_sources.get(callable_node.id)
                if src:
                    data["callable_source"] = src

        task_data[var_name] = data


def _collect_function_sources(source: str) -> dict[str, str]:
    """Map function name → dedented source, for PythonOperator callables."""
    tree = ast.parse(source)
    lines = source.splitlines()
    result: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            body = "\n".join(lines[node.lineno - 1 : node.end_lineno])
            result[node.name] = textwrap.dedent(body)
    return result


# ---------------------------------------------------------------------------
# Dependency extraction (>> operator)
# ---------------------------------------------------------------------------

def _collect_deps(
    tree: ast.Module,
    var_to_task_id: dict[str, str],
    deps: dict[str, list[str]],
) -> None:
    for node in ast.walk(tree):
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.BinOp):
            _process_rshift(node.value, var_to_task_id, deps)


def _process_rshift(
    node: ast.BinOp,
    var_to_task_id: dict[str, str],
    deps: dict[str, list[str]],
) -> None:
    if not isinstance(node.op, ast.RShift):
        return

    # Handle chained: (a >> b) >> c  →  recurse on left first
    if isinstance(node.left, ast.BinOp):
        _process_rshift(node.left, var_to_task_id, deps)

    lefts = _resolve_task_ids(node.left, var_to_task_id)
    rights = _resolve_task_ids(node.right, var_to_task_id)

    for right in rights:
        if right in deps:
            for left in lefts:
                if left not in deps[right]:
                    deps[right].append(left)


def _resolve_task_ids(node: ast.expr, var_to_task_id: dict[str, str]) -> list[str]:
    """Return task_ids that the node resolves to (handles vars, lists, chains)."""
    if isinstance(node, ast.Name):
        tid = var_to_task_id.get(node.id)
        return [tid] if tid else []
    if isinstance(node, ast.List):
        out: list[str] = []
        for elt in node.elts:
            out.extend(_resolve_task_ids(elt, var_to_task_id))
        return out
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.RShift):
        # The rightmost task(s) of a chain are the "output" side
        return _resolve_task_ids(node.right, var_to_task_id)
    return []


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _call_name(node: ast.Call) -> str:
    if isinstance(node.func, ast.Name):
        return node.func.id
    if isinstance(node.func, ast.Attribute):
        return node.func.attr
    return ""

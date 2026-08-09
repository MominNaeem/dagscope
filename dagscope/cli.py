import json
import os
import sys
from pathlib import Path

# Auto-load .env from the current working directory
_env_file = Path(".env")
if _env_file.exists():
    for _line in _env_file.read_text().splitlines():
        _line = _line.strip()
        if _line and not _line.startswith("#") and "=" in _line:
            _k, _v = _line.split("=", 1)
            os.environ.setdefault(_k.strip(), _v.strip())

import click
from rich.console import Console
from rich.table import Table as RichTable

from dagscope import impact_engine
from dagscope.dag_parser import parse_dag_folder
from dagscope.graph_builder import build_graph
from dagscope.sql_extractor import extract_sql
from dagscope.sql_parser import parse_sql_sources

console = Console()


def _load_graph(dag_dir: str):
    folder = Path(dag_dir)
    if not folder.exists():
        console.print(f"[red]DAG folder not found: {folder}[/red]")
        sys.exit(1)

    task_nodes = parse_dag_folder(folder)
    sql_sources = extract_sql(task_nodes, folder)
    table_edges, success_rate = parse_sql_sources(sql_sources)
    G = build_graph(task_nodes, table_edges)

    if success_rate < 1.0:
        console.print(f"[yellow]SQL parse success rate: {success_rate:.1%}[/yellow]")

    return G


@click.group()
@click.version_option()
def cli():
    """dagscope — Airflow DAG lineage and change impact analysis."""


# ---------------------------------------------------------------------------
# dagscope impact
# ---------------------------------------------------------------------------

@cli.command()
@click.option("--table", "target", default=None, metavar="SCHEMA.TABLE",
              help="Table to query impact for (e.g. public.positions_daily)")
@click.option("--task", "target_task", default=None, metavar="DAG.TASK",
              help="Task to query impact for (e.g. positions_daily.build_positions)")
@click.option("--dag-dir", default="sample_dags", show_default=True,
              help="Path to DAG folder")
@click.option("--direction", default="downstream",
              type=click.Choice(["downstream", "upstream"]), show_default=True)
@click.option("--no-llm", is_flag=True, help="Skip AI summarization")
def impact(target, target_task, dag_dir, direction, no_llm):
    """Show blast radius of a change to a table or task."""
    node_id = target or target_task
    if not node_id:
        raise click.UsageError("Provide --table or --task.")

    G = _load_graph(dag_dir)

    try:
        result = (
            impact_engine.downstream(G, node_id)
            if direction == "downstream"
            else impact_engine.upstream(G, node_id)
        )
    except ValueError as exc:
        console.print(f"[red]{exc}[/red]")
        sys.exit(1)

    if not result.nodes:
        console.print(
            f"[green]No {direction} dependencies found for [bold]{node_id}[/bold][/green]"
        )
        return

    t = RichTable(
        title=f"{direction.capitalize()} impact of [bold]{node_id}[/bold]",
        show_lines=True,
    )
    t.add_column("Node", style="cyan", no_wrap=True)
    t.add_column("Type", style="magenta")
    t.add_column("Hops", justify="right", style="yellow")

    for n in result.nodes:
        t.add_row(n.node_id, n.kind, str(n.hops))

    console.print(t)
    console.print(f"\n[bold]{len(result.nodes)}[/bold] node(s) in blast radius")

    if not no_llm:
        _maybe_llm_summary(result, G)


# ---------------------------------------------------------------------------
# dagscope check
# ---------------------------------------------------------------------------

@cli.command()
@click.option("--cycles", is_flag=True, help="Detect cycles in the lineage graph")
@click.option("--dag-dir", default="sample_dags", show_default=True)
def check(cycles, dag_dir):
    """Run integrity checks on the DAG set."""
    G = _load_graph(dag_dir)
    summary = impact_engine.graph_summary(G)

    console.print("\n[bold]Graph Summary[/bold]")
    console.print(f"  DAGs:   {summary['dag_count']}")
    console.print(f"  Tasks:  {summary['task_count']}")
    console.print(f"  Tables: {summary['table_count']}")
    console.print(
        f"  Edges:  {summary['edge_count']} "
        f"({summary['low_confidence_edge_count']} low-confidence)"
    )

    if cycles:
        found = impact_engine.find_cycles(G)
        if found:
            console.print(f"\n[red bold]Found {len(found)} cycle(s):[/red bold]")
            for i, cycle in enumerate(found, 1):
                path = " → ".join(cycle) + f" → {cycle[0]}"
                console.print(f"  Cycle {i}: {path}")
            sys.exit(1)
        else:
            console.print("\n[green]No cycles detected.[/green]")


# ---------------------------------------------------------------------------
# dagscope graph
# ---------------------------------------------------------------------------

@cli.command(name="graph")
@click.option("--output", default="graph.json", show_default=True)
@click.option("--dag-dir", default="sample_dags", show_default=True)
def export_graph(output, dag_dir):
    """Export the full lineage graph to JSON."""
    G = _load_graph(dag_dir)

    data = {
        "nodes": [{"id": n, **attrs} for n, attrs in G.nodes(data=True)],
        "edges": [{"source": u, "target": v, **attrs} for u, v, attrs in G.edges(data=True)],
    }

    out = Path(output)
    out.write_text(json.dumps(data, indent=2))
    console.print(f"[green]Exported to {out}[/green] ({len(data['nodes'])} nodes, {len(data['edges'])} edges)")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# dagscope serve
# ---------------------------------------------------------------------------

@cli.command()
@click.option("--dag-dir", default="sample_dags", show_default=True)
@click.option("--port", default=8000, show_default=True, type=int)
@click.option("--host", default="127.0.0.1", show_default=True)
def serve(dag_dir, port, host):
    """Launch the web UI (force-directed lineage graph in browser)."""
    import os
    os.environ["DAGSCOPE_DAG_DIR"] = str(Path(dag_dir).resolve())
    console.print(f"[bold]dagscope[/bold] web UI → http://{host}:{port}")
    try:
        import uvicorn
        uvicorn.run("dagscope.web.server:app", host=host, port=port, reload=False)
    except ImportError:
        console.print("[red]uvicorn not installed. Run: pip install uvicorn[/red]")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _maybe_llm_summary(result, G) -> None:
    try:
        from dagscope.llm_summarizer import summarize
        summary = summarize(result, G)
        if summary is None:
            return
        color = "red" if summary.severity in ("high", "critical") else "yellow"
        console.print(
            f"\n[bold]AI Summary[/bold]  "
            f"severity: [{color}]{summary.severity}[/{color}]"
        )
        console.print(f"\n{summary.summary}")
        if summary.recommended_checks:
            console.print("\n[bold]Recommended checks:[/bold]")
            for item in summary.recommended_checks:
                console.print(f"  • {item}")
        if summary.uncertainty:
            console.print(f"\n[dim]Note: {summary.uncertainty}[/dim]")
    except Exception as exc:
        console.print(f"[dim]LLM summary unavailable: {exc}[/dim]")

import json
import logging
import os
import re
from typing import Literal

import networkx as nx
from pydantic import BaseModel

from dagscope.impact_engine import ImpactResult

logger = logging.getLogger(__name__)

_SYSTEM = """You are a data platform engineer reviewing the downstream impact of a pipeline change.

You receive a JSON object with:
- query_node: the changed table or task
- direction: downstream or upstream
- affected_count: total nodes in blast radius
- nodes: up to 20 affected nodes with hop distances
- low_confidence_edges: edges inferred from PythonOperator source (may be incomplete)

Respond with exactly this JSON schema — no prose outside it:
{
  "severity": "low" | "medium" | "high" | "critical",
  "summary": "<one paragraph in plain English>",
  "affected_assets": [{"name": "<node_id>", "hops": <int>, "why": "<one sentence>"}],
  "recommended_checks": ["<action item>"],
  "uncertainty": "<note about low-confidence edges, or null>"
}

Severity guide:
  critical — 8+ downstream nodes, or export/reporting tables in the path
  high     — 4-7 nodes, or client-facing table names
  medium   — 2-3 nodes
  low      — 1 node or only task dependencies"""


class ImpactSummary(BaseModel):
    severity: Literal["low", "medium", "high", "critical"]
    summary: str
    affected_assets: list[dict]
    recommended_checks: list[str]
    uncertainty: str | None = None


def _strip_fences(text: str) -> str:
    """Remove markdown code fences the model sometimes wraps JSON in."""
    text = text.strip()
    match = re.search(r"```(?:json)?\s*([\s\S]+?)\s*```", text)
    return match.group(1) if match else text


def summarize(result: ImpactResult, G: nx.DiGraph) -> ImpactSummary | None:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        logger.debug("ANTHROPIC_API_KEY not set — skipping LLM summary")
        return None

    try:
        import anthropic
    except ImportError:
        logger.debug("anthropic package not installed")
        return None

    affected_node_ids = {n.node_id for n in result.nodes}
    low_conf = [
        f"{u} → {v}"
        for u, v, d in G.edges(data=True)
        if d.get("confidence") == "low"
        and (u in affected_node_ids or v in affected_node_ids or
             u == result.query_node or v == result.query_node)
    ]

    payload = {
        "query_node": result.query_node,
        "direction": result.direction,
        "affected_count": len(result.nodes),
        "nodes": [
            {"node_id": n.node_id, "kind": n.kind, "hops": n.hops}
            for n in result.nodes[:20]
        ],
        "low_confidence_edges": low_conf,
    }

    client = anthropic.Anthropic(api_key=api_key)
    try:
        msg = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=1024,
            system=_SYSTEM,
            messages=[{"role": "user", "content": json.dumps(payload)}],
        )
        return ImpactSummary(**json.loads(_strip_fences(msg.content[0].text)))
    except Exception as exc:
        logger.warning("LLM summarization failed: %s", exc)
        return None

import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from dagscope import impact_engine
from dagscope.dag_parser import parse_dag_folder
from dagscope.graph_builder import build_graph
from dagscope.sql_extractor import extract_sql
from dagscope.sql_parser import parse_sql_sources

_G = None
_STATIC = Path(__file__).parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _G
    dag_dir = Path(os.environ.get("DAGSCOPE_DAG_DIR", "sample_dags"))
    task_nodes = parse_dag_folder(dag_dir)
    sql_sources = extract_sql(task_nodes, dag_dir)
    table_edges, rate = parse_sql_sources(sql_sources)
    _G = build_graph(task_nodes, table_edges)
    print(f"[dagscope] Loaded {_G.number_of_nodes()} nodes, {_G.number_of_edges()} edges  (SQL parse rate: {rate:.1%})")
    yield


app = FastAPI(title="dagscope", lifespan=lifespan)

# Allow the Next.js dev server (port 3000) to call the API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_methods=["GET"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory=str(_STATIC)), name="static")


@app.get("/", response_class=HTMLResponse)
async def root():
    return (_STATIC / "index.html").read_text()


@app.get("/api/graph")
async def get_graph():
    return {
        "nodes": [{"id": n, **attrs} for n, attrs in _G.nodes(data=True)],
        "edges": [{"from": u, "to": v, **attrs} for u, v, attrs in _G.edges(data=True)],
    }


@app.get("/api/impact/{node_id:path}")
async def get_impact(node_id: str, direction: str = "downstream"):
    try:
        fn = impact_engine.downstream if direction == "downstream" else impact_engine.upstream
        result = fn(_G, node_id)
        return result.model_dump()
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@app.get("/api/ai-summary/{node_id:path}")
async def get_ai_summary(node_id: str, direction: str = "downstream"):
    try:
        fn = impact_engine.downstream if direction == "downstream" else impact_engine.upstream
        result = fn(_G, node_id)
        from dagscope.llm_summarizer import summarize
        summary = summarize(result, _G)
        if summary is None:
            return {"error": "ANTHROPIC_API_KEY not set or anthropic package missing"}
        return summary.model_dump()
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/api/cycles")
async def get_cycles():
    return {"cycles": impact_engine.find_cycles(_G)}


@app.get("/api/summary")
async def get_summary():
    return impact_engine.graph_summary(_G)

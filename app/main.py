from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, Dict, Any

from app.queries import papers_by_year, papers_by_field
from app.agent import run_multi_agent

app = FastAPI(title="SciSciNet Dartmouth Agent Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5174", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChartRequest(BaseModel):
    year_from: int = 2020
    year_to: int = 2024
    doctype: Optional[str] = None
    field_level: int = 1
    field_score_min: float = 0.3
    top_k: int = 30


class ChatRequest(BaseModel):
    message: str
    prev_plan: Optional[Dict[str, Any]] = None


@app.get("/health")
def health():
    return {"ok": True}


@app.post("/api/chart/papers_by_year")
def chart_papers_by_year(req: ChartRequest):
    rows = papers_by_year(req.year_from, req.year_to, req.doctype)
    data = [{"year": int(y), "n_papers": int(n)} for y, n in rows]

    spec = {
        "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
        "description": "Number of Dartmouth papers by year",
        "data": {"values": data},
        "mark": {"type": "bar", "tooltip": True},
        "encoding": {
            "x": {"field": "year", "type": "ordinal", "title": "Year"},
            "y": {"field": "n_papers", "type": "quantitative", "title": "Papers"},
            "tooltip": [{"field": "year"}, {"field": "n_papers"}],
        },
    }
    return {"chart": "papers_by_year", "data": data, "vegaLiteSpec": spec}


@app.post("/api/chart/papers_by_field")
def chart_papers_by_field(req: ChartRequest):
    rows = papers_by_field(
        req.year_from,
        req.year_to,
        level=req.field_level,
        field_score_min=req.field_score_min,
        doctype=req.doctype,
        top_k=req.top_k,
    )
    data = [{"field": str(f), "n_papers": int(n)} for f, n in rows]

    spec = {
        "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
        "description": "Number of Dartmouth papers by field",
        "data": {"values": data},
        "mark": {"type": "bar", "tooltip": True},
        "encoding": {
            "x": {"field": "field", "type": "nominal", "sort": "-y", "title": "Field"},
            "y": {"field": "n_papers", "type": "quantitative", "title": "Papers"},
            "tooltip": [{"field": "field"}, {"field": "n_papers"}],
        },
    }
    return {"chart": "papers_by_field", "data": data, "vegaLiteSpec": spec}


@app.post("/api/chat")
def chat(req: ChatRequest):
    try:
        return run_multi_agent(req.message, prev_plan=req.prev_plan)
    except Exception as e:
        import traceback

        return {
            "error_type": type(e).__name__,
            "error": str(e),
            "traceback_tail": traceback.format_exc().splitlines()[-40:],
        }
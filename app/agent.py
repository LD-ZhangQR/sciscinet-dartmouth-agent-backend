import json
import os
import re
from typing import Any, Dict, Literal, Optional, Tuple, List

from dotenv import load_dotenv
from openai import OpenAI

from app.queries import papers_by_year, papers_by_field

load_dotenv()
client = OpenAI()

ChartType = Literal["papers_by_year", "papers_by_field"]
MarkType = Literal["bar", "line", "area"]

SYSTEM = """
You are a planner/router for a Dartmouth SciSciNet dashboard.
Return ONLY valid JSON (no markdown, no code fences).

Supported charts:
- papers_by_year: counts of papers grouped by year
- papers_by_field: counts of papers grouped by field name

Core parameters:
- year_from, year_to
- doctype: null unless user mentions (e.g., "article", "preprint")
- papers_by_field: field_level, field_score_min, top_k

Style parameters:
- color: null unless user requests a specific color
- mark: "bar" unless user requests "line chart", "trend", or "area chart"

Compare mode:
- If the user asks to compare two year ranges, set compare=true and provide:
  compare_year_from, compare_year_to
- Compare should use the same chart_type and filters unless user changes them.

IMPORTANT: Conversation / prev_plan
- You may be given a previous plan as JSON (prev_plan).
- If prev_plan is provided and the user ONLY requests a styling change (e.g., color/mark),
  then KEEP all non-style parameters (including compare fields) from prev_plan and only change style fields.
- If prev_plan is provided and the user requests filter changes (doctype/top_k/field_score_min/field_level),
  keep the chart_type and other parameters unless user explicitly changes them.

Defaults (when no prior context):
- year_from=2020, year_to=2024
- doctype=null
- papers_by_field defaults: field_level=1, field_score_min=0.3, top_k=25
- color=null
- mark="bar"
- compare=false
- compare_year_from=null, compare_year_to=null

Color rules:
- If user requests a color, set color to a CSS color string (e.g., "red", "blue", "#ff0000", "crimson").
- Otherwise set color to null.

Mark rules:
- If user requests a chart type, set mark to one of: "bar", "line", "area".
- Examples: "use a line chart", "show trend" -> "line"; "area chart" -> "area".

Output JSON keys (always include chart_type; others may be null):
chart_type, year_from, year_to, doctype, field_level, field_score_min, top_k, color, mark,
compare, compare_year_from, compare_year_to
""".strip()


def _safe_strip_fences(raw: str) -> str:
    raw = (raw or "").strip()
    if raw.startswith("```"):
        raw = raw.strip("`").strip()
        if raw.lower().startswith("json"):
            raw = raw[4:].strip()
    return raw


def _is_empty_str(x: Any) -> bool:
    return isinstance(x, str) and not x.strip()


def _parse_compare_ranges(text: str) -> Optional[Tuple[int, int, int, int]]:
    """
    Parses patterns like:
    - compare 2020-2022 vs 2023-2024
    - 2020-2022 versus 2023-2024
    """
    t = (text or "").lower()
    m = re.search(r"(\d{4})\s*-\s*(\d{4}).*?\b(vs|versus|compare)\b.*?(\d{4})\s*-\s*(\d{4})", t)
    if not m:
        return None
    a1, a2, b1, b2 = int(m.group(1)), int(m.group(2)), int(m.group(4)), int(m.group(5))
    return a1, a2, b1, b2


def _parse_top_k(text: str) -> Optional[int]:
    t = (text or "").lower()
    m = re.search(r"\btop[_\s-]*k\s*[:=]?\s*(\d{1,4})\b", t)
    if m:
        return int(m.group(1))
    return None


def _parse_field_score_min(text: str) -> Optional[float]:
    t = (text or "").lower()
    m = re.search(r"\b(field[_\s-]*score[_\s-]*min|threshold|score)\s*[:=]?\s*(0?\.\d+|\d+(\.\d+)?)\b", t)
    if m:
        return float(m.group(2))
    return None


def _parse_field_level(text: str) -> Optional[int]:
    t = (text or "").lower()
    m = re.search(r"\b(field[_\s-]*level|level)\s*[:=]?\s*(\d{1,2})\b", t)
    if m:
        return int(m.group(2))
    return None


def _parse_doctype(text: str) -> Optional[str]:
    t = (text or "").lower()
    for k in ["article", "preprint", "conference", "journal", "proceedings"]:
        if re.search(rf"\b{k}\b", t):
            return k
    return None


def planner(user_text: str, prev_plan: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    model = os.getenv("OPENAI_MODEL", "gpt-4o")

    messages = [{"role": "system", "content": SYSTEM}]
    if prev_plan:
        messages.append({"role": "system", "content": f"prev_plan (JSON): {json.dumps(prev_plan, ensure_ascii=False)}"})
    messages.append({"role": "user", "content": user_text})

    resp = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=0,
        response_format={"type": "json_object"},
    )

    raw = _safe_strip_fences(resp.choices[0].message.content or "")
    plan = json.loads(raw)

    # Ensure chart_type exists
    if not plan.get("chart_type"):
        plan["chart_type"] = prev_plan.get("chart_type") if prev_plan else "papers_by_year"

    # Inherit missing keys from prev_plan (including compare)
    if prev_plan:
        inherit_keys = [
            "year_from",
            "year_to",
            "doctype",
            "field_level",
            "field_score_min",
            "top_k",
            "color",
            "mark",
            "compare",
            "compare_year_from",
            "compare_year_to",
        ]
        for k in inherit_keys:
            if k not in plan or plan[k] is None:
                plan[k] = prev_plan.get(k)

    # Fill defaults
    plan.setdefault("year_from", 2020)
    plan.setdefault("year_to", 2024)
    plan.setdefault("doctype", None)
    plan.setdefault("field_level", 1)
    plan.setdefault("field_score_min", 0.3)
    plan.setdefault("top_k", 25)
    plan.setdefault("color", None)
    plan.setdefault("mark", "bar")
    plan.setdefault("compare", False)
    plan.setdefault("compare_year_from", None)
    plan.setdefault("compare_year_to", None)

    # Regex fallback for compare & filters (stabilizes behavior)
    cmp = _parse_compare_ranges(user_text)
    if cmp:
        plan["compare"] = True
        plan["year_from"], plan["year_to"], plan["compare_year_from"], plan["compare_year_to"] = cmp

    tk = _parse_top_k(user_text)
    if tk is not None:
        plan["top_k"] = tk

    fs = _parse_field_score_min(user_text)
    if fs is not None:
        plan["field_score_min"] = fs

    fl = _parse_field_level(user_text)
    if fl is not None:
        plan["field_level"] = fl

    dt = _parse_doctype(user_text)
    if dt is not None:
        plan["doctype"] = dt

    # Normalize empty strings
    if _is_empty_str(plan.get("doctype")):
        plan["doctype"] = None
    if _is_empty_str(plan.get("color")):
        plan["color"] = None
    if _is_empty_str(plan.get("mark")):
        plan["mark"] = "bar"

    # Type normalize
    def _to_int(x: Any, default: int) -> int:
        try:
            return int(x)
        except Exception:
            return default

    def _to_float(x: Any, default: float) -> float:
        try:
            return float(x)
        except Exception:
            return default

    plan["year_from"] = _to_int(plan.get("year_from"), 2020)
    plan["year_to"] = _to_int(plan.get("year_to"), 2024)
    plan["field_level"] = _to_int(plan.get("field_level"), 1)
    plan["field_score_min"] = _to_float(plan.get("field_score_min"), 0.3)
    plan["top_k"] = _to_int(plan.get("top_k"), 25)

    # Normalize mark
    if plan.get("mark") not in ("bar", "line", "area"):
        plan["mark"] = "bar"

    # Normalize compare
    plan["compare"] = bool(plan.get("compare", False))
    if plan["compare"]:
        if plan.get("compare_year_from") is None or plan.get("compare_year_to") is None:
            plan["compare"] = False
            plan["compare_year_from"] = None
            plan["compare_year_to"] = None
        else:
            plan["compare_year_from"] = _to_int(plan.get("compare_year_from"), None)  # type: ignore[arg-type]
            plan["compare_year_to"] = _to_int(plan.get("compare_year_to"), None)  # type: ignore[arg-type]
            if plan["compare_year_from"] is None or plan["compare_year_to"] is None:
                plan["compare"] = False
                plan["compare_year_from"] = None
                plan["compare_year_to"] = None
    else:
        plan["compare_year_from"] = None
        plan["compare_year_to"] = None

    return plan


def _year_rows(year_from: int, year_to: int, doctype: Optional[str]) -> List[Dict[str, Any]]:
    rows = papers_by_year(year_from, year_to, doctype)
    # Ensure continuous years in [year_from, year_to]
    m = {int(y): int(n) for y, n in rows}
    out = []
    for y in range(year_from, year_to + 1):
        out.append({"year": y, "n_papers": int(m.get(y, 0))})
    return out


def _field_rows(
    year_from: int,
    year_to: int,
    doctype: Optional[str],
    field_level: int,
    field_score_min: float,
    top_k: int,
) -> List[Dict[str, Any]]:
    rows = papers_by_field(
        year_from,
        year_to,
        level=field_level,
        field_score_min=field_score_min,
        doctype=doctype,
        top_k=top_k,
    )
    return [{"field": str(f), "n_papers": int(n)} for f, n in rows]


def data_agent(plan: Dict[str, Any]) -> Dict[str, Any]:
    chart_type: ChartType = plan["chart_type"]
    year_from = int(plan.get("year_from", 2020))
    year_to = int(plan.get("year_to", 2024))
    doctype: Optional[str] = plan.get("doctype") or None

    compare = bool(plan.get("compare", False))
    c_from = plan.get("compare_year_from")
    c_to = plan.get("compare_year_to")

    if chart_type == "papers_by_year":
        if not compare:
            data = _year_rows(year_from, year_to, doctype)
            return {"chart_type": chart_type, "plan": plan, "data": data}

        a = _year_rows(year_from, year_to, doctype)
        b = _year_rows(int(c_from), int(c_to), doctype)

        data: List[Dict[str, Any]] = []
        for r in a:
            data.append({"group": "A", **r})
        for r in b:
            data.append({"group": "B", **r})
        return {"chart_type": chart_type, "plan": plan, "data": data}

    if chart_type == "papers_by_field":
        field_level = int(plan.get("field_level", 1))
        field_score_min = float(plan.get("field_score_min", 0.3))
        top_k = int(plan.get("top_k", 25))

        if not compare:
            data = _field_rows(year_from, year_to, doctype, field_level, field_score_min, top_k)
            return {"chart_type": chart_type, "plan": plan, "data": data}


        pool = max(top_k * 5, 200)

        a_rows = _field_rows(year_from, year_to, doctype, field_level, field_score_min, pool)
        b_rows = _field_rows(int(c_from), int(c_to), doctype, field_level, field_score_min, pool)

        a_map = {r["field"]: int(r["n_papers"]) for r in a_rows}
        b_map = {r["field"]: int(r["n_papers"]) for r in b_rows}

        fields = set(a_map.keys()) | set(b_map.keys())
        ranked = sorted(fields, key=lambda f: (a_map.get(f, 0) + b_map.get(f, 0), a_map.get(f, 0), b_map.get(f, 0)), reverse=True)
        keep = ranked[:top_k]

        data: List[Dict[str, Any]] = []
        for f in keep:
            data.append({"group": "A", "field": f, "n_papers": int(a_map.get(f, 0))})
        for f in keep:
            data.append({"group": "B", "field": f, "n_papers": int(b_map.get(f, 0))})

        return {"chart_type": chart_type, "plan": plan, "data": data}

    raise ValueError(f"Unsupported chart_type: {chart_type}")


def viz_agent(payload: Dict[str, Any]) -> Dict[str, Any]:
    chart_type: ChartType = payload["chart_type"]
    data = payload["data"]
    plan = payload["plan"]

    color = plan.get("color") or None
    mark_type: MarkType = plan.get("mark") or "bar"
    compare = bool(plan.get("compare", False))

    mark: Dict[str, Any] = {"type": mark_type, "tooltip": True}
    if (not compare) and color:
        mark["color"] = color

    if chart_type == "papers_by_year":
        params = []
        encoding: Dict[str, Any] = {
            "x": {"field": "year", "type": "ordinal", "title": "Year"},
            "y": {"field": "n_papers", "type": "quantitative", "title": "Papers"},
        }

        if compare:
            encoding["color"] = {"field": "group", "type": "nominal", "title": "Group"}
            params = [{"name": "pick", "select": {"type": "point", "fields": ["group", "year"]}}]
            encoding["opacity"] = {"condition": {"param": "pick", "value": 1}, "value": 0.35}
            encoding["tooltip"] = [{"field": "group"}, {"field": "year"}, {"field": "n_papers"}]
        else:
            params = [{"name": "pick", "select": {"type": "point", "fields": ["year"]}}]
            encoding["opacity"] = {"condition": {"param": "pick", "value": 1}, "value": 0.35}
            encoding["tooltip"] = [{"field": "year"}, {"field": "n_papers"}]

        spec = {
            "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
            "description": "Number of Dartmouth papers by year",
            "data": {"values": data},
            "params": params,
            "mark": mark,
            "encoding": encoding,
        }

        if compare:
            answer = (
                f"Papers by year (A={plan.get('year_from')}–{plan.get('year_to')}, "
                f"B={plan.get('compare_year_from')}–{plan.get('compare_year_to')})."
            )
        else:
            answer = f"Papers by year ({plan.get('year_from')}–{plan.get('year_to')})."

        return {"answer": answer, "plan": plan, "data": data, "vegaLiteSpec": spec}

    if chart_type == "papers_by_field":
        params = [{"name": "pick", "select": {"type": "point", "fields": ["field"]}}]

        encoding: Dict[str, Any] = {
            "x": {"field": "field", "type": "nominal", "sort": "-y", "title": "Field"},
            "y": {"field": "n_papers", "type": "quantitative", "title": "Papers"},
        }

        if compare:
            encoding["color"] = {"field": "group", "type": "nominal", "title": "Group"}
            encoding["opacity"] = {"condition": {"param": "pick", "value": 1}, "value": 0.35}
            encoding["tooltip"] = [{"field": "group"}, {"field": "field"}, {"field": "n_papers"}]
        else:
            encoding["opacity"] = {"condition": {"param": "pick", "value": 1}, "value": 0.35}
            encoding["tooltip"] = [{"field": "field"}, {"field": "n_papers"}]

        spec = {
            "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
            "description": "Number of Dartmouth papers by field",
            "data": {"values": data},
            "params": params,
            "mark": mark,
            "encoding": encoding,
        }

        if compare:
            answer = (
                f"Papers by field (A={plan.get('year_from')}–{plan.get('year_to')}, "
                f"B={plan.get('compare_year_from')}–{plan.get('compare_year_to')}, "
                f"level={plan.get('field_level')}, score>={plan.get('field_score_min')}, top_k={plan.get('top_k')})."
            )
        else:
            answer = (
                f"Papers by field ({plan.get('year_from')}–{plan.get('year_to')}, "
                f"level={plan.get('field_level')}, score>={plan.get('field_score_min')}, top_k={plan.get('top_k')})."
            )

        return {"answer": answer, "plan": plan, "data": data, "vegaLiteSpec": spec}

    raise ValueError(f"Unsupported chart_type: {chart_type}")


def run_multi_agent(user_text: str, prev_plan: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    plan = planner(user_text, prev_plan=prev_plan)
    payload = data_agent(plan)
    return viz_agent(payload)
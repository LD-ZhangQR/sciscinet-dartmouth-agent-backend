# SciSciNet Dartmouth Agent Backend

This repository contains the backend for Project 2: a chat-driven dashboard for exploring Dartmouth-related publication statistics derived from SciSciNet. The backend exposes an API that converts natural language requests into (1) a structured query plan, (2) aggregated chart data, and (3) a Vega-Lite specification for visualization.

The main goal is to support multi-turn interactions where users can iteratively refine a chart (filters, styling, and compare mode) without restating everything.

⸻

## Architecture Overview
```bash
The backend implements a simple multi-stage agent pipeline:
	1.	Planner / Router (LLM)
	•	Parses user text into a structured plan (plan)
	•	Supports multi-turn chat by inheriting from prev_plan
	2.	Data Agent
	•	Executes SciSciNet queries based on the plan
	•	Returns aggregated results
	3.	Visualization Agent
	•	Converts the aggregated data into a Vega-Lite spec
	•	Applies styling and compare-mode encoding
```
⸻

### Supported Charts
```bash
	•	papers_by_year
	•	Paper counts grouped by year
	•	papers_by_field
	•	Paper counts grouped by field name
```
⸻

### Supported Parameters

#### Core parameters
```bash
	•	year_from, year_to
	•	doctype (optional, e.g., article, preprint)
```
#### Field-chart parameters
```bash
	•	field_level
	•	field_score_min
	•	top_k (top K fields by paper count after filtering)
```
#### Styling
```bash
	•	color (e.g., purple, crimson)
	•	mark (bar, line, area)
```
#### Compare mode (two time ranges)
```bash
	•	compare (true / false)
	•	compare_year_from, compare_year_to
```
When compare mode is enabled, the returned dataset includes a group column (A / B) and the Vega-Lite spec uses color to distinguish groups.

⸻

### Multi-turn Chat (prev_plan)
```bash
The backend supports continuous refinement via prev_plan:
	•	Style-only messages reuse prior non-style parameters
	•	Filter updates modify only the requested fields
	•	Compare mode can be enabled/disabled as a follow-up

This is implemented through the /api/chat endpoint, where the frontend sends the last plan back as prev_plan.
```
⸻

#### Optional “quick chart” endpoints
```bash
	•	POST /api/chart/papers_by_year
	•	POST /api/chart/papers_by_field
```
These are used by the frontend “Quick buttons” and do not require the LLM planner.
⸻

#### Tech Stack
```bash
	•	FastAPI
	•	OpenAI API (LLM planner)
	•	SciSciNet query layer
	•	Vega-Lite (spec generation)
```
⸻

#### Running the Backend

Prerequisites
```bash
	•	Python 3.9+
	•	SciSciNet data available locally
	•	OpenAI API key configured via environment variables
```
Install
```bash
pip install -r requirements.txt
```
Start
```bash
uvicorn app.main:app --reload --port 8004
```
Default URL:
```bash
http://127.0.0.1:8004
```

⸻

SciSciNet Dartmouth Agent Backend

This repository contains the backend for Project 2: a chat-driven dashboard for exploring Dartmouth-related publication statistics derived from SciSciNet. The backend exposes an API that converts natural language requests into (1) a structured query plan, (2) aggregated chart data, and (3) a Vega-Lite specification for visualization.

The main goal is to support multi-turn interactions where users can iteratively refine a chart (filters, styling, and compare mode) without restating everything.

⸻

Architecture Overview

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

⸻

Supported Charts
	•	papers_by_year
	•	Paper counts grouped by year
	•	papers_by_field
	•	Paper counts grouped by field name

⸻

Supported Parameters

Core parameters
	•	year_from, year_to
	•	doctype (optional, e.g., article, preprint)

Field-chart parameters
	•	field_level
	•	field_score_min
	•	top_k (top K fields by paper count after filtering)

Styling
	•	color (e.g., purple, crimson)
	•	mark (bar, line, area)

Compare mode (two time ranges)
	•	compare (true / false)
	•	compare_year_from, compare_year_to

When compare mode is enabled, the returned dataset includes a group column (A / B) and the Vega-Lite spec uses color to distinguish groups.

⸻

Multi-turn Chat (prev_plan)

The backend supports continuous refinement via prev_plan:
	•	Style-only messages reuse prior non-style parameters
	•	Filter updates modify only the requested fields
	•	Compare mode can be enabled/disabled as a follow-up

This is implemented through the /api/chat endpoint, where the frontend sends the last plan back as prev_plan.

⸻

API Endpoints

Health check

GET /health

Response:

{ "ok": true }


⸻

Chat agent (main endpoint)

POST /api/chat

Request body:

{
  "message": "Show me papers by field from 2020 to 2024",
  "prev_plan": { }
}

Response:

{
  "answer": "...",
  "plan": { ... },
  "data": [ ... ],
  "vegaLiteSpec": { ... }
}


⸻

Optional “quick chart” endpoints
	•	POST /api/chart/papers_by_year
	•	POST /api/chart/papers_by_field

These are used by the frontend “Quick buttons” and do not require the LLM planner.

⸻

Tech Stack
	•	FastAPI
	•	OpenAI API (LLM planner)
	•	SciSciNet query layer
	•	Vega-Lite (spec generation)

⸻

Running the Backend

Prerequisites
	•	Python 3.9+
	•	SciSciNet data available locally
	•	OpenAI API key configured via environment variables

Install

pip install -r requirements.txt

Start

uvicorn app.main:app --reload --port 8004

Default URL:

http://127.0.0.1:8004


⸻

Security Notes
	•	This repository contains no secrets (no API keys).
	•	Configure keys locally via environment variables (e.g., a local .env file that is not committed).

⸻

Recommended Test Script (for grading)
	1.	Basic year chart:
	•	“Show me papers by year from 2020 to 2024.”
	2.	Style follow-up:
	•	“Make it purple.”
	3.	Mark follow-up:
	•	“Use a line chart.”
	4.	Compare mode:
	•	“Compare 2020–2022 vs 2023–2024.”
	5.	Field chart + filters:
	•	“Show me papers by field from 2020 to 2024, top 10, score threshold 0.4.”
	6.	Compare field chart:
	•	“Compare 2020–2022 vs 2023–2024.”

⸻

import duckdb
from pathlib import Path
from typing import Optional, Literal

ROOT = Path(__file__).resolve().parents[1]
DERIVED = ROOT / "data" / "derived"

FIELD_SCORE_MIN_DEFAULT = 0.3

def _con():
    con = duckdb.connect()
    con.execute("PRAGMA threads=8;")
    return con

def papers_by_year(year_from: int, year_to: int, doctype: Optional[str] = None):
    con = _con()
    p = (DERIVED / "dartmouth_papers.parquet").as_posix()
    where = "year BETWEEN ? AND ?"
    params = [year_from, year_to]
    if doctype:
        where += " AND doctype = ?"
        params.append(doctype)

    q = f"""
    SELECT year, COUNT(*) AS n_papers
    FROM read_parquet('{p}')
    WHERE {where}
    GROUP BY year
    ORDER BY year
    """
    return con.execute(q, params).fetchall()

def papers_by_field(
    year_from: int,
    year_to: int,
    level: int = 1,
    field_score_min: float = FIELD_SCORE_MIN_DEFAULT,
    doctype: Optional[str] = None,
    top_k: int = 30,
):
    con = _con()
    papers = (DERIVED / "dartmouth_papers.parquet").as_posix()
    pf = (DERIVED / "dartmouth_paperfields.parquet").as_posix()
    fields = (DERIVED / "fields.parquet").as_posix()

    where = "p.year BETWEEN ? AND ? AND pf.score_openalex >= ? AND f.level = ?"
    params = [year_from, year_to, field_score_min, level]

    if doctype:
        where += " AND p.doctype = ?"
        params.append(doctype)

    q = f"""
    SELECT f.display_name AS field, COUNT(DISTINCT p.paperid) AS n_papers
    FROM read_parquet('{papers}') p
    JOIN read_parquet('{pf}') pf ON p.paperid = pf.paperid
    JOIN read_parquet('{fields}') f ON pf.fieldid = f.fieldid
    WHERE {where}
    GROUP BY f.display_name
    ORDER BY n_papers DESC
    LIMIT {int(top_k)}
    """
    return con.execute(q, params).fetchall()

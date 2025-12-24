import duckdb
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
OUT = ROOT / "data" / "derived"
OUT.mkdir(parents=True, exist_ok=True)

INSTITUTION_IDS = [
    "I1289422878",  # Dartmouth–Hitchcock Medical Center
    "I4210144121",  # Children's Hospital at Dartmouth Hitchcock
    "I4390039367",  # Dartmouth Cancer Center
    "I126688049",   # Dartmouth Institute for Health Policy and Clinical Practice
    "I4390039337",  # Dartmouth Health
    "I107672454",   # Dartmouth College
]

YEAR_MIN_HARD = 1600
YEAR_MAX_HARD = 2025

def main():
    con = duckdb.connect()
    con.execute("PRAGMA threads=8;")

    paa = (RAW / "sciscinet_paper_author_affiliation.parquet").as_posix()
    papers = (RAW / "sciscinet_papers.parquet").as_posix()
    paperfields = (RAW / "sciscinet_paperfields.parquet").as_posix()
    fields = (RAW / "sciscinet_fields.parquet").as_posix()

    con.execute(
        f"""
        COPY (
          SELECT DISTINCT paperid
          FROM read_parquet('{paa}')
          WHERE institutionid IN ({",".join(["?"]*len(INSTITUTION_IDS))})
        ) TO '{(OUT/'dartmouth_paperids.parquet').as_posix()}' (FORMAT PARQUET);
        """,
        INSTITUTION_IDS,
    )

    con.execute(
        f"""
        COPY (
          SELECT paperid, doi, year, doctype,
                 cited_by_count, citation_count,
                 patent_count, newsfeed_count, nih_count, nsf_count, nct_count,
                 team_size, institution_count
          FROM read_parquet('{papers}')
          WHERE paperid IN (SELECT paperid FROM read_parquet('{(OUT/'dartmouth_paperids.parquet').as_posix()}'))
            AND year BETWEEN {YEAR_MIN_HARD} AND {YEAR_MAX_HARD}
        ) TO '{(OUT/'dartmouth_papers.parquet').as_posix()}' (FORMAT PARQUET);
        """
    )

    con.execute(
        f"""
        COPY (
          SELECT paperid, fieldid, score_openalex
          FROM read_parquet('{paperfields}')
          WHERE paperid IN (SELECT paperid FROM read_parquet('{(OUT/'dartmouth_paperids.parquet').as_posix()}'))
        ) TO '{(OUT/'dartmouth_paperfields.parquet').as_posix()}' (FORMAT PARQUET);
        """
    )

    con.execute(
        f"""
        COPY (
          SELECT fieldid, display_name, level
          FROM read_parquet('{fields}')
        ) TO '{(OUT/'fields.parquet').as_posix()}' (FORMAT PARQUET);
        """
    )

    print("Done. Wrote:")
    for f in ["dartmouth_paperids.parquet", "dartmouth_papers.parquet", "dartmouth_paperfields.parquet", "fields.parquet"]:
        print(" -", OUT / f)

if __name__ == "__main__":
    main()

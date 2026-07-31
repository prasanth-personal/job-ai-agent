import sqlite3
import json
from config.settings import DB_FILE


# ---------------------------------------------------------------------------
# Persistence: SQLite cache of jobs already scored.
#
# Key design choice: we dedupe on (employer_name, job_title), normalized
# (lowercased + stripped), NOT on apply_link. apply_link would be a cleaner
# unique key in theory, but it only survives into score_job if the LLM
# remembers to pass it through as a tool argument — an easy thing for the
# model to drop silently. employer_name + job_title come directly out of
# search_jobs's own return value, so the cache lookup doesn't depend on the
# LLM's discipline at all.
# ---------------------------------------------------------------------------

def init_db():
    conn = sqlite3.connect(DB_FILE)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS scored_jobs (
            job_key TEXT PRIMARY KEY,
            job_title TEXT,
            employer_name TEXT,
            location TEXT,
            apply_link TEXT,
            match TEXT,
            score INTEGER,
            matched_skills TEXT,
            missing_skills TEXT,
            scored_at TEXT
        )
    """)
    conn.commit()
    conn.close()


def make_job_key(employer_name: str, job_title: str) -> str:
    """Normalize employer+title into a stable dedupe key."""
    return f"{(employer_name or '').strip().lower()}|||{(job_title or '').strip().lower()}"


def get_cached_score(employer_name: str, job_title: str) -> dict | None:
    """Return a previously stored score dict if this job was already scored,
    else None."""
    key = make_job_key(employer_name, job_title)
    conn = sqlite3.connect(DB_FILE)
    row = conn.execute(
        "SELECT match, score, matched_skills, missing_skills FROM scored_jobs WHERE job_key = ?",
        (key,)
    ).fetchone()
    conn.close()
    if row is None:
        return None
    match, score, matched_json, missing_json = row
    return {
        "match": match,
        "score": score,
        "matched_skills": json.loads(matched_json),
        "missing_skills": json.loads(missing_json),
        "note": "Loaded from cache — not re-scored",
    }


def save_score(employer_name: str, job_title: str, location: str, apply_link: str, result: dict):
    """Persist a freshly computed score so future runs can skip re-scoring."""
    key = make_job_key(employer_name, job_title)
    conn = sqlite3.connect(DB_FILE)
    conn.execute("""
        INSERT OR REPLACE INTO scored_jobs
        (job_key, job_title, employer_name, location, apply_link, match, score,
         matched_skills, missing_skills, scored_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
    """, (
        key, job_title, employer_name, location, apply_link,
        result.get("match"), result.get("score"),
        json.dumps(result.get("matched_skills", [])),
        json.dumps(result.get("missing_skills", [])),
    ))
    conn.commit()
    conn.close()


def is_already_scored(employer_name: str, job_title: str) -> bool:
    key = make_job_key(employer_name, job_title)
    conn = sqlite3.connect(DB_FILE)
    row = conn.execute("SELECT 1 FROM scored_jobs WHERE job_key = ?", (key,)).fetchone()
    conn.close()
    return row is not None
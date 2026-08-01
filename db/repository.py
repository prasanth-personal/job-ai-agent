import json
from db.connection import get_connection


# ---------------------------------------------------------------------------
# Persistence: Postgres cache of jobs already scored.
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
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
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
            scored_at TIMESTAMP
        )
    """)
    conn.commit()
    cur.close()
    conn.close()


def make_job_key(employer_name: str, job_title: str) -> str:
    """Normalize employer+title into a stable dedupe key."""
    return f"{(employer_name or '').strip().lower()}|||{(job_title or '').strip().lower()}"


def get_cached_score(employer_name: str, job_title: str) -> dict | None:
    """Return a previously stored score dict if this job was already scored,
    else None."""
    key = make_job_key(employer_name, job_title)
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT match, score, matched_skills, missing_skills FROM scored_jobs WHERE job_key = %s",
        (key,)
    )
    row = cur.fetchone()
    cur.close()
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
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO scored_jobs
        (job_key, job_title, employer_name, location, apply_link, match, score,
         matched_skills, missing_skills, scored_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
        ON CONFLICT (job_key) DO UPDATE SET
            job_title = EXCLUDED.job_title,
            employer_name = EXCLUDED.employer_name,
            location = EXCLUDED.location,
            apply_link = EXCLUDED.apply_link,
            match = EXCLUDED.match,
            score = EXCLUDED.score,
            matched_skills = EXCLUDED.matched_skills,
            missing_skills = EXCLUDED.missing_skills,
            scored_at = EXCLUDED.scored_at
    """, (
        key, job_title, employer_name, location, apply_link,
        result.get("match"), result.get("score"),
        json.dumps(result.get("matched_skills", [])),
        json.dumps(result.get("missing_skills", [])),
    ))
    conn.commit()
    cur.close()
    conn.close()


def is_already_scored(employer_name: str, job_title: str) -> bool:
    key = make_job_key(employer_name, job_title)
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM scored_jobs WHERE job_key = %s", (key,))
    row = cur.fetchone()
    cur.close()
    conn.close()
    return row is not None
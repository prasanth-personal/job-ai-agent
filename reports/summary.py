import sqlite3
from config.settings import DB_FILE


def print_real_summary():
    """Ground truth summary, pulled directly from the database — NOT from
    the LLM's final chat message, which can hallucinate when it has no
    new jobs to report on."""
    conn = sqlite3.connect(DB_FILE)
    rows = conn.execute("""
        SELECT job_title, employer_name, match, score, apply_link
        FROM scored_jobs
        WHERE match IN ('High', 'Medium')
        ORDER BY score DESC
        LIMIT 10
    """).fetchall()
    conn.close()

    print("\n--- REAL TOP MATCHES (from database, not LLM memory) ---")
    if not rows:
        print("  No High/Medium matches found yet across any run.")
        return
    for title, employer, match, score, link in rows:
        print(f"  [{match} - {score}] {title} @ {employer}")
        print(f"    Apply: {link}")
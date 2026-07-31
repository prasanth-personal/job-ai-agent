import sqlite3
from datetime import datetime
from config.settings import DB_FILE
from db.repository import make_job_key


def init_applications_table():
    """Separate from scored_jobs — 'found and scored' and 'actually applied'
    are different facts that change independently."""
    conn = sqlite3.connect(DB_FILE)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS applications (
            job_key TEXT PRIMARY KEY,
            job_title TEXT,
            employer_name TEXT,
            apply_link TEXT,
            status TEXT DEFAULT 'Not Applied',
            applied_date TEXT,
            last_updated TEXT
        )
    """)
    conn.commit()
    conn.close()


def mark_applied(employer_name: str, job_title: str, apply_link: str = ""):
    """Marks a job as applied, stamping today's date."""
    key = make_job_key(employer_name, job_title)
    today = datetime.now().strftime("%Y-%m-%d")
    conn = sqlite3.connect(DB_FILE)
    conn.execute("""
        INSERT OR REPLACE INTO applications
        (job_key, job_title, employer_name, apply_link, status, applied_date, last_updated)
        VALUES (?, ?, ?, ?, 'Applied', ?, ?)
    """, (key, job_title, employer_name, apply_link, today, today))
    conn.commit()
    conn.close()


def update_status(employer_name: str, job_title: str, new_status: str):
    """Updates status for an existing application row
    (e.g. 'Interview', 'Rejected', 'Offer')."""
    key = make_job_key(employer_name, job_title)
    today = datetime.now().strftime("%Y-%m-%d")
    conn = sqlite3.connect(DB_FILE)
    conn.execute("""
        UPDATE applications SET status = ?, last_updated = ? WHERE job_key = ?
    """, (new_status, today, key))
    conn.commit()
    conn.close()


def get_application_status(employer_name: str, job_title: str) -> str:
    """Returns the current status, or 'Not Applied' if never touched."""
    key = make_job_key(employer_name, job_title)
    conn = sqlite3.connect(DB_FILE)
    row = conn.execute(
        "SELECT status FROM applications WHERE job_key = ?", (key,)
    ).fetchone()
    conn.close()
    return row[0] if row else "Not Applied"


def get_stale_applications(days_threshold: int = 5) -> list[dict]:
    """Jobs applied to more than days_threshold days ago with no update
    since — candidates for a 'still no response?' nudge."""
    conn = sqlite3.connect(DB_FILE)
    rows = conn.execute("""
        SELECT job_title, employer_name, applied_date, apply_link
        FROM applications
        WHERE status = 'Applied' AND applied_date <= date('now', ?)
    """, (f"-{days_threshold} day",)).fetchall()
    conn.close()
    return [
        {"job_title": t, "employer_name": e, "applied_date": d, "apply_link": l}
        for t, e, d, l in rows
    ]
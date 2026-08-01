from datetime import datetime
from db.connection import get_connection
from db.repository import make_job_key


def init_applications_table():
    """Separate from scored_jobs — 'found and scored' and 'actually applied'
    are different facts that change independently."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS applications (
            job_key TEXT PRIMARY KEY,
            job_title TEXT,
            employer_name TEXT,
            apply_link TEXT,
            status TEXT DEFAULT 'Not Applied',
            applied_date DATE,
            last_updated DATE
        )
    """)
    conn.commit()
    cur.close()
    conn.close()


def mark_applied(employer_name: str, job_title: str, apply_link: str = ""):
    """Marks a job as applied, stamping today's date."""
    key = make_job_key(employer_name, job_title)
    today = datetime.now().strftime("%Y-%m-%d")
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO applications
        (job_key, job_title, employer_name, apply_link, status, applied_date, last_updated)
        VALUES (%s, %s, %s, %s, 'Applied', %s, %s)
        ON CONFLICT (job_key) DO UPDATE SET
            job_title = EXCLUDED.job_title,
            employer_name = EXCLUDED.employer_name,
            apply_link = EXCLUDED.apply_link,
            status = 'Applied',
            applied_date = EXCLUDED.applied_date,
            last_updated = EXCLUDED.last_updated
    """, (key, job_title, employer_name, apply_link, today, today))
    conn.commit()
    cur.close()
    conn.close()


def update_status(employer_name: str, job_title: str, new_status: str):
    """Updates status for an existing application row
    (e.g. 'Interview', 'Rejected', 'Offer')."""
    key = make_job_key(employer_name, job_title)
    today = datetime.now().strftime("%Y-%m-%d")
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "UPDATE applications SET status = %s, last_updated = %s WHERE job_key = %s",
        (new_status, today, key)
    )
    conn.commit()
    cur.close()
    conn.close()


def get_application_status(employer_name: str, job_title: str) -> str:
    """Returns the current status, or 'Not Applied' if never touched."""
    key = make_job_key(employer_name, job_title)
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT status FROM applications WHERE job_key = %s", (key,))
    row = cur.fetchone()
    cur.close()
    conn.close()
    return row[0] if row else "Not Applied"


def get_stale_applications(days_threshold: int = 5) -> list[dict]:
    """Jobs applied to more than days_threshold days ago with no update
    since — candidates for a 'still no response?' nudge."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT job_title, employer_name, applied_date, apply_link
        FROM applications
        WHERE status = 'Applied' AND applied_date <= CURRENT_DATE - %s * INTERVAL '1 day'
    """, (days_threshold,))
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return [
        {"job_title": t, "employer_name": e, "applied_date": d, "apply_link": l}
        for t, e, d, l in rows
    ]
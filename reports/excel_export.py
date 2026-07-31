import sqlite3
import json
from datetime import date
import pandas as pd
from config.settings import DB_FILE


def export_to_excel(filename: str = None) -> str:
    """Pull every scored job out of SQLite, join with application status,
    and write to a date-stamped Excel file. Returns the actual filename
    used, so callers (e.g. the email sender) know exactly what was created."""
    if filename is None:
        filename = f"jobs_report_{date.today().isoformat()}.xlsx"

    conn = sqlite3.connect(DB_FILE)
    df = pd.read_sql_query("""
        SELECT s.job_title, s.employer_name, s.location, s.match, s.score,
               s.matched_skills, s.missing_skills, s.apply_link, s.scored_at,
               COALESCE(a.status, 'Not Applied') AS application_status
        FROM scored_jobs s
        LEFT JOIN applications a ON s.job_key = a.job_key
        ORDER BY s.score DESC
    """, conn)
    conn.close()

    if df.empty:
        print("No scored jobs in the database yet — nothing to export.")
        return None

    df["matched_skills"] = df["matched_skills"].apply(lambda x: ", ".join(json.loads(x)) if x else "")
    df["missing_skills"] = df["missing_skills"].apply(lambda x: ", ".join(json.loads(x)) if x else "")

    df.to_excel(filename, index=False)
    print(f"Exported {len(df)} scored jobs to {filename}")
    return filename
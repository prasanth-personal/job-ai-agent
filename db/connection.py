import psycopg2
import os

PGHOST = os.getenv("PGHOST")
PGPORT = os.getenv("PGPORT", "5432")
PGDATABASE = os.getenv("PGDATABASE")
PGUSER = os.getenv("PGUSER")
PGPASSWORD = os.getenv("PGPASSWORD")


def get_connection():
    """Single place that knows how to connect to Postgres — every DB
    module imports this instead of hardcoding sqlite3.connect(DB_FILE).
    Makes it trivial to see/change connection behavior in one spot."""
    return psycopg2.connect(
        host=PGHOST,
        port=PGPORT,
        dbname=PGDATABASE,
        user=PGUSER,
        password=PGPASSWORD,
    )
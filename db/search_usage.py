from db.connection import get_connection

ADZUNA_MONTHLY_LIMIT = 1000   # Adzuna free tier — verify against your dashboard
JSEARCH_MONTHLY_LIMIT = 200   # RapidAPI/JSearch — check your actual plan, this varies by account


def init_search_usage_table():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS search_api_usage (
            id SERIAL PRIMARY KEY,
            api_name TEXT NOT NULL,
            timestamp TIMESTAMP NOT NULL
        )
    """)
    conn.commit()
    cur.close()
    conn.close()


def record_search_call(api_name: str):
    """api_name: 'jsearch' or 'adzuna'. Call once per actual network
    request — not on cache hits, since those don't touch the vendor's quota."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO search_api_usage (api_name, timestamp) VALUES (%s, NOW())",
        (api_name,)
    )
    conn.commit()
    cur.close()
    conn.close()


def get_usage_this_month(api_name: str) -> int:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT COUNT(*) FROM search_api_usage
        WHERE api_name = %s
        AND date_trunc('month', timestamp) = date_trunc('month', NOW())
    """, (api_name,))
    count = cur.fetchone()[0]
    cur.close()
    conn.close()
    return count


def get_usage_summary() -> dict:
    return {
        "jsearch": {"month": get_usage_this_month("jsearch"), "limit": JSEARCH_MONTHLY_LIMIT},
        "adzuna": {"month": get_usage_this_month("adzuna"), "limit": ADZUNA_MONTHLY_LIMIT},
    }
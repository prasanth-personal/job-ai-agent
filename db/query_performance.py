from db.connection import get_connection


def init_query_performance_table():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS query_performance (
            query TEXT PRIMARY KEY,
            high_count INTEGER NOT NULL DEFAULT 0,
            medium_count INTEGER NOT NULL DEFAULT 0,
            low_count INTEGER NOT NULL DEFAULT 0,
            total_scored INTEGER NOT NULL DEFAULT 0,
            last_used TIMESTAMP
        )
    """)
    conn.commit()
    cur.close()
    conn.close()


def record_query_outcome(query: str, match: str):
    """Track how a query's results actually scored, so future runs can
    weight toward queries that have historically produced High matches."""
    if not query:
        return
    column = {"High": "high_count", "Medium": "medium_count", "Low": "low_count"}.get(match, "low_count")
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(f"""
        INSERT INTO query_performance (query, {column}, total_scored, last_used)
        VALUES (%s, 1, 1, NOW())
        ON CONFLICT (query) DO UPDATE SET
            {column} = query_performance.{column} + 1,
            total_scored = query_performance.total_scored + 1,
            last_used = NOW()
    """, (query,))
    conn.commit()
    cur.close()
    conn.close()


def get_query_scores(queries: list[str]) -> dict[str, float]:
    """Weight = a query's historical High-match rate. Untried queries get
    a neutral default so they still get picked sometimes (exploration)."""
    if not queries:
        return {}
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT query, high_count, total_scored FROM query_performance WHERE query = ANY(%s)",
        (queries,)
    )
    rows = {q: (h, t) for q, h, t in cur.fetchall()}
    cur.close()
    conn.close()

    DEFAULT_WEIGHT = 0.3
    scores = {}
    for q in queries:
        if q in rows:
            high, total = rows[q]
            scores[q] = (high / total) if total > 0 else DEFAULT_WEIGHT
        else:
            scores[q] = DEFAULT_WEIGHT
    return scores
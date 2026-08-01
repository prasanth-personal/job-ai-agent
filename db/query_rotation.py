from db.connection import get_connection


def init_query_rotation_table():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS query_rotation (
            role_family TEXT PRIMARY KEY,
            last_index INTEGER NOT NULL DEFAULT -1
        )
    """)
    conn.commit()
    cur.close()
    conn.close()


def get_next_queries_for_family(role_family: str, family_queries: list[str], n: int) -> list[str]:
    if not family_queries or n <= 0:
        return []

    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO query_rotation (role_family, last_index) VALUES (%s, -1) ON CONFLICT (role_family) DO NOTHING",
        (role_family,)
    )
    cur.execute("SELECT last_index FROM query_rotation WHERE role_family = %s", (role_family,))
    row = cur.fetchone()
    last_index = row[0] if row else -1

    total = len(family_queries)
    n = min(n, total)

    selected = []
    idx = last_index
    for _ in range(n):
        idx = (idx + 1) % total
        selected.append(family_queries[idx])

    cur.execute("UPDATE query_rotation SET last_index = %s WHERE role_family = %s", (idx, role_family))
    conn.commit()
    cur.close()
    conn.close()

    return selected


def get_next_queries(all_queries: list[str], n: int) -> list[str]:
    """Legacy flat rotation — kept for the fallback path (static
    SEARCH_QUERIES list, which has no role_family labels)."""
    return get_next_queries_for_family("__flat__", all_queries, n)
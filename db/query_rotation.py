import random
from db.connection import get_connection
from db.query_performance import get_query_scores
from utils.logger import get_logger

log = get_logger()

MIN_WEIGHT_FLOOR = 0.05  # a query never hits zero odds — keeps exploration alive


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
    """Weighted-random pick, favoring queries with a higher historical
    High-match rate — replaces the old pure round-robin cursor."""
    if not family_queries or n <= 0:
        return []

    n = min(n, len(family_queries))
    scores = get_query_scores(family_queries)

    pool = list(family_queries)
    weights = [max(scores.get(q, 0.3), MIN_WEIGHT_FLOOR) for q in pool]

    selected = []
    for _ in range(n):
        pick = random.choices(pool, weights=weights, k=1)[0]
        idx = pool.index(pick)
        selected.append(pool.pop(idx))
        weights.pop(idx)

    log.info(f"Query weights for '{role_family}': " + ", ".join(f"{q}={scores.get(q, 0.3):.2f}" for q in family_queries))
    return selected


def get_next_queries(all_queries: list[str], n: int) -> list[str]:
    """Legacy flat fallback — now also weighted, same as above."""
    return get_next_queries_for_family("__flat__", all_queries, n)
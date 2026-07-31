import sqlite3
from datetime import datetime, timedelta
from config.settings import DB_FILE

# Free-tier limits for llama-3.3-70b-versatile, from Groq's rate limits page.
RPM_LIMIT = 30
RPD_LIMIT = 1000
TPM_LIMIT = 12000
TPD_LIMIT = 100000

# Safety margin — stop BEFORE hitting the exact ceiling, not at it.
SAFETY_MARGIN = 0.9


def init_usage_table():
    conn = sqlite3.connect(DB_FILE)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS groq_usage (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            prompt_tokens INTEGER,
            completion_tokens INTEGER,
            total_tokens INTEGER
        )
    """)
    conn.commit()
    conn.close()


def record_usage(prompt_tokens: int, completion_tokens: int, total_tokens: int):
    """Logs one LLM call's real token usage, pulled from
    response.response_metadata['token_usage'] after each call."""
    conn = sqlite3.connect(DB_FILE)
    conn.execute("""
        INSERT INTO groq_usage (timestamp, prompt_tokens, completion_tokens, total_tokens)
        VALUES (?, ?, ?, ?)
    """, (datetime.now().isoformat(), prompt_tokens, completion_tokens, total_tokens))
    conn.commit()
    conn.close()


def get_usage_last_minute() -> dict:
    """Sums tokens and counts requests in the trailing 60 seconds — this is
    your live TPM/RPM check."""
    cutoff = (datetime.now() - timedelta(seconds=60)).isoformat()
    conn = sqlite3.connect(DB_FILE)
    row = conn.execute("""
        SELECT COALESCE(SUM(total_tokens), 0), COUNT(*)
        FROM groq_usage WHERE timestamp >= ?
    """, (cutoff,)).fetchone()
    conn.close()
    return {"tokens": row[0], "requests": row[1]}


def get_usage_today() -> dict:
    """Sums tokens and counts requests for today — this is your TPD/RPD check."""
    today_prefix = datetime.now().strftime("%Y-%m-%d")
    conn = sqlite3.connect(DB_FILE)
    row = conn.execute("""
        SELECT COALESCE(SUM(total_tokens), 0), COUNT(*)
        FROM groq_usage WHERE timestamp LIKE ?
    """, (f"{today_prefix}%",)).fetchone()
    conn.close()
    return {"tokens": row[0], "requests": row[1]}


def can_make_request(estimated_tokens: int = 1000) -> tuple[bool, str]:
    """Gatekeeper — check BEFORE making a call whether it's safe to proceed,
    using a 90% safety margin so we stop before actually hitting a 429,
    not after."""
    minute = get_usage_last_minute()
    today = get_usage_today()

    if minute["requests"] + 1 > RPM_LIMIT * SAFETY_MARGIN:
        return False, f"Would exceed RPM safety margin ({minute['requests']}/{RPM_LIMIT} this minute)"

    if minute["tokens"] + estimated_tokens > TPM_LIMIT * SAFETY_MARGIN:
        return False, f"Would exceed TPM safety margin ({minute['tokens']}/{TPM_LIMIT} this minute)"

    if today["requests"] + 1 > RPD_LIMIT * SAFETY_MARGIN:
        return False, f"Would exceed RPD safety margin ({today['requests']}/{RPD_LIMIT} today)"

    if today["tokens"] + estimated_tokens > TPD_LIMIT * SAFETY_MARGIN:
        return False, f"Would exceed TPD safety margin ({today['tokens']}/{TPD_LIMIT} today)"

    return True, "OK"
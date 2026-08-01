from db.connection import get_connection

RPM_LIMIT = 30
RPD_LIMIT = 1000
TPM_LIMIT = 12000
TPD_LIMIT = 100000
SAFETY_MARGIN = 0.9


def init_usage_table():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS groq_usage (
            id SERIAL PRIMARY KEY,
            timestamp TIMESTAMP,
            prompt_tokens INTEGER,
            completion_tokens INTEGER,
            total_tokens INTEGER
        )
    """)
    conn.commit()
    cur.close()
    conn.close()


def record_usage(prompt_tokens: int, completion_tokens: int, total_tokens: int):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO groq_usage (timestamp, prompt_tokens, completion_tokens, total_tokens)
        VALUES (NOW(), %s, %s, %s)
    """, (prompt_tokens, completion_tokens, total_tokens))
    conn.commit()
    cur.close()
    conn.close()


def get_usage_last_minute() -> dict:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT COALESCE(SUM(total_tokens), 0), COUNT(*)
        FROM groq_usage WHERE timestamp >= NOW() - INTERVAL '60 seconds'
    """)
    row = cur.fetchone()
    cur.close()
    conn.close()
    return {"tokens": row[0], "requests": row[1]}


def get_usage_today() -> dict:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT COALESCE(SUM(total_tokens), 0), COUNT(*)
        FROM groq_usage WHERE timestamp::date = CURRENT_DATE
    """)
    row = cur.fetchone()
    cur.close()
    conn.close()
    return {"tokens": row[0], "requests": row[1]}


def can_make_request(estimated_tokens: int = 1000) -> tuple[bool, str]:
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
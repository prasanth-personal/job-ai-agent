import json
from datetime import date, timedelta
from config.settings import GROQ_API_KEY, MY_RESUME, ROLE_FAMILIES, SEARCH_QUERIES
from db.connection import get_connection
from langchain_groq import ChatGroq
from utils.retry import call_llm_with_retry
from utils.logger import get_logger

log = get_logger()

REFRESH_INTERVAL_DAYS = 14


def init_expanded_queries_table():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS expanded_queries (
            id SERIAL PRIMARY KEY,
            role_family TEXT NOT NULL,
            query_text TEXT NOT NULL,
            generated_date DATE NOT NULL
        )
    """)
    conn.commit()
    cur.close()
    conn.close()


def _generate_queries_for_family(role_family: str, description: str) -> list[str]:
    prompt = f"""You are helping generate job search query variations for India job boards.

ROLE FAMILY: {role_family}
DESCRIPTION: {description}

CANDIDATE RESUME (for context on seniority/specialization — stay grounded
in this candidate's real background, don't invent unrelated variations):
{MY_RESUME[:1500]}

Generate 6-8 realistic, distinct search query strings recruiters/job boards
would actually use for this role family in India — vary by seniority
(e.g. Senior, Lead, Architect) and common synonyms, but stay grounded in
the candidate's real background. Each query should be short (3-6 words),
suitable for a job search API's free-text query field.

Reply ONLY with valid JSON, no markdown:
{{"queries": ["query 1", "query 2", ...]}}"""

    llm = ChatGroq(model="llama-3.3-70b-versatile", temperature=0.3, groq_api_key=GROQ_API_KEY)
    try:
        response = call_llm_with_retry(llm, prompt, estimated_tokens=800)
        raw = response.content.strip().strip("`").replace("json", "", 1).strip()
        parsed = json.loads(raw)
        queries = [q.strip() for q in parsed.get("queries", []) if q.strip()]
        return queries
    except Exception as e:
        log.error(f"Query expansion failed for '{role_family}': {e}")
        return []


def refresh_expanded_queries(force: bool = False):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT MAX(generated_date) FROM expanded_queries")
    row = cur.fetchone()
    last_generated = row[0] if row else None

    needs_refresh = force or not last_generated
    if not needs_refresh:
        needs_refresh = (date.today() - last_generated) > timedelta(days=REFRESH_INTERVAL_DAYS)

    if not needs_refresh:
        cur.close()
        conn.close()
        log.info("Expanded query pool is fresh — skipping regeneration")
        return

    log.info("Regenerating expanded query pool via LLM...")
    all_new_queries = []
    for family, description in ROLE_FAMILIES.items():
        queries = _generate_queries_for_family(family, description)
        for q in queries:
            all_new_queries.append((family, q))
        log.info(f"Generated {len(queries)} queries for '{family}'")

    if not all_new_queries:
        log.warning("Query expansion returned nothing this run — keeping existing pool if any")
        cur.close()
        conn.close()
        return

    cur.execute("DELETE FROM expanded_queries")
    today = date.today()
    cur.executemany(
        "INSERT INTO expanded_queries (role_family, query_text, generated_date) VALUES (%s, %s, %s)",
        [(family, q, today) for family, q in all_new_queries]
    )
    conn.commit()
    cur.close()
    conn.close()
    log.info(f"Stored {len(all_new_queries)} expanded queries total")


def get_all_expanded_queries() -> list[str]:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT query_text FROM expanded_queries")
    rows = cur.fetchall()
    cur.close()
    conn.close()
    if not rows:
        return SEARCH_QUERIES
    return [r[0] for r in rows]


def get_queries_grouped_by_family() -> dict[str, list[str]]:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT role_family, query_text FROM expanded_queries")
    rows = cur.fetchall()
    cur.close()
    conn.close()

    if not rows:
        return {"__fallback__": SEARCH_QUERIES}

    grouped: dict[str, list[str]] = {}
    for family, query_text in rows:
        grouped.setdefault(family, []).append(query_text)
    return grouped
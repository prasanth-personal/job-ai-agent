from graph.phase3.search_agent.state import SearchAgentState
from tools.search import search_jobs
from tools.search_adzuna import search_jobs_adzuna
from db.repository import make_job_key
from utils.logger import get_logger

log = get_logger()

MIN_GOOD_JOBS = 3


def generate_query_variant(query: str, attempt: int) -> str:
    """Generate a semantic variant of the query for retry attempts.
    Swaps seniority levels and key synonyms without burning LLM tokens.
    attempt: 0-indexed attempt number (0 = first attempt, 1 = second, etc.)"""
    
    if attempt == 0:
        return query  # First attempt: use original
    
    seniority_map = {
        "senior": ["lead", "principal", "architect"],
        "lead": ["senior", "principal"],
        "principal": ["senior", "architect"],
        "architect": ["principal", "senior"],
        "junior": ["associate", "entry-level"],
    }
    
    synonym_map = {
        "consultant": ["architect", "engineer", "lead"],
        "engineer": ["developer", "architect", "consultant"],
        "developer": ["engineer", "architect"],
    }
    
    words = query.lower().split()
    
    # Try to swap one seniority or synonym word
    for i, word in enumerate(words):
        if word in seniority_map:
            variant = seniority_map[word][(attempt - 1) % len(seniority_map[word])]
            words[i] = variant
            return " ".join(words)
        if word in synonym_map:
            variant = synonym_map[word][(attempt - 1) % len(synonym_map[word])]
            words[i] = variant
            return " ".join(words)
    
    # If no seniority/synonym found, add "Technical" if possible
    if "salesforce" in query.lower() and "technical" not in query.lower():
        return query.replace("Salesforce", "Salesforce Technical", 1)
    
    # Fallback: return original
    return query


def search_step(state: SearchAgentState) -> dict:
    query = state["query"]
    attempts = state["search_attempts"]  # 0-indexed
    
    # On retry attempts, use a query variant instead of the exact same query
    search_query = generate_query_variant(query, attempts)
    
    new_jobs = []

    existing_keys = {
        make_job_key(j.get("employer_name", ""), j.get("job_title", ""))
        for j in state["raw_jobs"]
    }

    try:
        jsearch_results = search_jobs.invoke({"query": search_query}) or []
        new_jobs.extend([j for j in jsearch_results if "info" not in j])
    except Exception as e:
        log.warning(f"SearchAgent: JSearch failed for '{search_query}': {e}")

    try:
        adzuna_results = search_jobs_adzuna.invoke({"query": search_query}) or []
        new_jobs.extend([j for j in adzuna_results if "info" not in j])
    except Exception as e:
        log.warning(f"SearchAgent: Adzuna failed for '{search_query}': {e}")

    deduped_new = [
        j for j in new_jobs
        if make_job_key(j.get("employer_name", ""), j.get("job_title", "")) not in existing_keys
    ]

    combined = state["raw_jobs"] + deduped_new
    new_attempts = attempts + 1
    done = len(combined) >= MIN_GOOD_JOBS or new_attempts >= state["max_attempts"]

    log.info(f"SearchAgent attempt {new_attempts}: searched '{search_query}', found {len(deduped_new)} new, {len(combined)} total, done={done}")

    return {"raw_jobs": combined, "search_attempts": new_attempts, "done": done}


def should_continue_search(state: SearchAgentState) -> str:
    """Search Agent's OWN internal guardrail — completely separate from
    anything at the top level. This agent decides for itself when it's
    satisfied or has hit its own limit."""
    return "done" if state["done"] else "search_step"
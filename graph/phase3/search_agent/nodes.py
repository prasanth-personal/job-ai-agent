from graph.phase3.search_agent.state import SearchAgentState
from tools.search import search_jobs
from tools.search_adzuna import search_jobs_adzuna
from db.repository import make_job_key
from utils.logger import get_logger

log = get_logger()

MIN_GOOD_JOBS = 3


def search_step(state: SearchAgentState) -> dict:
    query = state["query"]
    new_jobs = []

    existing_keys = {
        make_job_key(j.get("employer_name", ""), j.get("job_title", ""))
        for j in state["raw_jobs"]
    }

    try:
        jsearch_results = search_jobs.invoke({"query": query}) or []
        new_jobs.extend([j for j in jsearch_results if "info" not in j])
    except Exception as e:
        log.warning(f"SearchAgent: JSearch failed for '{query}': {e}")

    try:
        adzuna_results = search_jobs_adzuna.invoke({"query": query}) or []
        new_jobs.extend([j for j in adzuna_results if "info" not in j])
    except Exception as e:
        log.warning(f"SearchAgent: Adzuna failed for '{query}': {e}")

    deduped_new = [
        j for j in new_jobs
        if make_job_key(j.get("employer_name", ""), j.get("job_title", "")) not in existing_keys
    ]

    combined = state["raw_jobs"] + deduped_new
    attempts = state["search_attempts"] + 1
    done = len(combined) >= MIN_GOOD_JOBS or attempts >= state["max_attempts"]

    log.info(f"SearchAgent attempt {attempts}: {len(deduped_new)} new, {len(combined)} total, done={done}")

    return {"raw_jobs": combined, "search_attempts": attempts, "done": done}


def should_continue_search(state: SearchAgentState) -> str:
    """Search Agent's OWN internal guardrail — completely separate from
    anything at the top level. This agent decides for itself when it's
    satisfied or has hit its own limit."""
    return "done" if state["done"] else "search_step"
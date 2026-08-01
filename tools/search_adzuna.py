import re
import requests
from config.settings import ADZUNA_APP_ID, ADZUNA_APP_KEY, ADZUNA_ENABLED
from db.repository import is_already_scored, make_job_key
from tools.search import is_credible, valid_jobs_this_session, _clean_text
from langchain_core.tools import tool
from utils.logger import get_logger

log = get_logger()


def _clean_adzuna_query(query: str) -> str:
    """Adzuna's country is set via the URL path, not the search text —
    strip a trailing 'India' so the search term itself stays clean."""
    cleaned = re.sub(r"\s+India\s*$", "", query, flags=re.IGNORECASE)
    return cleaned.strip() or query


@tool
def search_jobs_adzuna(query: str) -> list[dict]:
    """Search for job postings on Adzuna matching a given query, filtered to India.
    Same shape and filtering as search_jobs (JSearch) — credibility checks,
    already-scored dedup, and fabrication-guard registration all apply here too.
    Use this as a SECOND, independent source alongside search_jobs — Adzuna has
    its own separate quota, so use it when search_jobs results feel limited."""
    if not ADZUNA_ENABLED:
        return [{"info": "Adzuna is not configured (missing ADZUNA_APP_ID/KEY) — skip this tool."}]

    cleaned_query = _clean_adzuna_query(query)
    url = "https://api.adzuna.com/v1/api/jobs/in/search/1"
    params = {
        "app_id": ADZUNA_APP_ID,
        "app_key": ADZUNA_APP_KEY,
        "what": cleaned_query,
        "results_per_page": 10,
        "max_days_old": 7,
        "content-type": "application/json",
    }

    response = requests.get(url, params=params, timeout=30)
    if response.status_code != 200:
        log.error(f"Adzuna error: {response.status_code} - {response.text}")
        return [{"info": f"Adzuna search failed with status {response.status_code}."}]

    raw_jobs = response.json().get("results", [])[:5]

    trimmed_jobs = []
    skipped_seen = 0
    skipped_spam = 0
    for job in raw_jobs:
        title = _clean_text(job.get("title", ""))
        employer = _clean_text((job.get("company") or {}).get("display_name", ""))
        apply_link = job.get("redirect_url", "")
        description = job.get("description", "")
        location = (job.get("location") or {}).get("display_name", "Not specified")

        if is_already_scored(employer, title):
            skipped_seen += 1
            continue

        credible, reason = is_credible(title, employer, apply_link)
        if not credible:
            skipped_spam += 1
            log.warning(f"search_jobs_adzuna: filtered out '{title}' @ '{employer}' — {reason}")
            continue

        trimmed_jobs.append({
            "job_title": title,
            "employer_name": employer,
            "location": location,
            "apply_link": apply_link,
            "job_description": description[:600],
        })

    if skipped_seen:
        log.info(f"search_jobs_adzuna: skipped {skipped_seen} job(s) already scored in a previous run")
    if skipped_spam:
        log.info(f"search_jobs_adzuna: filtered {skipped_spam} job(s) as not credible")

    # Register with the SAME fabrication guard used by search_jobs — one
    # shared set, so score_job doesn't care which tool found a given job.
    for job in trimmed_jobs:
        valid_jobs_this_session.add(make_job_key(job["employer_name"], job["job_title"]))

    if not trimmed_jobs:
        return [{"info": f"No new jobs found on Adzuna for '{query}'."}]

    return trimmed_jobs
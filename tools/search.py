import html
import requests
from utils.logger import get_logger
log = get_logger()
from urllib.parse import urlparse
from config.settings import RAPIDAPI_KEY, SPAM_KEYWORDS, TRUSTED_BOARDS, SUSPICIOUS_BOARDS
from db.repository import is_already_scored, make_job_key
from langchain_core.tools import tool


def _clean_text(text: str) -> str:
    """JSearch sometimes returns titles/company names with unescaped
    unicode sequences (e.g. 'u0026' instead of '&'). Decode standard
    HTML/unicode entities so titles display cleanly in the Excel export."""
    if not text:
        return text
    text = html.unescape(text)
    text = text.replace("u0026", "&")  # catches the raw literal case too
    return text


def verify_apply_link(apply_link: str, employer_website: str = "") -> tuple[bool, str]:
    """Check whether a job's apply link is trustworthy.
    Returns (is_ok: bool, reason: str)."""
    if not apply_link:
        return False, "No apply link"

    apply_domain = urlparse(apply_link).netloc.replace("www.", "").lower()

    for s in SUSPICIOUS_BOARDS:
        if s in apply_domain:
            return False, f"Suspicious board: {s}"

    if employer_website:
        site_domain = urlparse(employer_website).netloc.replace("www.", "").lower()
        if site_domain and site_domain in apply_domain:
            return True, "Direct company site"

    for board in TRUSTED_BOARDS:
        if board in apply_domain:
            return True, f"Trusted board: {board}"

    path = urlparse(apply_link).path.lower()
    if any(kw in path for kw in ["/jobs", "/careers", "/apply", "/job-detail", "/vacancy"]):
        return True, f"Career-style path: {apply_domain}"

    return False, f"Unrecognized domain: {apply_domain}"


def is_credible(job_title: str, employer_name: str, apply_link: str, employer_website: str = "") -> tuple[bool, str]:
    """Combined credibility check: spam keywords + apply link verification."""
    combined = f"{job_title} {employer_name}".lower()
    for kw in SPAM_KEYWORDS:
        if kw in combined:
            return False, f"Spam keyword: {kw}"

    link_ok, reason = verify_apply_link(apply_link, employer_website)
    if not link_ok:
        return False, reason

    return True, "OK"


# Tracks employer+title keys that came from a REAL search_jobs call this
# session — score_job checks against this to reject fabricated jobs.
valid_jobs_this_session = set()


@tool
def search_jobs(query: str) -> list[dict]:
    """Search for job postings matching a given query, filtered to India.
    Returns a trimmed list of job dicts with title, company, location, apply link,
    and a short job_description excerpt. Jobs already scored in a previous run,
    or that fail credibility checks, are filtered out here before the LLM sees them."""
    url = "https://jsearch.p.rapidapi.com/search-v2"
    headers = {
        "X-RapidAPI-Key": RAPIDAPI_KEY,
        "X-RapidAPI-Host": "jsearch.p.rapidapi.com",
    }
    params = {"query": query, "location": "India", "num_pages": "1"}

    response = requests.get(url, headers=headers, params=params)
    if response.status_code != 200:
        log.error(f"Error: {response.status_code} - {response.text}")
        return [{"info": f"Search failed with status {response.status_code} — no jobs returned."}]

    data = response.json()
    raw_jobs = data.get("data", {}).get("jobs", [])[:5]

    trimmed_jobs = []
    skipped_seen = 0
    skipped_spam = 0
    for job in raw_jobs:
        title = _clean_text(job.get("job_title"))
        employer = _clean_text(job.get("employer_name"))
        apply_link = job.get("job_apply_link", "")
        employer_website = job.get("employer_website", "") or ""

        if is_already_scored(employer, title):
            skipped_seen += 1
            continue

        credible, reason = is_credible(title, employer, apply_link, employer_website)
        if not credible:
            skipped_spam += 1
            log.warning(f"search_jobs: filtered out '{title}' @ '{employer}' — {reason}")
            continue

        city = job.get("job_city") or job.get("job_location") or "Not specified"
        trimmed_jobs.append({
            "job_title": title,
            "employer_name": employer,
            "location": city,
            "apply_link": apply_link,
            "job_description": job.get("job_description", "")[:600],
        })

    if skipped_seen:
        log.info(f"search_jobs: skipped {skipped_seen} job(s) already scored in a previous run")
    if skipped_spam:
        log.info(f"search_jobs: filtered {skipped_spam} job(s) as not credible")

    for job in trimmed_jobs:
        valid_jobs_this_session.add(make_job_key(job["employer_name"], job["job_title"]))

    if not trimmed_jobs:
        return [{"info": f"No new jobs found for '{query}' — all {skipped_seen} result(s) were already scored previously."}]

    return trimmed_jobs
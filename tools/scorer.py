import json
from langchain_core.tools import tool
from langchain_groq import ChatGroq
from config.settings import GROQ_API_KEY, MY_RESUME
from db.repository import get_cached_score, save_score, make_job_key
from utils.retry import call_llm_with_retry
from tools.search import valid_jobs_this_session
from config.prompts import build_scoring_prompt
from db.api_usage import record_usage
from db.query_performance import record_query_outcome
from utils.logger import get_logger
log = get_logger()



@tool
def score_job(job_title: str, employer_name: str, job_description: str,
              apply_link: str, location: str = "", source_query: str = "") -> dict:
    """Score how well a single job matches the candidate's actual resume.
    Refuses to score/save any job that wasn't actually returned by a real
    search_jobs call this session (fabrication guard), unless it's a
    legitimately cached job from a past run."""

    cached = get_cached_score(employer_name, job_title)
    if cached is not None:
        return cached

    key = make_job_key(employer_name, job_title)
    if key not in valid_jobs_this_session:
        log.warning(f"REJECTED score_job call for unverified job: '{job_title}' @ '{employer_name}'")
        return {"match": "Low", "score": 0, "matched_skills": [], "missing_skills": [],
                "note": "Rejected — this job was not found by a real search_jobs call"}

    prompt = build_scoring_prompt(job_title, job_description, MY_RESUME)
    scoring_llm = ChatGroq(model="llama-3.3-70b-versatile", temperature=0, groq_api_key=GROQ_API_KEY)

    # FIX: catch total rate-limit exhaustion here instead of letting it
    # propagate and crash the whole graph run. One job failing to score
    # should not lose all the progress made on previous jobs/queries.
    try:
        response = call_llm_with_retry(scoring_llm, prompt)
        usage = response.response_metadata.get("token_usage", {})
        record_usage(prompt_tokens=usage.get("prompt_tokens", 0), completion_tokens=usage.get("completion_tokens", 0),
        total_tokens=usage.get("total_tokens", 0),)
    except RuntimeError as e:
        log.error(f"score_job: giving up on '{job_title}' @ '{employer_name}' — {e}")
        return {"match": "Low", "score": 0, "matched_skills": [], "missing_skills": [],
                "note": "Could not score — rate limit exhausted, try again later"}

    raw_text = response.content.strip().strip("`").replace("json", "", 1).strip()

    try:
        result = json.loads(raw_text)
    except json.JSONDecodeError:
        result = {"match": "Low", "score": 0, "matched_skills": [], "missing_skills": [],
                   "note": "Could not parse LLM response"}

    # Compute score deterministically from actual skill overlap, instead of
    # trusting the LLM to invent a number — this is what was causing every
    # High match to land on the same round 90, with no real differentiation.
    matched = result.get("matched_skills", [])
    missing = result.get("missing_skills", [])
    total = len(matched) + len(missing)
    result["score"] = round((len(matched) / total) * 100) if total > 0 else 0

    if result["score"] >= 75:
        result["match"] = "High"
    elif result["score"] >= 40:
        result["match"] = "Medium"
    else:
        result["match"] = "Low"

    save_score(employer_name, job_title, location, apply_link, result, source_query=source_query)
    record_query_outcome(source_query, result["match"])

    return result
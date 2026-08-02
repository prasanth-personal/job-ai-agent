from langchain_groq import ChatGroq
from config.settings import GROQ_API_KEY, MY_RESUME
from graph.phase3.resume_agent.state import ResumeAgentState
from tools.scorer import score_job
from utils.retry import call_llm_with_retry
from utils.logger import get_logger

log = get_logger()


def score_step(state: ResumeAgentState) -> dict:
    scored = []
    for job in state["raw_jobs"]:
        try:
            result = score_job.invoke({
                "job_title": job.get("job_title", ""),
                "employer_name": job.get("employer_name", ""),
                "job_description": job.get("job_description", ""),
                "apply_link": job.get("apply_link", ""),
                "location": job.get("location", ""),
                "source_query": job.get("source_query", ""),
            })
            scored.append({
                "job_title": job.get("job_title", ""),
                "employer_name": job.get("employer_name", ""),
                "apply_link": job.get("apply_link", ""),
                "source_query": job.get("source_query", ""),
                **result,
            })
        except Exception as e:
            log.error(f"ResumeAgent: failed to score '{job.get('job_title')}' — {e}")

    log.info(f"ResumeAgent scored {len(scored)} of {len(state['raw_jobs'])} jobs")
    return {"scored_jobs": scored}


def tailor_step(state: ResumeAgentState) -> dict:
    """NEW capability vs Phase 2: for every High match, ask the LLM for
    2-3 tailored resume bullet points emphasizing the matched skills for
    THAT specific job. Only High matches get this — keeps token cost
    bounded, since tailoring every Low match would be wasteful."""
    updated = []
    llm = ChatGroq(model="llama-3.3-70b-versatile", temperature=0, groq_api_key=GROQ_API_KEY)

    for job in state["scored_jobs"]:
        if job.get("match") != "High":
            updated.append(job)
            continue

        matched = ", ".join(job.get("matched_skills", []))
        prompt = f"""Given this resume and a job the candidate matched HIGH on,
write 2-3 short tailored resume bullet points emphasizing the overlap.

RESUME: {MY_RESUME[:1500]}
JOB: {job['job_title']} at {job['employer_name']}
MATCHED SKILLS: {matched}

Reply with ONLY the bullet points, one per line, no extra commentary."""

        try:
            response = call_llm_with_retry(llm, prompt, estimated_tokens=900)
            job["tailored_notes"] = response.content.strip()
        except Exception as e:
            log.warning(f"ResumeAgent: tailoring failed for '{job['job_title']}' — {e}")
            job["tailored_notes"] = ""

        updated.append(job)

    return {"scored_jobs": updated}
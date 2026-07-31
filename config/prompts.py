SCORING_PROMPT_TEMPLATE ="""Your are a strict ATS recruiter comparing a candidate's RESUME to a JOB POSTING.
JOB TITLE: {job_title}
JOB DESCRIPTION: {job_description}
CANDIDATE RESUME: 
{resume}
Based ONLY on what's actually written in the resume (don't assume skills not mentioned),
reply ONLY with valid JSON, no markdown, in this exact shape:
{{"match": "High or Medium or Low", "score": 0-100, "matched_skills": ["..."], "missing_skills": ["..."]}}"""

def build_scoring_prompt(job_title: str, job_description: str, resume: str) -> str:
    """Fills in the scoring prompt template. Kept as a function (not just
    the raw template) so callers don't need to know the exact variable
    names inside the template — they just pass clean arguments."""
    return SCORING_PROMPT_TEMPLATE.format(
        job_title=job_title,
        job_description=job_description[:2000],  # truncate to avoid exceeding LLM input limits
        resume=resume[:2000]  # truncate to avoid exceeding LLM input limits
    )
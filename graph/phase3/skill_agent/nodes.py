from collections import Counter
from langchain_groq import ChatGroq
from config.settings import GROQ_API_KEY
from graph.phase3.skill_agent.state import SkillAgentState
from utils.retry import call_llm_with_retry
from utils.logger import get_logger

log = get_logger()

TOP_N_TO_RESEARCH = 3  # only research the most common gaps — controls cost


def aggregate_step(state: SkillAgentState) -> dict:
    """Reused from Phase 2's skill_gap_node — free, no LLM call."""
    tracker = Counter()
    for job in state["scored_jobs"]:
        for skill in job.get("missing_skills", []):
            cleaned = skill.strip().lower()
            if cleaned:
                tracker[cleaned] += 1
    log.info(f"SkillAgent aggregated {len(tracker)} distinct gaps")
    return {"skill_gaps": dict(tracker)}


def research_step(state: SkillAgentState) -> dict:
    """NEW capability vs Phase 2: for the top N most common gaps, ask the
    LLM for a short, practical note on what the skill involves and how to
    start learning it. Bounded to TOP_N_TO_RESEARCH so this doesn't scale
    with total distinct gaps found (which could be dozens, as seen in
    earlier test runs today)."""
    top_gaps = sorted(state["skill_gaps"].items(), key=lambda x: -x[1])[:TOP_N_TO_RESEARCH]
    if not top_gaps:
        return {"skill_research": {}}

    llm = ChatGroq(model="llama-3.3-70b-versatile", temperature=0, groq_api_key=GROQ_API_KEY)
    research = {}

    for skill, count in top_gaps:
        prompt = f"""In 2 sentences, explain what '{skill}' involves in a
Salesforce/enterprise software context, and suggest one concrete first
step to start learning it (e.g. a specific type of resource, not a generic
'take a course')."""
        try:
            response = call_llm_with_retry(llm, prompt, estimated_tokens=400)
            research[skill] = response.content.strip()
        except Exception as e:
            log.warning(f"SkillAgent: research failed for '{skill}' — {e}")
            research[skill] = ""

    return {"skill_research": research}
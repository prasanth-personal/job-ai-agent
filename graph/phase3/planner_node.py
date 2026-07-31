import json
from langchain_groq import ChatGroq
from config.settings import GROQ_API_KEY, MY_RESUME, SEARCH_QUERIES
from graph.phase3.state import TopLevelState
from utils.retry import call_llm_with_retry
from utils.logger import get_logger

log = get_logger()


def planner_node(state: TopLevelState) -> dict:
    """Top-level planner — same judgment as Phase 2's planner, but its
    only job here is picking ONE best query for this run to hand to
    Search Agent (Phase 3 runs one query per full 3-agent pass, since
    each pass is more expensive than Phase 2's fixed pipeline)."""

    query_list_text = "\n".join(f"- {q}" for q in SEARCH_QUERIES)
    prompt = f"""You are planning a job search session.

CANDIDATE RESUME:
{MY_RESUME}

AVAILABLE QUERIES:
{query_list_text}

Pick the SINGLE best query for this candidate right now. Reply ONLY with
that exact query string, no quotes, no markdown, no explanation."""

    llm = ChatGroq(model="llama-3.3-70b-versatile", temperature=0, groq_api_key=GROQ_API_KEY)

    try:
        response = call_llm_with_retry(llm, prompt, estimated_tokens=1000)
        chosen = response.content.strip().strip('"').strip("'")
        if chosen not in SEARCH_QUERIES:
            raise ValueError(f"LLM returned a query not in config: '{chosen}'")
        log.info(f"Phase3 planner selected: {chosen}")
        return {"queries": [chosen]}
    except Exception as e:
        log.warning(f"Phase3 planner failed ({e}) — falling back to first configured query")
        return {"queries": [SEARCH_QUERIES[0]]}
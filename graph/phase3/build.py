import time
from langgraph.graph import StateGraph, END
from graph.phase3.state import TopLevelState
from graph.phase3.search_agent.build import build_search_agent
from graph.phase3.search_agent.state import initial_search_state
from graph.phase3.resume_agent.build import build_resume_agent
from graph.phase3.resume_agent.state import initial_resume_state
from graph.phase3.skill_agent.build import build_skill_agent
from graph.phase3.skill_agent.state import initial_skill_state
from db.repository import make_job_key
from utils.logger import get_logger
from graph.phase3.planner_node import planner_node

log = get_logger()

_search_agent = build_search_agent()
_resume_agent = build_resume_agent()
_skill_agent = build_skill_agent()

# Pause between queries within one run — sequential, not parallel, since
# neither tools/search.py nor tools/search_adzuna.py have any built-in
# rate-limit throttling yet. This is a cheap, safe guard against bursting
# JSearch/Adzuna until proper per-provider throttling is added.
INTER_QUERY_DELAY_SECONDS = 2


def search_node(state: TopLevelState) -> dict:
    """Boundary node: runs the Search Agent sub-graph once PER query in
    state['queries'] (now potentially several, from the round-robin
    planner), sequentially — not in parallel, to stay safe against rate
    limits with no throttling in place yet. Merges results across queries,
    deduping by employer+title so the same job surfacing from two
    different queries doesn't get double-counted or double-scored."""
    all_raw_jobs = []
    seen_keys = set()

    queries = state["queries"] or []
    for i, query in enumerate(queries):
        sub_result = _search_agent.invoke(initial_search_state(query))
        new_jobs = sub_result["raw_jobs"]

        added = 0
        for job in new_jobs:
            key = make_job_key(job.get("employer_name", ""), job.get("job_title", ""))
            if key in seen_keys:
                continue
            seen_keys.add(key)
            all_raw_jobs.append(job)
            added += 1

        log.info(f"Top-level: Search Agent query '{query}' returned {len(new_jobs)} jobs, {added} new after cross-query dedup")

        if i < len(queries) - 1:
            time.sleep(INTER_QUERY_DELAY_SECONDS)

    log.info(f"Top-level: Search Agent total across {len(queries)} quer{'y' if len(queries)==1 else 'ies'}: {len(all_raw_jobs)} jobs")
    return {"found_jobs": all_raw_jobs}


def resume_node(state: TopLevelState) -> dict:
    """Boundary node: hands found_jobs into Resume Agent's own state,
    gets back scored_jobs (with tailored_notes on High matches)."""
    sub_result = _resume_agent.invoke(initial_resume_state(state["found_jobs"]))
    log.info(f"Top-level: Resume Agent scored {len(sub_result['scored_jobs'])} jobs")
    return {"scored_jobs": sub_result["scored_jobs"]}


def skill_node(state: TopLevelState) -> dict:
    """Boundary node: hands scored_jobs into Skill Agent, gets back
    aggregated gaps + research notes."""
    sub_result = _skill_agent.invoke(initial_skill_state(state["scored_jobs"]))
    log.info(f"Top-level: Skill Agent found {len(sub_result['skill_gaps'])} gaps, researched {len(sub_result['skill_research'])}")
    return {"skill_gaps": sub_result["skill_gaps"], "skill_research": sub_result["skill_research"]}


def recommend_node(state: TopLevelState) -> dict:
    """Final grounded summary — same principle as Phase 2's version:
    built from real scored_jobs data, not conversation memory."""
    high_medium = [j for j in state["scored_jobs"] if j.get("match") in ("High", "Medium")]
    if not high_medium:
        return {"final_summary": "No High or Medium match jobs found in this run."}
    lines = [f"- {j['job_title']} @ {j['employer_name']} ({j['match']}, {j['score']})" for j in high_medium]
    summary = f"{len(high_medium)} jobs worth reviewing:\n" + "\n".join(lines)
    return {"final_summary": summary}


def build_phase3_pipeline():
    builder = StateGraph(TopLevelState)
    builder.add_node("planner", planner_node)
    builder.add_node("search", search_node)
    builder.add_node("resume", resume_node)
    builder.add_node("skill", skill_node)
    builder.add_node("recommend", recommend_node)

    builder.set_entry_point("planner")
    builder.add_edge("planner", "search")
    builder.add_edge("search", "resume")
    builder.add_edge("resume", "skill")
    builder.add_edge("skill", "recommend")
    builder.add_edge("recommend", END)

    return builder.compile()
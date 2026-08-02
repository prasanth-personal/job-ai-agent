import time
from datetime import date
from langgraph.graph import StateGraph, END
from graph.phase3.state import TopLevelState
from graph.phase3.search_agent.build import build_search_agent
from graph.phase3.search_agent.state import initial_search_state
from graph.phase3.resume_agent.build import build_resume_agent
from graph.phase3.resume_agent.state import initial_resume_state
from graph.phase3.skill_agent.build import build_skill_agent
from graph.phase3.skill_agent.state import initial_skill_state
from db.repository import make_job_key
from db.checkpoints import save_checkpoint
from utils.logger import get_logger
from graph.phase3.planner_node import planner_node as _planner_node

log = get_logger()

_search_agent = build_search_agent()
_resume_agent = build_resume_agent()
_skill_agent = build_skill_agent()

INTER_QUERY_DELAY_SECONDS = 2


def _checkpoint(state: TopLevelState, stage: str, delta: dict):
    merged = {**state, **delta}
    save_checkpoint(date.today(), stage, merged)


def planner_node(state: TopLevelState) -> dict:
    delta = _planner_node(state)
    _checkpoint(state, "planner", delta)
    return delta


def search_node(state: TopLevelState) -> dict:
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
    delta = {"found_jobs": all_raw_jobs}
    _checkpoint(state, "search", delta)
    return delta


def resume_node(state: TopLevelState) -> dict:
    sub_result = _resume_agent.invoke(initial_resume_state(state["found_jobs"]))
    log.info(f"Top-level: Resume Agent scored {len(sub_result['scored_jobs'])} jobs")
    delta = {"scored_jobs": sub_result["scored_jobs"]}
    _checkpoint(state, "resume", delta)
    return delta


def skill_node(state: TopLevelState) -> dict:
    sub_result = _skill_agent.invoke(initial_skill_state(state["scored_jobs"]))
    log.info(f"Top-level: Skill Agent found {len(sub_result['skill_gaps'])} gaps, researched {len(sub_result['skill_research'])}")
    delta = {"skill_gaps": sub_result["skill_gaps"], "skill_research": sub_result["skill_research"]}
    _checkpoint(state, "skill", delta)
    return delta


def recommend_node(state: TopLevelState) -> dict:
    high_medium = [j for j in state["scored_jobs"] if j.get("match") in ("High", "Medium")]
    if not high_medium:
        return {"final_summary": "No High or Medium match jobs found in this run."}
    lines = [f"- {j['job_title']} @ {j['employer_name']} ({j['match']}, {j['score']})" for j in high_medium]
    summary = f"{len(high_medium)} jobs worth reviewing:\n" + "\n".join(lines)
    return {"final_summary": summary}


def route_start_stage(state: TopLevelState) -> str:
    return state.get("_resume_stage") or "planner"


def build_phase3_pipeline():
    builder = StateGraph(TopLevelState)
    builder.add_node("planner", planner_node)
    builder.add_node("search", search_node)
    builder.add_node("resume", resume_node)
    builder.add_node("skill", skill_node)
    builder.add_node("recommend", recommend_node)

    builder.set_conditional_entry_point(
        route_start_stage,
        {"planner": "planner", "search": "search", "resume": "resume", "skill": "skill", "recommend": "recommend"},
    )
    builder.add_edge("planner", "search")
    builder.add_edge("search", "resume")
    builder.add_edge("resume", "skill")
    builder.add_edge("skill", "recommend")
    builder.add_edge("recommend", END)

    return builder.compile()
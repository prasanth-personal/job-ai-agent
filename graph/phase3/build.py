from langgraph.graph import StateGraph, END
from graph.phase3.state import TopLevelState
from graph.phase3.search_agent.build import build_search_agent
from graph.phase3.search_agent.state import initial_search_state
from graph.phase3.resume_agent.build import build_resume_agent
from graph.phase3.resume_agent.state import initial_resume_state
from graph.phase3.skill_agent.build import build_skill_agent
from graph.phase3.skill_agent.state import initial_skill_state
from utils.logger import get_logger
from graph.phase3.planner_node import planner_node

log = get_logger()

_search_agent = build_search_agent()
_resume_agent = build_resume_agent()
_skill_agent = build_skill_agent()


def search_node(state: TopLevelState) -> dict:
    """Boundary node: translates TopLevelState into Search Agent's own
    state shape, runs the whole sub-graph, translates its result back.
    Only queries[0] is used for now — running multiple queries through
    Search Agent sequentially is a natural next extension, kept simple
    here on purpose."""
    query = state["queries"][0] if state["queries"] else ""
    sub_result = _search_agent.invoke(initial_search_state(query))
    log.info(f"Top-level: Search Agent returned {len(sub_result['raw_jobs'])} jobs")
    return {"found_jobs": sub_result["raw_jobs"]}


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
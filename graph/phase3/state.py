from typing import TypedDict


class TopLevelState(TypedDict):
    queries: list[str]
    searched_queries: list[str]  # NEW — queries already run through search_node, so a replan only searches the newly added ones
    found_jobs: list[dict]
    scored_jobs: list[dict]
    skill_gaps: dict[str, int]
    skill_research: dict[str, str]
    final_summary: str
    _resume_stage: str
    replan_count: int  # NEW — hard cap on mid-run replans, shared across both trigger types


def initial_top_state(queries: list[str]) -> TopLevelState:
    """queries param kept for call-site compatibility — the planner
    always builds its own fresh list each run, it never reads this."""
    return TopLevelState(
        queries=[],
        searched_queries=[],
        found_jobs=[],
        scored_jobs=[],
        skill_gaps={},
        skill_research={},
        final_summary="",
        _resume_stage="planner",
        replan_count=0,
    )


def resume_top_state(saved_state: dict, resume_stage: str) -> TopLevelState:
    """Rebuild state from a saved checkpoint, entering the graph at the
    stage right after the last one that completed."""
    return TopLevelState(
        queries=saved_state.get("queries", []),
        searched_queries=saved_state.get("searched_queries", []),
        found_jobs=saved_state.get("found_jobs", []),
        scored_jobs=saved_state.get("scored_jobs", []),
        skill_gaps=saved_state.get("skill_gaps", {}),
        skill_research=saved_state.get("skill_research", {}),
        final_summary=saved_state.get("final_summary", ""),
        _resume_stage=resume_stage,
        replan_count=saved_state.get("replan_count", 0),
    )
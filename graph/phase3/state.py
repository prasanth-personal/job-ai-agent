from typing import TypedDict


class TopLevelState(TypedDict):
    queries: list[str]
    found_jobs: list[dict]
    scored_jobs: list[dict]
    skill_gaps: dict[str, int]
    skill_research: dict[str, str]
    final_summary: str
    _resume_stage: str  # NEW — where the entry router should start


def initial_top_state(queries: list[str]) -> TopLevelState:
    return TopLevelState(
        queries=queries,
        found_jobs=[],
        scored_jobs=[],
        skill_gaps={},
        skill_research={},
        final_summary="",
        _resume_stage="planner",
    )


def resume_top_state(saved_state: dict, resume_stage: str) -> TopLevelState:
    """Rebuild state from a saved checkpoint, entering the graph at the
    stage right after the last one that completed."""
    return TopLevelState(
        queries=saved_state.get("queries", []),
        found_jobs=saved_state.get("found_jobs", []),
        scored_jobs=saved_state.get("scored_jobs", []),
        skill_gaps=saved_state.get("skill_gaps", {}),
        skill_research=saved_state.get("skill_research", {}),
        final_summary=saved_state.get("final_summary", ""),
        _resume_stage=resume_stage,
    )
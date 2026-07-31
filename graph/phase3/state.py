from typing import TypedDict


class TopLevelState(TypedDict):
    # Set by the top-level planner — same idea as Phase 2's planner,
    # decides which queries to prioritize this run.
    queries: list[str]

    # Set by Search Agent (its own sub-graph) — the final list of
    # credible jobs it found, after its own internal search-and-judge loop.
    # Search Agent's OWN internal reasoning/state does not leak out here —
    # only this final result does.
    found_jobs: list[dict]

    # Set by Resume Agent — scored jobs, and for High matches, an added
    # tailored_resume_notes field (new capability vs Phase 2).
    scored_jobs: list[dict]

    # Set by Skill Agent — aggregated skill gaps, potentially with
    # research notes on high-priority gaps (new capability vs Phase 2).
    skill_gaps: dict[str, int]
    skill_research: dict[str, str]

    # Set by the final Recommendation step.
    final_summary: str


def initial_top_state(queries: list[str]) -> TopLevelState:
    return TopLevelState(
        queries=queries,
        found_jobs=[],
        scored_jobs=[],
        skill_gaps={},
        skill_research={},
        final_summary="",
    )
from typing import TypedDict


class SkillAgentState(TypedDict):
    scored_jobs: list[dict]        # handed in from Resume Agent's output
    skill_gaps: dict[str, int]     # output
    skill_research: dict[str, str] # output — notes on top gaps only


def initial_skill_state(scored_jobs: list[dict]) -> SkillAgentState:
    return SkillAgentState(scored_jobs=scored_jobs, skill_gaps={}, skill_research={})
from typing import TypedDict


class ResumeAgentState(TypedDict):
    raw_jobs: list[dict]      # handed in from Search Agent's output
    scored_jobs: list[dict]   # output — includes tailored_notes for High matches


def initial_resume_state(raw_jobs: list[dict]) -> ResumeAgentState:
    return ResumeAgentState(raw_jobs=raw_jobs, scored_jobs=[])
from typing import TypedDict


class SearchAgentState(TypedDict):
    query: str                    # the single query this agent was handed
    raw_jobs: list[dict]           # accumulates across internal loop iterations
    search_attempts: int           # internal guardrail counter
    max_attempts: int
    done: bool


def initial_search_state(query: str, max_attempts: int = 2) -> SearchAgentState:
    return SearchAgentState(
        query=query,
        raw_jobs=[],
        search_attempts=0,
        max_attempts=max_attempts,
        done=False,
    )
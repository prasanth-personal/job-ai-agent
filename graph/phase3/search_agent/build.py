from langgraph.graph import StateGraph, END
from graph.phase3.search_agent.state import SearchAgentState
from graph.phase3.search_agent.nodes import search_step, should_continue_search


def build_search_agent():
    """Compiles Search Agent as its own standalone graph. This compiled
    graph is what gets embedded as a single node inside the top-level
    Planner graph in a later step — a graph used as a node."""
    builder = StateGraph(SearchAgentState)
    builder.add_node("search_step", search_step)
    builder.set_entry_point("search_step")
    builder.add_conditional_edges(
        "search_step", should_continue_search, {"search_step": "search_step", "done": END}
    )
    return builder.compile()
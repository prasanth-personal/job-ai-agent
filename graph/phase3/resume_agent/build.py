from langgraph.graph import StateGraph, END
from graph.phase3.resume_agent.state import ResumeAgentState
from graph.phase3.resume_agent.nodes import score_step, tailor_step


def build_resume_agent():
    """Two-step fixed sequence, no loop needed here — score, then tailor
    High matches. Unlike Search Agent, this doesn't need to decide
    'have I done enough,' just execute both steps once."""
    builder = StateGraph(ResumeAgentState)
    builder.add_node("score_step", score_step)
    builder.add_node("tailor_step", tailor_step)
    builder.set_entry_point("score_step")
    builder.add_edge("score_step", "tailor_step")
    builder.add_edge("tailor_step", END)
    return builder.compile()
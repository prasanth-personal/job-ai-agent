from langgraph.graph import StateGraph, END
from graph.phase3.skill_agent.state import SkillAgentState
from graph.phase3.skill_agent.nodes import aggregate_step, research_step


def build_skill_agent():
    builder = StateGraph(SkillAgentState)
    builder.add_node("aggregate_step", aggregate_step)
    builder.add_node("research_step", research_step)
    builder.set_entry_point("aggregate_step")
    builder.add_edge("aggregate_step", "research_step")
    builder.add_edge("research_step", END)
    return builder.compile()
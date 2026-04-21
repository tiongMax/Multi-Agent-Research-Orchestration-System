from langgraph.graph import StateGraph, END

from agents.planner import run_planner
from agents.researcher import run_researcher
from agents.extractor import run_extractor
from agents.critic import run_critic
from agents.writer import run_writer
from graph.edges import route_after_critic
from graph.state import ResearchState


def _rework(state: ResearchState) -> dict:
    """Increment retry counter before looping back to researcher."""
    return {"retry_count": state.get("retry_count", 0) + 1}


def build_graph():
    builder = StateGraph(ResearchState)

    builder.add_node("planner", run_planner)
    builder.add_node("researcher", run_researcher)
    builder.add_node("extractor", run_extractor)
    builder.add_node("critic", run_critic)
    builder.add_node("rework", _rework)
    builder.add_node("writer", run_writer)

    builder.set_entry_point("planner")
    builder.add_edge("planner", "researcher")
    builder.add_edge("researcher", "extractor")
    builder.add_edge("extractor", "critic")
    builder.add_conditional_edges(
        "critic",
        route_after_critic,
        {"rework": "rework", "writer": "writer"},
    )
    builder.add_edge("rework", "researcher")
    builder.add_edge("writer", END)

    return builder.compile()


graph = build_graph()


def run(query: str) -> ResearchState:
    """Convenience entry point for running the full pipeline."""
    initial: ResearchState = {
        "query": query,
        "sub_questions": [],
        "search_results": {},
        "extracted_facts": [],
        "critique": "",
        "final_report": "",
        "current_step": "",
        "retry_count": 0,
        "errors": [],
        "memory_hits": [],
    }
    return graph.invoke(initial)

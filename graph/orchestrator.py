from langgraph.graph import StateGraph, END

from agents.planner import run_planner
from agents.researcher import run_researcher
from agents.extractor import run_extractor
from agents.critic import run_critic
from agents.writer import run_writer
from core.logger import get_logger
from graph.edges import route_after_critic
from graph.state import ResearchState
from memory.store import retrieve_similar, save_research

log = get_logger(__name__)


def _rework(state: ResearchState) -> dict:
    attempt = state.get("retry_count", 0) + 1
    log.warning("Rework triggered — attempt %d", attempt)
    return {"retry_count": attempt}


def _memory_retrieve(state: ResearchState) -> dict:
    hits = retrieve_similar(state["query"])
    return {"memory_hits": hits, "current_step": "memory_retrieved"}


def _memory_save(state: ResearchState) -> dict:
    save_research(
        query=state["query"],
        sub_questions=state.get("sub_questions", []),
        facts=state.get("extracted_facts", []),
        report=state.get("final_report", ""),
    )
    return {}


def build_graph():
    builder = StateGraph(ResearchState)

    builder.add_node("planner", run_planner)
    builder.add_node("memory_retrieve", _memory_retrieve)
    builder.add_node("researcher", run_researcher)
    builder.add_node("extractor", run_extractor)
    builder.add_node("critic", run_critic)
    builder.add_node("rework", _rework)
    builder.add_node("writer", run_writer)
    builder.add_node("memory_save", _memory_save)

    builder.set_entry_point("planner")
    builder.add_edge("planner", "memory_retrieve")
    builder.add_edge("memory_retrieve", "researcher")
    builder.add_edge("researcher", "extractor")
    builder.add_edge("extractor", "critic")
    builder.add_conditional_edges(
        "critic",
        route_after_critic,
        {"rework": "rework", "writer": "writer"},
    )
    builder.add_edge("rework", "researcher")
    builder.add_edge("writer", "memory_save")
    builder.add_edge("memory_save", END)

    return builder.compile()


graph = build_graph()


def run(query: str) -> ResearchState:
    """Convenience entry point for running the full pipeline."""
    log.info('── Pipeline start: "%s"', query)
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
    result = graph.invoke(initial)
    retries = result.get("retry_count", 0)
    errors = result.get("errors", [])
    log.info(
        "── Pipeline complete (retries=%d, facts=%d, errors=%d)",
        retries,
        len(result.get("extracted_facts", [])),
        len(errors),
    )
    if errors:
        for err in errors:
            log.warning("Pipeline error recorded: %s", err)
    return result

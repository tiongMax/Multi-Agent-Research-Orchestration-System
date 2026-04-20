from typing import TypedDict


class ResearchState(TypedDict):
    query: str                       # Original user query
    sub_questions: list[str]         # Planner output
    search_results: dict[str, list]  # Researcher output keyed by sub-question
    extracted_facts: list[str]       # Extractor output
    critique: str                    # Critic evaluation text
    final_report: str                # Writer output
    current_step: str                # Orchestrator tracking
    retry_count: int                 # Failure handling counter
    errors: list[str]                # Error log
    memory_hits: list[str]           # Facts retrieved from vector memory

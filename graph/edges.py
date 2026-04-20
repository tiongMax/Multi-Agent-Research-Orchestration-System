from graph.state import ResearchState

_MAX_RETRIES = 3


def route_after_critic(state: ResearchState) -> str:
    """Send to rework+re-research if quality is poor, otherwise proceed to writer."""
    poor = "VERDICT: POOR" in state.get("critique", "")
    under_limit = state.get("retry_count", 0) < _MAX_RETRIES
    return "rework" if (poor and under_limit) else "writer"

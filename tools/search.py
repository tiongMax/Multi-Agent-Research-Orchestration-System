from ddgs import DDGS
from tenacity import retry, stop_after_attempt, wait_exponential, before_sleep_log
import logging

from core.logger import get_logger

log = get_logger(__name__)


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    before_sleep=before_sleep_log(log, logging.WARNING),
)
def search_web(query: str, max_results: int = 5) -> list[dict]:
    """Return DuckDuckGo text results for a query."""
    with DDGS() as ddgs:
        results = list(ddgs.text(query, max_results=max_results))
    return results

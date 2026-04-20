import concurrent.futures

import httpx
from bs4 import BeautifulSoup

from graph.state import ResearchState
from tools.search import search_web

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0 Safari/537.36"
    )
}
_MAX_CHARS = 4000
_MAX_WORKERS = 5


def _scrape_sync(url: str) -> str:
    try:
        with httpx.Client(timeout=12, headers=_HEADERS, follow_redirects=True) as client:
            resp = client.get(url)
            resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "lxml")
        for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
            tag.decompose()
        return soup.get_text(separator="\n", strip=True)[:_MAX_CHARS]
    except Exception:
        return ""


def _research_subquestion(sub_question: str) -> tuple[str, list[dict]]:
    results = search_web(sub_question, max_results=5)
    enriched = []
    for r in results:
        url = r.get("href", "")
        content = _scrape_sync(url) if url else ""
        enriched.append({
            "title": r.get("title", ""),
            "url": url,
            "snippet": r.get("body", ""),
            "content": content or r.get("body", ""),
        })
    return sub_question, enriched


def run_researcher(state: ResearchState) -> dict:
    sub_questions = state["sub_questions"]
    errors = list(state.get("errors", []))
    search_results: dict[str, list] = {}

    with concurrent.futures.ThreadPoolExecutor(max_workers=_MAX_WORKERS) as executor:
        futures = {executor.submit(_research_subquestion, q): q for q in sub_questions}
        for future in concurrent.futures.as_completed(futures):
            q = futures[future]
            try:
                _, results = future.result(timeout=90)
                search_results[q] = results
            except Exception as e:
                errors.append(f"Researcher failed for '{q}': {e}")
                search_results[q] = []

    return {
        "search_results": search_results,
        "errors": errors,
        "current_step": "researcher_done",
    }

"""Tests for agents.researcher.run_researcher.

run_researcher fans out DuckDuckGo searches across sub-questions in parallel
using ThreadPoolExecutor, scrapes each result URL, and returns a dict keyed
by sub-question. Network calls (search_web, _scrape_sync) are mocked so tests
run offline.
"""
from unittest.mock import patch

from agents.researcher import run_researcher

_MOCK_RESULTS = [{"href": "http://example.com", "title": "Example", "body": "snippet text"}]


def test_builds_search_results_structure():
    """Assembles search_results dict keyed by sub-question with scraped content."""
    with patch("agents.researcher.search_web", return_value=_MOCK_RESULTS), \
         patch("agents.researcher._scrape_sync", return_value="scraped content"):
        result = run_researcher({"sub_questions": ["What is a qubit?"], "errors": []})

    assert "What is a qubit?" in result["search_results"]
    entry = result["search_results"]["What is a qubit?"][0]
    assert entry["content"] == "scraped content"
    assert entry["url"] == "http://example.com"
    assert result["current_step"] == "researcher_done"


def test_falls_back_to_snippet_when_scrape_empty():
    """Uses the DuckDuckGo snippet as content when scraping returns nothing."""
    with patch("agents.researcher.search_web", return_value=_MOCK_RESULTS), \
         patch("agents.researcher._scrape_sync", return_value=""):
        result = run_researcher({"sub_questions": ["q"], "errors": []})

    assert result["search_results"]["q"][0]["content"] == "snippet text"


def test_records_error_and_empty_list_on_search_failure():
    """A failed search logs an error message and stores an empty list for that sub-question."""
    with patch("agents.researcher.search_web", side_effect=Exception("network error")):
        result = run_researcher({"sub_questions": ["What is a qubit?"], "errors": []})

    assert result["search_results"]["What is a qubit?"] == []
    assert any("Researcher failed" in e for e in result["errors"])


def test_handles_multiple_sub_questions():
    """All sub-questions appear as keys in search_results regardless of execution order."""
    with patch("agents.researcher.search_web", return_value=_MOCK_RESULTS), \
         patch("agents.researcher._scrape_sync", return_value="content"):
        result = run_researcher({"sub_questions": ["q1", "q2", "q3"], "errors": []})

    assert set(result["search_results"].keys()) == {"q1", "q2", "q3"}

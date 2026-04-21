"""Tests for agents.extractor.run_extractor.

run_extractor sends scraped content to the LLM once per sub-question and
collects facts into a flat list. Memory hits from a prior vector search are
prepended before any LLM-extracted facts.
"""
from unittest.mock import MagicMock, patch

from agents.extractor import run_extractor

_SEARCH_RESULTS = {
    "What is a qubit?": [{"url": "http://example.com", "content": "A qubit is a quantum bit..."}]
}


def _make_response(text: str) -> MagicMock:
    r = MagicMock()
    r.content = text
    return r


def test_extracts_facts_and_strips_numbering():
    """Parses LLM output into a flat list with numbered prefixes removed."""
    with patch("agents.extractor._llm") as mock_llm:
        mock_llm.invoke.return_value = _make_response(
            "1. Qubits can be in superposition\n2. Entanglement links qubits"
        )
        result = run_extractor({
            "search_results": _SEARCH_RESULTS,
            "memory_hits": [],
            "errors": [],
        })

    assert "Qubits can be in superposition" in result["extracted_facts"]
    assert "Entanglement links qubits" in result["extracted_facts"]
    assert result["current_step"] == "extractor_done"


def test_prepends_memory_hits():
    """Memory hits from prior searches appear before LLM-extracted facts."""
    with patch("agents.extractor._llm") as mock_llm:
        mock_llm.invoke.return_value = _make_response("1. New fact")
        result = run_extractor({
            "search_results": _SEARCH_RESULTS,
            "memory_hits": ["Cached fact from memory"],
            "errors": [],
        })

    assert result["extracted_facts"][0] == "Cached fact from memory"
    assert "New fact" in result["extracted_facts"]


def test_skips_sub_question_with_no_results():
    """Does not call the LLM when a sub-question has no search results."""
    with patch("agents.extractor._llm") as mock_llm:
        result = run_extractor({
            "search_results": {"empty q": []},
            "memory_hits": [],
            "errors": [],
        })

    mock_llm.invoke.assert_not_called()
    assert result["extracted_facts"] == []


def test_records_error_on_llm_failure():
    """A failed LLM call is logged in errors without raising an exception."""
    with patch("agents.extractor._llm") as mock_llm:
        mock_llm.invoke.side_effect = Exception("API timeout")
        result = run_extractor({
            "search_results": _SEARCH_RESULTS,
            "memory_hits": [],
            "errors": [],
        })

    assert any("Extractor failed" in e for e in result["errors"])

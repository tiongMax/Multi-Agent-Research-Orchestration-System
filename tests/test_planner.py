"""Tests for agents.planner.run_planner.

run_planner calls the LLM once to decompose a query into sub-questions and
returns them as a plain list with numbering prefixes stripped.
"""
from unittest.mock import MagicMock, patch

from agents.planner import run_planner


def _make_response(text: str) -> MagicMock:
    r = MagicMock()
    r.content = text
    return r


def test_parses_numbered_list():
    """Returns one sub-question per line with dot-style numbering removed."""
    with patch("agents.planner._llm") as mock_llm:
        mock_llm.invoke.return_value = _make_response(
            "1. What is a qubit?\n2. How does entanglement work?\n3. What are quantum gates?"
        )
        result = run_planner({"query": "What is quantum computing?"})

    assert result["sub_questions"] == [
        "What is a qubit?",
        "How does entanglement work?",
        "What are quantum gates?",
    ]
    assert result["current_step"] == "planner_done"


def test_strips_both_numbering_formats():
    """Strips both '1.' and '1)' prefix formats from LLM output."""
    with patch("agents.planner._llm") as mock_llm:
        mock_llm.invoke.return_value = _make_response(
            "1) First question\n2. Second question\n3) Third question"
        )
        result = run_planner({"query": "test"})

    assert result["sub_questions"] == ["First question", "Second question", "Third question"]


def test_skips_blank_lines():
    """Blank lines in LLM output are not included in sub_questions."""
    with patch("agents.planner._llm") as mock_llm:
        mock_llm.invoke.return_value = _make_response("1. Only question\n\n")
        result = run_planner({"query": "test"})

    assert result["sub_questions"] == ["Only question"]

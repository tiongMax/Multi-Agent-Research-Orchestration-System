"""Tests for agents.writer.run_writer.

run_writer sends the query, extracted facts, and critic evaluation to the LLM
and returns a markdown report. On LLM failure it returns a fallback message
so the pipeline state remains valid.
"""
from unittest.mock import MagicMock, patch

from agents.writer import run_writer

_BASE_STATE = {
    "query": "What is quantum computing?",
    "extracted_facts": ["Qubits can superpose", "Entanglement links qubits"],
    "critique": "VERDICT: GOOD",
    "errors": [],
}


def _make_response(text: str) -> MagicMock:
    r = MagicMock()
    r.content = text
    return r


def test_returns_report_from_llm():
    """Stores the LLM response verbatim as final_report and marks step complete."""
    with patch("agents.writer._llm") as mock_llm:
        mock_llm.invoke.return_value = _make_response("## Introduction\nQuantum computing uses qubits...")
        result = run_writer(_BASE_STATE)

    assert result["final_report"] == "## Introduction\nQuantum computing uses qubits..."
    assert result["current_step"] == "complete"


def test_graceful_degradation_on_llm_failure():
    """Returns a fallback message and logs the error when the LLM call fails."""
    with patch("agents.writer._llm") as mock_llm:
        mock_llm.invoke.side_effect = Exception("API error")
        result = run_writer(_BASE_STATE)

    assert "failed" in result["final_report"].lower()
    assert any("Writer failed" in e for e in result["errors"])
    assert result["current_step"] == "complete"


def test_facts_and_critique_passed_to_llm():
    """Extracted facts and critic verdict are both present in the LLM prompt."""
    captured = []

    def fake_invoke(messages):
        captured.extend(messages)
        r = MagicMock()
        r.content = "report"
        return r

    with patch("agents.writer._llm") as mock_llm:
        mock_llm.invoke.side_effect = fake_invoke
        run_writer(_BASE_STATE)

    prompt_text = " ".join(m.content for m in captured)
    assert "Qubits can superpose" in prompt_text
    assert "VERDICT: GOOD" in prompt_text

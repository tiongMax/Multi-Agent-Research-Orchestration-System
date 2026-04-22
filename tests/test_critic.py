"""Tests for agents.critic.run_critic.

run_critic runs a heuristic contradiction check first, then asks the LLM to
issue a VERDICT: GOOD or VERDICT: POOR. On LLM failure it defaults to GOOD so
the pipeline can continue.
"""
from unittest.mock import MagicMock, patch

from agents.critic import run_critic

_BASE_STATE = {
    "query": "What is quantum computing?",
    "extracted_facts": ["Qubits can be 0 and 1 simultaneously", "Quantum gates manipulate qubits"],
    "errors": [],
}


def _make_response(text: str) -> MagicMock:
    r = MagicMock()
    r.content = text
    return r


def test_good_verdict_is_preserved():
    """Stores the full LLM response when it contains VERDICT: GOOD."""
    with patch("agents.critic._llm") as mock_llm:
        mock_llm.invoke.return_value = _make_response("Facts are well-supported.\nVERDICT: GOOD")
        result = run_critic(_BASE_STATE)

    assert "VERDICT: GOOD" in result["critique"]
    assert result["current_step"] == "critic_done"


def test_poor_verdict_is_preserved():
    """Stores the full LLM response when it contains VERDICT: POOR."""
    with patch("agents.critic._llm") as mock_llm:
        mock_llm.invoke.return_value = _make_response("Coverage is insufficient.\nVERDICT: POOR")
        result = run_critic(_BASE_STATE)

    assert "VERDICT: POOR" in result["critique"]


def test_graceful_degradation_on_llm_failure():
    """Defaults critique to VERDICT: GOOD and logs the error when the LLM call fails."""
    with patch("agents.critic._llm") as mock_llm:
        mock_llm.invoke.side_effect = Exception("API error")
        result = run_critic(_BASE_STATE)

    assert result["critique"] == "VERDICT: GOOD"
    assert any("Critic failed" in e for e in result["errors"])


def test_contradiction_text_included_in_prompt():
    """Detected contradictions are surfaced in the LLM prompt for further evaluation."""
    contradictory_state = {
        **_BASE_STATE,
        "extracted_facts": [
            "quantum computers are not faster than classical computers for all tasks",
            "quantum computers are faster than classical computers for all tasks",
        ],
    }
    captured = []

    def fake_invoke(messages):
        captured.extend(messages)
        r = MagicMock()
        r.content = "VERDICT: POOR"
        return r

    with patch("agents.critic._llm") as mock_llm:
        mock_llm.invoke.side_effect = fake_invoke
        run_critic(contradictory_state)

    prompt_text = " ".join(m.content for m in captured)
    assert "contradiction" in prompt_text.lower()

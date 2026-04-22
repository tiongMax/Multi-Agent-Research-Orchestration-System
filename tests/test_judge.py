"""Tests for evaluation.judge — score_report, score_state, and evaluate_batch.

All LLM calls and pipeline runs are mocked so tests run without a live
Gemini API key or research pipeline.
"""
from unittest.mock import MagicMock, patch

import pytest

from evaluation.judge import JudgeScore, _parse_json, score_report, score_state, evaluate_batch


# ── _parse_json ───────────────────────────────────────────────────────────────

def test_parse_json_clean_object():
    raw = '{"faithfulness": 4.5, "coherence": 3.0, "completeness": 4.0, "reasoning": "good"}'
    result = _parse_json(raw)
    assert result["faithfulness"] == 4.5
    assert result["reasoning"] == "good"


def test_parse_json_strips_code_fences():
    raw = '```json\n{"faithfulness": 3.0, "coherence": 3.0, "completeness": 3.0, "reasoning": ""}\n```'
    result = _parse_json(raw)
    assert result["faithfulness"] == 3.0


def test_parse_json_strips_plain_code_fence():
    raw = '```{"faithfulness": 2.0, "coherence": 2.0, "completeness": 2.0, "reasoning": "x"}```'
    result = _parse_json(raw)
    assert result["coherence"] == 2.0


def test_parse_json_raises_on_no_json():
    with pytest.raises(ValueError, match="No JSON object found"):
        _parse_json("Sorry, I cannot evaluate this.")


# ── JudgeScore ────────────────────────────────────────────────────────────────

def test_judge_score_average():
    score = JudgeScore(faithfulness=4.0, coherence=3.0, completeness=5.0)
    assert score.average == 4.0


def test_judge_score_average_rounds_to_two_decimals():
    score = JudgeScore(faithfulness=4.0, coherence=4.0, completeness=5.0)
    assert score.average == 4.33


# ── score_report ──────────────────────────────────────────────────────────────

def _make_llm_response(payload: dict) -> MagicMock:
    import json
    mock = MagicMock()
    mock.content = json.dumps(payload)
    return mock


def test_score_report_returns_judge_score():
    payload = {"faithfulness": 4.5, "coherence": 4.0, "completeness": 3.5, "reasoning": "solid"}
    with patch("evaluation.judge._llm") as mock_llm:
        mock_llm.invoke.return_value = _make_llm_response(payload)
        result = score_report(
            query="What is LangGraph?",
            sub_questions=["How does LangGraph work?"],
            facts=["LangGraph is a graph-based framework"],
            report="## LangGraph\nIt is a graph-based framework.",
        )
    assert isinstance(result, JudgeScore)
    assert result.faithfulness == 4.5
    assert result.coherence == 4.0
    assert result.completeness == 3.5
    assert result.reasoning == "solid"


def test_score_report_passes_query_in_prompt():
    payload = {"faithfulness": 3.0, "coherence": 3.0, "completeness": 3.0, "reasoning": ""}
    with patch("evaluation.judge._llm") as mock_llm:
        mock_llm.invoke.return_value = _make_llm_response(payload)
        score_report(
            query="What is retrieval-augmented generation?",
            sub_questions=[],
            facts=[],
            report="report text",
        )
    call_args = mock_llm.invoke.call_args[0][0]
    human_content = call_args[1].content
    assert "What is retrieval-augmented generation?" in human_content


def test_score_report_includes_facts_in_prompt():
    payload = {"faithfulness": 3.0, "coherence": 3.0, "completeness": 3.0, "reasoning": ""}
    with patch("evaluation.judge._llm") as mock_llm:
        mock_llm.invoke.return_value = _make_llm_response(payload)
        score_report(
            query="q",
            sub_questions=[],
            facts=["fact one", "fact two"],
            report="report",
        )
    human_content = mock_llm.invoke.call_args[0][0][1].content
    assert "fact one" in human_content
    assert "fact two" in human_content


def test_score_report_handles_missing_reasoning_key():
    payload = {"faithfulness": 4.0, "coherence": 4.0, "completeness": 4.0}
    with patch("evaluation.judge._llm") as mock_llm:
        mock_llm.invoke.return_value = _make_llm_response(payload)
        result = score_report("q", [], [], "report")
    assert result.reasoning == ""


# ── score_state ───────────────────────────────────────────────────────────────

def test_score_state_delegates_to_score_report():
    state = {
        "query": "What is pgvector?",
        "sub_questions": ["How does pgvector index work?"],
        "extracted_facts": ["pgvector extends Postgres"],
        "final_report": "## pgvector\nIt extends Postgres.",
    }
    payload = {"faithfulness": 5.0, "coherence": 5.0, "completeness": 5.0, "reasoning": "perfect"}
    with patch("evaluation.judge._llm") as mock_llm:
        mock_llm.invoke.return_value = _make_llm_response(payload)
        result = score_state(state)
    assert result.faithfulness == 5.0


def test_score_state_handles_missing_state_keys():
    state = {"query": "q"}
    payload = {"faithfulness": 1.0, "coherence": 1.0, "completeness": 1.0, "reasoning": "empty"}
    with patch("evaluation.judge._llm") as mock_llm:
        mock_llm.invoke.return_value = _make_llm_response(payload)
        result = score_state(state)
    assert isinstance(result, JudgeScore)


# ── evaluate_batch ────────────────────────────────────────────────────────────

_FAKE_STATE = {
    "query": "What is LangGraph?",
    "sub_questions": ["How does LangGraph work?"],
    "extracted_facts": ["LangGraph is a graph-based framework"],
    "final_report": "## LangGraph\nIt is a graph-based framework.",
    "retry_count": 0,
    "errors": [],
}


def test_evaluate_batch_returns_one_result_per_query():
    payload = {"faithfulness": 4.0, "coherence": 4.0, "completeness": 4.0, "reasoning": "good"}
    with patch("evaluation.judge.run", return_value=_FAKE_STATE), \
         patch("evaluation.judge._llm") as mock_llm:
        mock_llm.invoke.return_value = _make_llm_response(payload)
        results = evaluate_batch(["query one", "query two"])
    assert len(results) == 2


def test_evaluate_batch_result_contains_expected_keys():
    payload = {"faithfulness": 4.0, "coherence": 3.0, "completeness": 5.0, "reasoning": "ok"}
    with patch("evaluation.judge.run", return_value=_FAKE_STATE), \
         patch("evaluation.judge._llm") as mock_llm:
        mock_llm.invoke.return_value = _make_llm_response(payload)
        results = evaluate_batch(["test query"])
    keys = set(results[0].keys())
    assert {"query", "faithfulness", "coherence", "completeness", "average", "reasoning",
            "sub_questions", "retry_count", "errors", "report"}.issubset(keys)


def test_evaluate_batch_defaults_to_zeros_on_scoring_failure():
    with patch("evaluation.judge.run", return_value=_FAKE_STATE), \
         patch("evaluation.judge._llm") as mock_llm:
        mock_llm.invoke.side_effect = Exception("LLM unavailable")
        results = evaluate_batch(["query"])
    assert results[0]["faithfulness"] == 0
    assert results[0]["coherence"] == 0
    assert results[0]["completeness"] == 0


def test_evaluate_batch_average_is_correct():
    payload = {"faithfulness": 4.0, "coherence": 3.0, "completeness": 5.0, "reasoning": ""}
    with patch("evaluation.judge.run", return_value=_FAKE_STATE), \
         patch("evaluation.judge._llm") as mock_llm:
        mock_llm.invoke.return_value = _make_llm_response(payload)
        results = evaluate_batch(["query"])
    assert results[0]["average"] == round((4.0 + 3.0 + 5.0) / 3, 2)

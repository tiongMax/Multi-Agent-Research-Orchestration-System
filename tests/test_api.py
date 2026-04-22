"""Tests for api.main — POST /research and POST /research/stream.

The graph's run() and graph.stream() are mocked so tests run without a live
pipeline, DB, or API key.
"""
import json
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from api.main import app, _make_event

client = TestClient(app)

_FAKE_STATE = {
    "query": "What is LangGraph?",
    "sub_questions": ["How does LangGraph work?", "What are LangGraph nodes?"],
    "search_results": {},
    "extracted_facts": ["LangGraph is a graph-based orchestration framework"],
    "critique": "VERDICT: GOOD",
    "final_report": "## LangGraph\nLangGraph is a graph-based orchestration framework.",
    "current_step": "memory_save",
    "retry_count": 0,
    "errors": [],
    "memory_hits": [],
}


# ── POST /research ────────────────────────────────────────────────────────────

def test_research_returns_200_with_report():
    with patch("api.main.run", return_value=_FAKE_STATE):
        response = client.post("/research", json={"query": "What is LangGraph?"})
    assert response.status_code == 200
    body = response.json()
    assert body["report"] == _FAKE_STATE["final_report"]
    assert body["query"] == "What is LangGraph?"


def test_research_response_contains_all_fields():
    with patch("api.main.run", return_value=_FAKE_STATE):
        response = client.post("/research", json={"query": "What is LangGraph?"})
    body = response.json()
    assert set(body.keys()) == {"query", "report", "sub_questions", "extracted_facts", "errors", "retry_count"}


def test_research_passes_query_to_run():
    with patch("api.main.run", return_value=_FAKE_STATE) as mock_run:
        client.post("/research", json={"query": "What is LangGraph?"})
    mock_run.assert_called_once_with("What is LangGraph?")


def test_research_returns_422_when_query_missing():
    response = client.post("/research", json={})
    assert response.status_code == 422


def test_research_returns_empty_errors_list_when_pipeline_succeeds():
    with patch("api.main.run", return_value=_FAKE_STATE):
        response = client.post("/research", json={"query": "test"})
    assert response.json()["errors"] == []


def test_research_surfaces_errors_from_state():
    state_with_errors = {**_FAKE_STATE, "errors": ["scrape failed for http://example.com"]}
    with patch("api.main.run", return_value=state_with_errors):
        response = client.post("/research", json={"query": "test"})
    assert response.json()["errors"] == ["scrape failed for http://example.com"]


# ── _make_event ───────────────────────────────────────────────────────────────

def test_make_event_planner():
    event = _make_event("planner", {"sub_questions": ["q1", "q2", "q3"]})
    assert event == {"agent": "planner", "status": "Decomposed into 3 sub-questions"}


def test_make_event_memory_retrieve_with_hits():
    event = _make_event("memory_retrieve", {"memory_hits": ["fact A", "fact B"]})
    assert event == {"agent": "memory_retrieve", "status": "Retrieved 2 facts from memory"}


def test_make_event_memory_retrieve_no_hits():
    event = _make_event("memory_retrieve", {"memory_hits": []})
    assert event == {"agent": "memory_retrieve", "status": "No memory hits"}


def test_make_event_researcher_counts_all_sources():
    output = {"search_results": {"q1": ["r1", "r2"], "q2": ["r3"]}}
    event = _make_event("researcher", output)
    assert event == {"agent": "researcher", "status": "Found 3 sources across sub-questions"}


def test_make_event_extractor():
    event = _make_event("extractor", {"extracted_facts": ["f1", "f2", "f3", "f4"]})
    assert event == {"agent": "extractor", "status": "Extracted 4 key facts"}


def test_make_event_critic_good_verdict():
    event = _make_event("critic", {"critique": "VERDICT: GOOD — well supported"})
    assert event == {"agent": "critic", "status": "Quality verdict: GOOD"}


def test_make_event_critic_poor_verdict():
    event = _make_event("critic", {"critique": "VERDICT: POOR — missing sources"})
    assert event == {"agent": "critic", "status": "Quality verdict: POOR"}


def test_make_event_rework_shows_attempt_number():
    event = _make_event("rework", {"retry_count": 2})
    assert event == {"agent": "rework", "status": "Re-researching (attempt 2)"}


def test_make_event_writer_includes_report():
    event = _make_event("writer", {"final_report": "## Report\ncontent"})
    assert event["agent"] == "writer"
    assert event["report"] == "## Report\ncontent"
    assert event["status"] == "Synthesising final report..."


def test_make_event_memory_save():
    event = _make_event("memory_save", {})
    assert event == {"agent": "memory_save", "status": "Research saved to memory"}


def test_make_event_unknown_node_uses_node_name_as_status():
    event = _make_event("some_new_node", {})
    assert event == {"agent": "some_new_node", "status": "some_new_node"}


# ── POST /research/stream ─────────────────────────────────────────────────────

def test_stream_returns_200():
    mock_stream = [
        {"planner": {"sub_questions": ["q1"]}},
        {"writer": {"final_report": "## Report"}},
    ]
    with patch("api.main.graph") as mock_graph:
        mock_graph.stream.return_value = iter(mock_stream)
        response = client.post("/research/stream", json={"query": "What is LangGraph?"})
    assert response.status_code == 200


def test_stream_emits_agent_events_as_sse():
    mock_stream = [
        {"planner": {"sub_questions": ["q1", "q2"]}},
        {"writer": {"final_report": "## Done"}},
    ]
    with patch("api.main.graph") as mock_graph:
        mock_graph.stream.return_value = iter(mock_stream)
        response = client.post("/research/stream", json={"query": "test"})

    lines = [l for l in response.text.splitlines() if l.startswith("data:")]
    events = [json.loads(l.removeprefix("data: ").strip()) for l in lines]

    agents = [e["agent"] for e in events]
    assert "planner" in agents
    assert "writer" in agents
    assert "complete" in agents


def test_stream_final_complete_event_contains_report():
    mock_stream = [
        {"writer": {"final_report": "## Final Report"}},
    ]
    with patch("api.main.graph") as mock_graph:
        mock_graph.stream.return_value = iter(mock_stream)
        response = client.post("/research/stream", json={"query": "test"})

    lines = [l for l in response.text.splitlines() if l.startswith("data:")]
    events = [json.loads(l.removeprefix("data: ").strip()) for l in lines]
    complete = next(e for e in events if e["agent"] == "complete")
    assert complete["report"] == "## Final Report"

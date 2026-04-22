"""Integration tests for the full research pipeline.

These tests require:
  - Docker running: `docker-compose up -d postgres`
  - A valid GEMINI_API_KEY in .env or environment

They are skipped automatically when either prerequisite is missing so they
never block the unit test suite in CI or local dev without Docker.

Run explicitly with:
    pytest tests/test_integration.py -v
"""
import os

import psycopg2
import pytest
from fastapi.testclient import TestClient

# ── Prerequisites check ───────────────────────────────────────────────────────

def _db_available() -> bool:
    try:
        conn = psycopg2.connect(
            os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/research_db"),
            connect_timeout=3,
        )
        conn.close()
        return True
    except Exception:
        return False


requires_db = pytest.mark.skipif(
    not _db_available(),
    reason="Postgres unavailable — run `docker-compose up -d postgres` first",
)

requires_api_key = pytest.mark.skipif(
    not os.getenv("GEMINI_API_KEY"),
    reason="GEMINI_API_KEY not set",
)

integration = pytest.mark.skipif(
    not _db_available() or not os.getenv("GEMINI_API_KEY"),
    reason="Integration tests require Postgres + GEMINI_API_KEY",
)


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def api_client():
    from api.main import app
    return TestClient(app)


@pytest.fixture(scope="module")
def db_conn():
    conn = psycopg2.connect(
        os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/research_db")
    )
    yield conn
    conn.close()


@pytest.fixture(autouse=True)
def clean_memory(db_conn):
    """Wipe research_memory before each test to ensure isolation."""
    with db_conn.cursor() as cur:
        cur.execute("DELETE FROM research_memory")
    db_conn.commit()


# ── POST /research ────────────────────────────────────────────────────────────

@integration
def test_post_research_returns_non_empty_report(api_client):
    response = api_client.post("/research", json={"query": "What is a large language model?"})
    assert response.status_code == 200
    body = response.json()
    assert len(body["report"]) > 100


@integration
def test_post_research_response_shape(api_client):
    response = api_client.post("/research", json={"query": "What is a large language model?"})
    body = response.json()
    assert body["query"] == "What is a large language model?"
    assert isinstance(body["sub_questions"], list)
    assert len(body["sub_questions"]) >= 1
    assert isinstance(body["extracted_facts"], list)
    assert len(body["extracted_facts"]) >= 1
    assert isinstance(body["errors"], list)
    assert isinstance(body["retry_count"], int)


@integration
def test_post_research_persists_to_db(api_client, db_conn):
    api_client.post("/research", json={"query": "What is a transformer neural network?"})
    with db_conn.cursor() as cur:
        cur.execute("SELECT query, facts, report FROM research_memory")
        rows = cur.fetchall()
    assert len(rows) == 1
    assert rows[0][0] == "What is a transformer neural network?"
    assert rows[0][1]  # facts list is non-empty
    assert rows[0][2]  # report is non-empty


# ── Memory retrieval ──────────────────────────────────────────────────────────

@integration
def test_second_similar_query_gets_memory_hits(api_client):
    api_client.post("/research", json={"query": "What is a transformer neural network?"})

    from graph.orchestrator import run
    result = run("How do transformer models work in deep learning?")
    assert len(result["memory_hits"]) > 0


@integration
def test_unrelated_query_gets_no_memory_hits(api_client):
    api_client.post("/research", json={"query": "What is a transformer neural network?"})

    from graph.orchestrator import run
    result = run("What are the economic effects of deforestation in Brazil?")
    assert result["memory_hits"] == []


# ── POST /research/stream ─────────────────────────────────────────────────────

@integration
def test_stream_emits_all_expected_agents(api_client):
    import json as _json
    response = api_client.post(
        "/research/stream",
        json={"query": "What is retrieval-augmented generation?"},
    )
    assert response.status_code == 200
    lines = [l for l in response.text.splitlines() if l.startswith("data:")]
    events = [_json.loads(l.removeprefix("data: ").strip()) for l in lines]
    agents = {e["agent"] for e in events}
    assert "planner" in agents
    assert "researcher" in agents
    assert "extractor" in agents
    assert "critic" in agents
    assert "writer" in agents
    assert "complete" in agents


@integration
def test_stream_complete_event_contains_report(api_client):
    import json as _json
    response = api_client.post(
        "/research/stream",
        json={"query": "What is retrieval-augmented generation?"},
    )
    lines = [l for l in response.text.splitlines() if l.startswith("data:")]
    events = [_json.loads(l.removeprefix("data: ").strip()) for l in lines]
    complete = next(e for e in events if e["agent"] == "complete")
    assert len(complete["report"]) > 100

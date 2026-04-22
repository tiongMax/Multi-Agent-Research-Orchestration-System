"""Integration tests for the full research pipeline.

These tests require:
  - Docker running: `docker-compose up -d postgres`
  - A valid GEMINI_API_KEY in .env or environment

They are skipped automatically when either prerequisite is missing so they
never block the unit test suite in CI or local dev without Docker.

Run explicitly with:
    pytest tests/test_integration.py -v
"""
import json as _json
import os
import time

import psycopg2
import pytest
from dotenv import load_dotenv
from fastapi.testclient import TestClient

load_dotenv()

# ── Prerequisites check ───────────────────────────────────────────────────────

def _db_available() -> bool:
    try:
        conn = psycopg2.connect(
            os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5433/research_db"),
            connect_timeout=3,
        )
        conn.close()
        return True
    except Exception:
        return False


integration = pytest.mark.skipif(
    not _db_available() or not os.getenv("GEMINI_API_KEY"),
    reason="Integration tests require Postgres + GEMINI_API_KEY",
)

# ── Rate-limit retry helper ───────────────────────────────────────────────────

def _with_retry(fn, retries: int = 3, base_delay: int = 60):
    """Retry fn on 429 rate-limit errors with exponential backoff."""
    for attempt in range(retries):
        try:
            return fn()
        except Exception as e:
            if "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e):
                if attempt < retries - 1:
                    wait = base_delay * (2 ** attempt)
                    print(f"\n  Rate limited — waiting {wait}s before retry {attempt + 2}/{retries}")
                    time.sleep(wait)
                    continue
            raise
    raise RuntimeError("Exhausted retries")


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def api_client():
    from api.main import app
    return TestClient(app)


@pytest.fixture(scope="module")
def db_conn():
    conn = psycopg2.connect(
        os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5433/research_db")
    )
    yield conn
    conn.close()


@pytest.fixture(autouse=True)
def clean_memory(db_conn):
    """Wipe research_memory before each test to ensure isolation."""
    with db_conn.cursor() as cur:
        cur.execute("DELETE FROM research_memory")
    db_conn.commit()
    yield
    # Pause between tests to stay within free-tier rate limits
    time.sleep(15)


# ── POST /research ────────────────────────────────────────────────────────────

@integration
def test_post_research_returns_non_empty_report(api_client):
    def run():
        return api_client.post("/research", json={"query": "What is a large language model?"})
    response = _with_retry(run)
    assert response.status_code == 200
    assert len(response.json()["report"]) > 100


@integration
def test_post_research_response_shape(api_client):
    def run():
        return api_client.post("/research", json={"query": "What is a large language model?"})
    body = _with_retry(run).json()
    assert body["query"] == "What is a large language model?"
    assert isinstance(body["sub_questions"], list) and len(body["sub_questions"]) >= 1
    assert isinstance(body["extracted_facts"], list) and len(body["extracted_facts"]) >= 1
    assert isinstance(body["errors"], list)
    assert isinstance(body["retry_count"], int)


@integration
def test_post_research_persists_to_db(api_client, db_conn):
    def run():
        return api_client.post("/research", json={"query": "What is a transformer neural network?"})
    _with_retry(run)
    with db_conn.cursor() as cur:
        cur.execute("SELECT query, facts, report FROM research_memory")
        rows = cur.fetchall()
    assert len(rows) == 1
    assert rows[0][0] == "What is a transformer neural network?"
    assert rows[0][1]
    assert rows[0][2]


# ── Memory retrieval ──────────────────────────────────────────────────────────

@integration
def test_second_similar_query_gets_memory_hits(api_client):
    def seed():
        return api_client.post("/research", json={"query": "What is a transformer neural network?"})
    _with_retry(seed)

    from graph.orchestrator import run
    result = _with_retry(lambda: run("How do transformer models work in deep learning?"))
    assert len(result["memory_hits"]) > 0


@integration
def test_unrelated_query_gets_no_memory_hits(api_client):
    def seed():
        return api_client.post("/research", json={"query": "What is a transformer neural network?"})
    _with_retry(seed)

    from graph.orchestrator import run
    result = _with_retry(lambda: run("What are the economic effects of deforestation in Brazil?"))
    assert result["memory_hits"] == []


# ── POST /research/stream ─────────────────────────────────────────────────────

@integration
def test_stream_emits_all_expected_agents(api_client):
    def run():
        return api_client.post(
            "/research/stream",
            json={"query": "What is retrieval-augmented generation?"},
        )
    response = _with_retry(run)
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
    def run():
        return api_client.post(
            "/research/stream",
            json={"query": "What is retrieval-augmented generation?"},
        )
    response = _with_retry(run)
    lines = [l for l in response.text.splitlines() if l.startswith("data:")]
    events = [_json.loads(l.removeprefix("data: ").strip()) for l in lines]
    complete = next(e for e in events if e["agent"] == "complete")
    assert len(complete["report"]) > 100

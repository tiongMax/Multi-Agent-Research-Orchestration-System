"""Tests for memory.store (retrieve_similar and save_research).

All DB and embedding calls are mocked so tests run without a live Postgres
instance or Gemini API key.
"""
from unittest.mock import MagicMock, patch, call

from memory.store import retrieve_similar, save_research


def _make_cursor(rows: list) -> MagicMock:
    cur = MagicMock()
    cur.__enter__ = lambda s: s
    cur.__exit__ = MagicMock(return_value=False)
    cur.fetchall.return_value = rows
    return cur


def _make_conn(cur: MagicMock) -> MagicMock:
    conn = MagicMock()
    conn.cursor.return_value = cur
    return conn


# ── retrieve_similar ──────────────────────────────────────────────────────────

def test_retrieve_returns_empty_when_db_unavailable():
    """Gracefully returns [] when the DB connection fails."""
    with patch("memory.store._connect", side_effect=Exception("no db")):
        result = retrieve_similar("test query")
    assert result == []


def test_retrieve_returns_empty_when_embed_fails():
    """Gracefully returns [] when the embedding API call fails."""
    with patch("memory.store.embed_text", side_effect=Exception("api error")):
        result = retrieve_similar("test query")
    assert result == []


def test_retrieve_returns_empty_when_no_rows_match():
    """Returns [] when the similarity query finds no past sessions."""
    cur = _make_cursor([])
    conn = _make_conn(cur)
    with patch("memory.store._connect", return_value=conn), \
         patch("memory.store.embed_text", return_value=[0.1] * 768):
        result = retrieve_similar("obscure query with no past matches")
    assert result == []


def test_retrieve_flattens_facts_from_multiple_rows():
    """Merges fact lists from multiple matching past sessions into one list."""
    cur = _make_cursor([(["fact A", "fact B"],), (["fact C"],)])
    conn = _make_conn(cur)
    with patch("memory.store._connect", return_value=conn), \
         patch("memory.store.embed_text", return_value=[0.1] * 768):
        result = retrieve_similar("anything")
    assert result == ["fact A", "fact B", "fact C"]


def test_retrieve_skips_none_facts_in_rows():
    """Skips rows where facts column is NULL without crashing."""
    cur = _make_cursor([(None,), (["fact X"],)])
    conn = _make_conn(cur)
    with patch("memory.store._connect", return_value=conn), \
         patch("memory.store.embed_text", return_value=[0.1] * 768):
        result = retrieve_similar("query")
    assert result == ["fact X"]


# ── save_research ─────────────────────────────────────────────────────────────

def test_save_silently_fails_when_db_unavailable():
    """Never raises even when the DB connection fails."""
    with patch("memory.store._connect", side_effect=Exception("no db")):
        save_research("q", ["sq1"], ["fact1"], "report")


def test_save_silently_fails_when_embed_fails():
    """Never raises even when the embedding API call fails."""
    with patch("memory.store.embed_text", side_effect=Exception("api error")):
        save_research("q", ["sq1"], ["fact1"], "report")


def test_save_inserts_correct_values():
    """Passes query, sub_questions, facts, report, and embedding to INSERT."""
    fake_embedding = [0.42] * 768
    cur = _make_cursor([])
    conn = _make_conn(cur)
    with patch("memory.store._connect", return_value=conn), \
         patch("memory.store.embed_text", return_value=fake_embedding):
        save_research(
            query="What is pgvector?",
            sub_questions=["How does pgvector index work?"],
            facts=["pgvector stores embeddings in Postgres"],
            report="## Report\npgvector extends Postgres.",
        )
    cur.execute.assert_called_once()
    sql, params = cur.execute.call_args[0]
    assert "INSERT INTO research_memory" in sql
    assert params[0] == "What is pgvector?"
    assert params[1] == ["How does pgvector index work?"]
    assert params[2] == ["pgvector stores embeddings in Postgres"]
    assert params[3] == "## Report\npgvector extends Postgres."
    assert params[4] == fake_embedding


def test_save_commits_transaction():
    """Calls conn.commit() after a successful insert."""
    cur = _make_cursor([])
    conn = _make_conn(cur)
    with patch("memory.store._connect", return_value=conn), \
         patch("memory.store.embed_text", return_value=[0.1] * 768):
        save_research("q", ["sq"], ["fact"], "report")
    conn.commit.assert_called_once()

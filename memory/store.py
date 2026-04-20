import os
import psycopg2
from pgvector.psycopg2 import register_vector
from dotenv import load_dotenv

from memory.embeddings import embed_text

load_dotenv()

_SIMILARITY_THRESHOLD = 0.85
_TOP_K = 3


def _connect():
    conn = psycopg2.connect(os.getenv("DATABASE_URL"))
    register_vector(conn)
    return conn


def retrieve_similar(query: str) -> list[str]:
    """Return facts from past research whose query embedding is close to this one."""
    try:
        embedding = embed_text(query)
        conn = _connect()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT facts
                    FROM research_memory
                    WHERE 1 - (embedding <=> %s::vector) > %s
                    ORDER BY embedding <=> %s::vector
                    LIMIT %s
                    """,
                    (embedding, _SIMILARITY_THRESHOLD, embedding, _TOP_K),
                )
                rows = cur.fetchall()
        finally:
            conn.close()

        hits: list[str] = []
        for (facts,) in rows:
            if facts:
                hits.extend(facts)
        return hits
    except Exception:
        # DB unavailable during local dev — degrade gracefully
        return []


def save_research(
    query: str,
    sub_questions: list[str],
    facts: list[str],
    report: str,
) -> None:
    """Persist a completed research session to the vector store."""
    try:
        embedding = embed_text(query)
        conn = _connect()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO research_memory (query, sub_questions, facts, report, embedding)
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (query, sub_questions, facts, report, embedding),
                )
            conn.commit()
        finally:
            conn.close()
    except Exception:
        pass  # Never let a memory write crash the pipeline

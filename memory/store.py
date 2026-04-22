import os
import psycopg2
from pgvector.psycopg2 import register_vector
from dotenv import load_dotenv

from core.logger import get_logger
from memory.embeddings import embed_text

log = get_logger(__name__)

load_dotenv()

_SIMILARITY_THRESHOLD = 0.85
_TOP_K = 3


def _connect():
    conn = psycopg2.connect(os.getenv("DATABASE_URL"))
    register_vector(conn)
    return conn


def retrieve_similar(query: str) -> list[str]:
    """Return facts from past research whose query embedding is close to this one."""
    log.info("Checking memory for similar past research")
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

        if hits:
            log.info("Found %d fact(s) from past research", len(hits))
        else:
            log.info("No relevant past research found")
        return hits
    except Exception as e:
        log.warning("Memory retrieve unavailable (DB down?): %s", e)
        return []


def save_research(
    query: str,
    sub_questions: list[str],
    facts: list[str],
    report: str,
) -> None:
    """Persist a completed research session to the vector store."""
    log.info("Saving research to memory")
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
        log.info("Research saved successfully")
    except Exception as e:
        log.warning("Memory save failed (DB down?): %s", e)

import asyncio
import json
import os
import threading

import psycopg2
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sse_starlette.sse import EventSourceResponse

from api.schemas import HistoryItem, ResearchRequest, ResearchResponse
from graph.orchestrator import graph, run
from graph.state import ResearchState

app = FastAPI(title="Multi-Agent Research System")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def _build_initial(query: str) -> ResearchState:
    return {
        "query": query,
        "sub_questions": [],
        "search_results": {},
        "extracted_facts": [],
        "critique": "",
        "final_report": "",
        "current_step": "",
        "retry_count": 0,
        "errors": [],
        "memory_hits": [],
    }


def _make_event(node: str, output: dict) -> dict:
    """Map a node update to a human-readable SSE payload."""
    if node == "planner":
        n = len(output.get("sub_questions", []))
        status = f"Decomposed into {n} sub-questions"
    elif node == "memory_retrieve":
        n = len(output.get("memory_hits", []))
        status = f"Retrieved {n} facts from memory" if n else "No memory hits"
    elif node == "researcher":
        n = sum(len(v) for v in output.get("search_results", {}).values())
        status = f"Found {n} sources across sub-questions"
    elif node == "extractor":
        n = len(output.get("extracted_facts", []))
        status = f"Extracted {n} key facts"
    elif node == "critic":
        verdict = "GOOD" if "VERDICT: GOOD" in output.get("critique", "") else "POOR"
        status = f"Quality verdict: {verdict}"
    elif node == "rework":
        status = f"Re-researching (attempt {output.get('retry_count', 1)})"
    elif node == "writer":
        status = "Synthesising final report..."
    elif node == "memory_save":
        status = "Research saved to memory"
    else:
        status = node

    event: dict = {"agent": node, "status": status}
    if node == "planner":
        event["details"] = output.get("sub_questions", [])
    elif node == "extractor":
        event["details"] = output.get("extracted_facts", [])[:4]
    elif node == "writer":
        event["report"] = output.get("final_report", "")
    return event


# ── Endpoints ────────────────────────────────────────────────────────────────

@app.post("/research", response_model=ResearchResponse)
async def research(request: ResearchRequest) -> ResearchResponse:
    """Run the full pipeline and return the completed report."""
    result = await asyncio.to_thread(run, request.query)
    return ResearchResponse(
        query=result["query"],
        report=result.get("final_report", ""),
        sub_questions=result.get("sub_questions", []),
        extracted_facts=result.get("extracted_facts", []),
        errors=result.get("errors", []),
        retry_count=result.get("retry_count", 0),
    )


@app.get("/research/history", response_model=list[HistoryItem])
async def research_history(limit: int = 20) -> list[HistoryItem]:
    """Return the most recent research sessions from the vector store."""
    try:
        conn = psycopg2.connect(os.getenv("DATABASE_URL"))
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, query, report, sub_questions, facts, created_at
                    FROM research_memory
                    ORDER BY created_at DESC
                    LIMIT %s
                    """,
                    (limit,),
                )
                rows = cur.fetchall()
        finally:
            conn.close()
        return [
            HistoryItem(
                id=row[0],
                query=row[1],
                report=row[2] or "",
                sub_questions=row[3] or [],
                facts=row[4] or [],
                created_at=row[5],
            )
            for row in rows
        ]
    except Exception:
        return []


@app.post("/research/stream")
async def research_stream(request: ResearchRequest) -> EventSourceResponse:
    """Stream agent progress in real-time via Server-Sent Events."""

    async def event_generator():
        loop = asyncio.get_event_loop()
        queue: asyncio.Queue = asyncio.Queue()

        def run_graph():
            try:
                for event in graph.stream(
                    _build_initial(request.query), stream_mode="updates"
                ):
                    for node, output in event.items():
                        loop.call_soon_threadsafe(queue.put_nowait, (node, output))
            finally:
                loop.call_soon_threadsafe(queue.put_nowait, None)

        threading.Thread(target=run_graph, daemon=True).start()

        final_report = ""
        while True:
            item = await queue.get()
            if item is None:
                break
            node, output = item
            if node == "writer":
                final_report = output.get("final_report", "")
            yield {"data": json.dumps(_make_event(node, output))}

        yield {"data": json.dumps({"agent": "complete", "report": final_report})}

    return EventSourceResponse(event_generator())

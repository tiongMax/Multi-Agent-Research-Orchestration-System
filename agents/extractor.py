import os
import re
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, SystemMessage

from core.logger import get_logger
from graph.state import ResearchState

log = get_logger(__name__)

load_dotenv()

_llm = ChatGoogleGenerativeAI(
    model="gemini-3-flash-preview",
    google_api_key=os.getenv("GEMINI_API_KEY"),
    temperature=0.1,
)

_SYSTEM = """\
You are a fact extraction expert. Given search results for a research sub-question,
extract the most important, specific facts. Each fact must be:
- Concrete and verifiable
- Self-contained (understandable without surrounding context)
- Directly relevant to the sub-question

Return ONLY a numbered list of facts, one per line. No preamble."""

_MAX_CONTENT_CHARS = 1500
_MAX_SOURCES = 3


def _text(content) -> str:
    if isinstance(content, list):
        return "".join(p.get("text", "") if isinstance(p, dict) else str(p) for p in content)
    return content


def run_extractor(state: ResearchState) -> dict:
    search_results = state["search_results"]
    all_facts = list(state.get("memory_hits", []))
    errors = list(state.get("errors", []))

    log.info("Extracting facts from %d sub-questions", len(search_results))

    for sub_question, results in search_results.items():
        if not results:
            log.debug('No results for "%s", skipping', sub_question)
            continue

        context_parts = []
        for r in results[:_MAX_SOURCES]:
            content = (r.get("content") or r.get("snippet", ""))[:_MAX_CONTENT_CHARS]
            if content:
                context_parts.append(f"Source: {r.get('url', 'unknown')}\n{content}")

        if not context_parts:
            continue

        prompt = (
            f"Sub-question: {sub_question}\n\n"
            + "\n\n---\n\n".join(context_parts)
        )

        before = len(all_facts)
        try:
            response = _llm.invoke([
                SystemMessage(content=_SYSTEM),
                HumanMessage(content=prompt),
            ])
            for line in _text(response.content).strip().splitlines():
                fact = re.sub(r"^\d+[.)]\s*", "", line.strip())
                if fact:
                    all_facts.append(fact)
            log.debug('"%s" → %d facts', sub_question, len(all_facts) - before)
        except Exception as e:
            log.error('Extraction failed for "%s": %s', sub_question, e)
            errors.append(f"Extractor failed for '{sub_question}': {e}")

    log.info("Total: %d facts extracted", len(all_facts))

    return {
        "extracted_facts": all_facts,
        "errors": errors,
        "current_step": "extractor_done",
    }

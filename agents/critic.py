import os
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, SystemMessage

from core.logger import get_logger
from graph.state import ResearchState
from tools.cross_reference import find_contradictions

log = get_logger(__name__)

load_dotenv()

_llm = ChatGoogleGenerativeAI(
    model="gemini-3-flash-preview",
    google_api_key=os.getenv("GEMINI_API_KEY"),
    temperature=0.2,
)

_SYSTEM = """\
You are a critical research evaluator. Given a query and its extracted facts, assess:
1. Whether facts are specific and well-supported (not vague)
2. Whether they collectively answer the original query
3. Whether any contradictions or gaps exist

End your evaluation with exactly one of these verdicts on its own line:
VERDICT: GOOD   — quality is sufficient to write a report
VERDICT: POOR   — significant gaps, contradictions, or missing coverage"""


def _text(content) -> str:
    if isinstance(content, list):
        return "".join(p.get("text", "") if isinstance(p, dict) else str(p) for p in content)
    return content


def run_critic(state: ResearchState) -> dict:
    facts = state["extracted_facts"]
    errors = list(state.get("errors", []))

    log.info("Evaluating %d facts", len(facts))

    contradictions = find_contradictions(facts)
    contradiction_text = ""
    if contradictions:
        log.warning("Detected %d potential contradiction(s)", len(contradictions))
        pairs = "\n".join(f"  • '{a}' vs '{b}'" for a, b in contradictions[:3])
        contradiction_text = f"\n\nDetected potential contradictions:\n{pairs}"

    facts_text = "\n".join(f"{i + 1}. {f}" for i, f in enumerate(facts))
    prompt = (
        f"Original query: {state['query']}\n\n"
        f"Extracted facts:\n{facts_text}"
        f"{contradiction_text}"
    )

    try:
        response = _llm.invoke([
            SystemMessage(content=_SYSTEM),
            HumanMessage(content=prompt),
        ])
        critique = _text(response.content).strip()
    except Exception as e:
        log.error("Critic LLM failed, defaulting to GOOD: %s", e)
        errors.append(f"Critic failed: {e}")
        critique = "VERDICT: GOOD"  # graceful degradation

    if "VERDICT: GOOD" in critique:
        log.info("Verdict: GOOD — proceeding to write report")
    else:
        log.warning("Verdict: POOR — research will be reworked")

    return {
        "critique": critique,
        "errors": errors,
        "current_step": "critic_done",
    }

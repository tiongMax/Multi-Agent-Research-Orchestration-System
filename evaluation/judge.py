"""
LLM-as-judge evaluation pipeline.

Usage:
    python -m evaluation.judge --input queries.json --output results.json

queries.json format: ["query one", "query two", ...]
"""

import argparse
import json
import os
import re
from dataclasses import dataclass, asdict

from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, SystemMessage

from graph.orchestrator import run
from graph.state import ResearchState

load_dotenv()

_llm = ChatGoogleGenerativeAI(
    model="gemini-2.0-flash",
    google_api_key=os.getenv("GEMINI_API_KEY"),
    temperature=0.1,
)

_SYSTEM = """\
You are an expert research report evaluator. Score the report on three dimensions, each 1.0–5.0:

- faithfulness:   Are all claims grounded in the provided source facts? Penalise hallucinations.
- coherence:      Is the report logically structured and easy to follow?
- completeness:   Does the report fully address the original query and all sub-questions?

Respond with valid JSON only — no markdown, no prose:
{"faithfulness": <float>, "coherence": <float>, "completeness": <float>, "reasoning": "<brief note>"}"""


@dataclass
class JudgeScore:
    faithfulness: float
    coherence: float
    completeness: float
    reasoning: str = ""

    @property
    def average(self) -> float:
        return round((self.faithfulness + self.coherence + self.completeness) / 3, 2)


def _parse_json(text: str) -> dict:
    """Extract the first JSON object from a model response, stripping code fences."""
    text = re.sub(r"```(?:json)?", "", text).strip()
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        raise ValueError(f"No JSON object found in response: {text!r}")
    return json.loads(match.group())


def score_report(
    query: str,
    sub_questions: list[str],
    facts: list[str],
    report: str,
) -> JudgeScore:
    """Score a single report across all three dimensions."""
    facts_text = "\n".join(f"- {f}" for f in facts)
    subq_text = "\n".join(f"{i + 1}. {q}" for i, q in enumerate(sub_questions))
    prompt = (
        f"Original query: {query}\n\n"
        f"Sub-questions:\n{subq_text}\n\n"
        f"Source facts:\n{facts_text}\n\n"
        f"Report:\n{report}"
    )
    response = _llm.invoke([SystemMessage(content=_SYSTEM), HumanMessage(content=prompt)])
    data = _parse_json(response.content)
    return JudgeScore(
        faithfulness=float(data["faithfulness"]),
        coherence=float(data["coherence"]),
        completeness=float(data["completeness"]),
        reasoning=data.get("reasoning", ""),
    )


def score_state(state: ResearchState) -> JudgeScore:
    """Convenience wrapper — score a completed ResearchState directly."""
    return score_report(
        query=state["query"],
        sub_questions=state.get("sub_questions", []),
        facts=state.get("extracted_facts", []),
        report=state.get("final_report", ""),
    )


def evaluate_batch(queries: list[str]) -> list[dict]:
    """Run the full pipeline + judge for each query. Returns list of result dicts."""
    results = []
    for i, query in enumerate(queries, 1):
        print(f"[{i}/{len(queries)}] Running: {query}")
        state = run(query)
        try:
            score = score_state(state)
        except Exception as e:
            score = JudgeScore(faithfulness=0, coherence=0, completeness=0, reasoning=str(e))

        results.append({
            "query": query,
            **asdict(score),
            "average": score.average,
            "sub_questions": state.get("sub_questions", []),
            "retry_count": state.get("retry_count", 0),
            "errors": state.get("errors", []),
            "report": state.get("final_report", ""),
        })
        print(
            f"    faithfulness={score.faithfulness}  "
            f"coherence={score.coherence}  "
            f"completeness={score.completeness}  "
            f"avg={score.average}"
        )
    return results


def _print_summary(results: list[dict]) -> None:
    n = len(results)
    for dim in ("faithfulness", "coherence", "completeness", "average"):
        avg = sum(r[dim] for r in results) / n
        print(f"  {dim:<14} {avg:.2f}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Batch-evaluate research reports.")
    parser.add_argument("--input", required=True, help="JSON file containing a list of query strings")
    parser.add_argument("--output", required=True, help="Output JSON file for scored results")
    args = parser.parse_args()

    with open(args.input) as f:
        queries: list[str] = json.load(f)

    results = evaluate_batch(queries)

    with open(args.output, "w") as f:
        json.dump(results, f, indent=2)

    print(f"\nEvaluated {len(results)} queries — summary:")
    _print_summary(results)
    print(f"Results written to {args.output}")

import os
import re
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, SystemMessage

from graph.state import ResearchState

load_dotenv()

_llm = ChatGoogleGenerativeAI(
    model="gemini-2.0-flash",
    google_api_key=os.getenv("GEMINI_API_KEY"),
    temperature=0.3,
)

_SYSTEM = """\
You are a research planning expert. Given a user query, decompose it into 3-5 specific,
focused sub-questions that together would fully answer the original query.
Return ONLY a numbered list of sub-questions — no preamble, no explanation."""


def run_planner(state: ResearchState) -> dict:
    response = _llm.invoke([
        SystemMessage(content=_SYSTEM),
        HumanMessage(content=f"Query: {state['query']}"),
    ])

    sub_questions = []
    for line in response.content.strip().splitlines():
        line = line.strip()
        cleaned = re.sub(r"^\d+[.)]\s*", "", line)
        if cleaned:
            sub_questions.append(cleaned)

    return {
        "sub_questions": sub_questions,
        "current_step": "planner_done",
    }

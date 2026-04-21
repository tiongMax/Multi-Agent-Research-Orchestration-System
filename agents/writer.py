import os
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, SystemMessage

from graph.state import ResearchState

load_dotenv()

_llm = ChatGoogleGenerativeAI(
    model="gemini-2.0-flash",
    google_api_key=os.getenv("GEMINI_API_KEY"),
    temperature=0.4,
)

_SYSTEM = """\
You are an expert research writer. Using the provided query, extracted facts, and critic evaluation,
write a comprehensive research report that:
- Opens with a clear introduction that restates the query
- Organises the body into thematic sections with ## headers
- Grounds every claim in the provided facts
- Closes with a concise conclusion
- Is 400–600 words
- Uses markdown formatting throughout"""


def run_writer(state: ResearchState) -> dict:
    facts_text = "\n".join(f"- {f}" for f in state["extracted_facts"])
    prompt = (
        f"Query: {state['query']}\n\n"
        f"Extracted facts:\n{facts_text}\n\n"
        f"Critic's evaluation:\n{state.get('critique', 'N/A')}"
    )

    errors = list(state.get("errors", []))
    try:
        response = _llm.invoke([
            SystemMessage(content=_SYSTEM),
            HumanMessage(content=prompt),
        ])
        final_report = response.content.strip()
    except Exception as e:
        errors.append(f"Writer failed: {e}")
        final_report = "Report generation failed. Please retry."

    return {
        "final_report": final_report,
        "errors": errors,
        "current_step": "complete",
    }

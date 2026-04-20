import os
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

_MODEL = "models/text-embedding-004"


def embed_text(text: str) -> list[float]:
    result = genai.embed_content(
        model=_MODEL,
        content=text,
        task_type="retrieval_document",
    )
    return result["embedding"]

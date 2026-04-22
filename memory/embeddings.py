import os
from google import genai
from google.genai import types
from dotenv import load_dotenv

load_dotenv()
_client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

_MODEL = "text-embedding-004"


def embed_text(text: str) -> list[float]:
    result = _client.models.embed_content(
        model=_MODEL,
        contents=text,
        config=types.EmbedContentConfig(task_type="RETRIEVAL_DOCUMENT"),
    )
    return result.embeddings[0].values

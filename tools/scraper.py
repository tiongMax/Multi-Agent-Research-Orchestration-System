import httpx
from bs4 import BeautifulSoup
from tenacity import retry, stop_after_attempt, wait_exponential

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0 Safari/537.36"
    )
}
_MAX_CHARS = 4000


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
async def scrape_url(url: str) -> str:
    """Fetch a URL and return cleaned visible text, capped at _MAX_CHARS."""
    async with httpx.AsyncClient(timeout=15, headers=_HEADERS, follow_redirects=True) as client:
        response = await client.get(url)
        response.raise_for_status()

    soup = BeautifulSoup(response.text, "lxml")
    for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
        tag.decompose()

    text = soup.get_text(separator="\n", strip=True)
    return text[:_MAX_CHARS]

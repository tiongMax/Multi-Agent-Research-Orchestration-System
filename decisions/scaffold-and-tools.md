# Technical Decisions — Scaffold & Tools

Covers the project structure, infrastructure, shared state schema, and the three core tools (search, scraper, cross-reference).

---

## 1. PostgreSQL + pgvector over a dedicated vector DB

**Decision:** Run pgvector inside a Docker container as the vector store.

**Alternatives considered:** Pinecone, Chroma, Weaviate, FAISS (in-memory).

**Why pgvector:**
- Keeps the entire stack local and free — no external service, no extra API key.
- PostgreSQL is already the natural choice for storing structured research data (queries, facts, reports); adding a vector column to the same table avoids a second service.
- The `ivfflat` index gives approximate nearest-neighbour search fast enough for this scale (hundreds to low thousands of stored queries).
- SQL is familiar — schema changes, debugging, and manual inspection are straightforward.

**Trade-off:** pgvector's ANN recall and write throughput lag behind purpose-built vector DBs at millions-of-vectors scale. Acceptable here; would revisit at production scale.

---

## 2. Docker for the database, not a managed service

**Decision:** Ship a `docker-compose.yml` that spins up pgvector locally.

**Why:**
- Zero-cost local development — no cloud account needed to run the project.
- The `pgvector/pgvector:pg16` image comes with the extension pre-installed; no manual `CREATE EXTENSION` step needed beyond `init.sql`.
- `healthcheck` + `depends_on: condition: service_healthy` ensures the app container never starts before the DB is ready.

**Trade-off:** Developers need Docker installed. Mitigated by clear setup instructions.

---

## 3. TypedDict for shared state, not Pydantic

**Decision:** `ResearchState` is a `TypedDict`, not a Pydantic `BaseModel`.

**Why:**
- LangGraph's `StateGraph` accepts `TypedDict` natively and merges node return dicts automatically.
- `TypedDict` adds zero runtime overhead — no validation, no serialisation cost on every state transition.
- Static type checkers (mypy, pyright) still catch key typos and wrong types at development time.

**Trade-off:** No runtime validation means a node returning a wrongly typed value fails silently or causes a downstream error rather than a clear validation exception. Acceptable during development where all nodes are in-house.

---

## 4. ddgs (DuckDuckGo) for web search

**Decision:** Use the `ddgs` package for all web searches.

**Alternatives considered:** SerpAPI, Brave Search API, Google Custom Search.

**Why ddgs:**
- Completely free — no API key, no rate-limit tier, no billing setup.
- Returns structured results (title, URL, body snippet) ready to pass to the scraper.
- Simple synchronous interface wraps neatly into a retried function.

**Trade-off:** DuckDuckGo does not expose a paid tier with higher quotas or result quality guarantees. For a production system serving many concurrent users, a paid search API would be more reliable.

---

## 5. httpx + BeautifulSoup (lxml) for scraping, synchronous

**Decision:** Use `httpx.Client` (sync) with BeautifulSoup/lxml to extract page text.

**Alternatives considered:** `requests`, `playwright` (for JS-rendered pages), `scrapy`.

**Why httpx sync:**
- httpx has a modern API with timeout and redirect handling built in.
- Sync client avoids event-loop complexity inside LangGraph nodes (see Agents decisions for the full reasoning).
- BeautifulSoup + lxml is fast for stripping boilerplate tags (nav, footer, scripts) and extracting readable text.
- Content is capped at 4000 characters to stay within LLM context limits without truncation logic.

**Trade-off:** Does not handle JavaScript-rendered pages (SPAs). Most research sources (Wikipedia, news sites, blogs) are server-rendered, so this covers the common case. Playwright could be added as a fallback for JS-heavy URLs.

---

## 6. Heuristic contradiction detection in cross_reference.py

**Decision:** Detect contradictions by checking for keyword overlap + negation-word polarity mismatch, rather than using an LLM.

**Why heuristic:**
- A dedicated LLM call per fact-pair would be prohibitively slow (O(n²) pairs) and costly for large fact lists.
- The heuristic catches the most common class of contradiction: one fact asserts X, another asserts "not X" about the same subject.
- The result is passed to the Critic agent, which uses an LLM for nuanced evaluation — the heuristic is a pre-filter, not the final judge.

**Trade-off:** Misses semantic contradictions that don't use explicit negation words (e.g., "the company grew 10%" vs "revenue declined"). The LLM critic is the backstop for these cases.

---

## 7. Tenacity for retry logic on tools

**Decision:** Use the `tenacity` library for exponential-backoff retries on `search_web` and `scrape_url`.

**Why:**
- Declarative `@retry` decorators keep retry logic out of business logic.
- Exponential backoff with jitter is the correct strategy for transient network failures and rate limits.
- 3 attempts with `wait_exponential(min=2, max=10)` balances resilience against pipeline latency.

**Trade-off:** A tool that consistently fails will still take ~14 seconds (2+4+8) before giving up. Acceptable for a research pipeline where latency is already measured in tens of seconds.

---
description: "Build a latency-aware query router that dispatches between a structured KV-cache lookup, vector search, and the existing Neo4j graph retrieval, for this RAG codebase."
agent: "agent"
---
# Build the query router (structured cache + vector + graph)

You are extending the existing `graph_rag/` RAG system in this workspace. It currently
answers questions purely via entity-anchored Neo4j graph traversal
(`graph_rag/retrieval.py`). Your job: add a **query router** that also uses a
structured key-value cache and a vector store, choosing the fastest sufficient
path per question instead of always running full graph retrieval.

Read these files first to understand existing conventions before writing anything:
[graph_rag/config.py](../../graph_rag/config.py), [graph_rag/retrieval.py](../../graph_rag/retrieval.py),
[graph_rag/neo4j_store.py](../../graph_rag/neo4j_store.py), [graph_rag/pipeline.py](../../graph_rag/pipeline.py),
[query.py](../../query.py). Match their style: dataclass `Settings`, module-level functions
(not classes) with docstrings explaining *why*, `logging.getLogger(__name__)`, type hints,
env-var driven configuration with sane defaults.

## Architecture to build

```
question
   │
   ▼
[1] Structured cache lookup (new: graph_rag/query_cache.py)
   │  cache key = hash(normalized question) + current graph_version
   │  HIT  → return cached answer immediately, skip everything below
   │  MISS ↓
[2] Entity extraction + anchor resolution (existing: extract_entities, _match_entity_ids)
   │
   ├─ anchors resolved ─────► [3a] Graph retrieval (existing: structured_retriever,
   │                                source_text_retriever, hop=2, char-budgeted)
   │
   └─ no anchors / graph context too thin ─► [3b] Vector similarity search (new:
                                                    graph_rag/vector_store.py)
   │
   ▼
[4] Merge available context (graph + vector, deduped, within max_context_chars)
   │
   ▼
[5] LLM answer (existing prompt in answer_question)
   │
   ▼
[6] Write (question_hash, graph_version) -> answer into the cache, return answer
```

## Component 1 — Structured KV cache (`graph_rag/query_cache.py`)

Goal: near-zero latency for repeated/near-duplicate questions, and correctness on
re-ingestion (stale answers must never be served after the graph changes).

- Normalize the question before hashing: lowercase, strip, collapse whitespace.
- Cache key = `sha256(normalized_question)` **plus** a `graph_version` value, so a
  full re-ingestion invalidates every prior entry without needing per-key eviction
  logic. Store `graph_version` as a single counter/timestamp node property in Neo4j
  (e.g. `MERGE (v:GraphMeta {key:"version"}) SET v.value = timestamp()`), bumped once
  at the end of `run_ingestion_pipeline` (`graph_rag/pipeline.py`). Read it once per
  process and cache it, not per query.
- Start with a local, dependency-light backing store — an LRU in-memory dict
  (`functools.lru_cache`-style, or a small `OrderedDict`) with a max entry count and a
  TTL, persisted to a local SQLite file (stdlib `sqlite3`, no new service) so the cache
  survives process restarts. Do NOT introduce Redis or another external service unless
  explicitly asked later — this must run with zero extra infrastructure.
- Public API to expose: `get_cached_answer(question: str) -> str | None` and
  `set_cached_answer(question: str, answer: str) -> None`. Both take the Neo4jGraph
  connection to read `graph_version` lazily.
- Add `QUERY_CACHE_TTL_SECONDS` (default 3600) and `QUERY_CACHE_MAX_ENTRIES` (default
  1000) to `Settings`/`.env`, following the exact pattern of `RETRIEVAL_HOPS` in
  `graph_rag/config.py`.

## Component 2 — Vector store (`graph_rag/vector_store.py`)

Goal: a semantic fallback for questions that name no clear entity (extraction returns
an empty list, or resolves to zero graph anchors) — the graph/full-text path cannot
answer these today.

- Reuse Neo4j itself rather than standing up a second datastore: use
  `langchain_neo4j.Neo4jVector` (already an implied dependency via `langchain-neo4j`)
  to create a vector index over `Document` node `text` properties (the same nodes
  already written by `write_graph_documents` with `include_source=True` — do not
  create a second copy of the chunks).
- Embeddings: default to a local `sentence-transformers` model via
  `langchain_huggingface.HuggingFaceEmbeddings` (no extra API key needed, since only
  `GROQ_API_KEY` exists today). Make the model name configurable
  (`EMBEDDING_MODEL`, default `sentence-transformers/all-MiniLM-L6-v2`).
- Public API: `build_vector_store(graph_settings) -> Neo4jVector` and
  `vector_search(store, question: str, k: int = 5) -> str` returning joined chunk text,
  matching the return shape of `source_text_retriever` in `graph_rag/retrieval.py` so
  it can be merged the same way.
- Embeddings must be (re)built as part of ingestion (`graph_rag/pipeline.py`), not
  lazily at query time — add this as a step after `write_graph_documents`.

## Component 3 — The router (`graph_rag/router.py`)

- Single public entry point: `route_and_answer(graph, llm, vector_store, question, settings) -> str`,
  replacing the direct `answer_question` call in `query.py`.
- Steps, in order, short-circuiting as soon as one produces a usable result:
  1. `get_cached_answer` — return immediately on hit.
  2. `extract_entities` + `_match_entity_ids` (reuse existing functions, do not
     duplicate their logic) — if this resolves to at least one node id, run
     `structured_retriever` + `source_text_retriever` (existing, hop=2, char-budgeted
     per the existing design).
  3. If step 2 resolved no anchors, OR the resulting context is shorter than a
     configurable `MIN_GRAPH_CONTEXT_CHARS` threshold (default 200 — i.e. "too thin to
     be useful"), additionally run `vector_search` and append its result.
  4. Combine whatever context was gathered (graph section + vector section,
     deduplicated, still bounded by `max_context_chars` split proportionally between
     the two sources if both fired) and generate the final answer via the existing
     `_ANSWER_PROMPT` chain in `graph_rag/retrieval.py` (reuse it, don't duplicate the
     prompt).
  5. `set_cached_answer` before returning.
- Log which path(s) fired for every question (cache hit / graph / vector / both) at
  INFO level — this is essential for evaluating whether the router is actually saving
  latency, and for debugging wrong answers later.

## Prerequisite fixes (do these first — the router will silently produce wrong/duplicate
results without them)

1. Add a uniqueness constraint on `__Entity__.id` in `ensure_entity_fulltext_index`
   (or a new `ensure_constraints` function) in `graph_rag/retrieval.py`:
   `CREATE CONSTRAINT IF NOT EXISTS FOR (n:__Entity__) REQUIRE n.id IS UNIQUE` — run it
   once at the start of both ingestion and query paths, same pattern as the existing
   fulltext index creation.
2. Verify `write_graph_documents` behavior on re-ingestion of identical content (does
   it duplicate `Document` nodes?). Write a test proving idempotency; if it does
   duplicate, add a `MERGE` key derived from a content hash before writing.

## Testing requirements

- All new logic (cache key derivation, TTL expiry, router branch selection) must have
  **offline unit tests** that mock `Neo4jGraph`/`Neo4jVector`/the LLM — do not make
  every test require a live `.env` like the existing `tests/test_retrieval.py` does.
  Put these in `tests/test_query_cache.py` and `tests/test_router.py`.
- Add one live smoke test (skipped without `.env`, matching the existing pattern) that
  exercises the full router end-to-end: cache miss → graph path → cache hit on repeat.

## Config additions (`.env` / `graph_rag/config.py`)

Add, with defaults, following the exact style of existing `RETRIEVAL_*` vars:
`QUERY_CACHE_TTL_SECONDS=3600`, `QUERY_CACHE_MAX_ENTRIES=1000`,
`EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2`,
`MIN_GRAPH_CONTEXT_CHARS=200`.

## Explicitly out of scope for this task

- Do not introduce Redis, a separate vector DB service, or any new external
  infrastructure — everything must run against the existing Neo4j instance plus local
  process memory/SQLite.
- Do not change the existing graph hop/char-budget behavior in
  `graph_rag/retrieval.py` — only add to it (the vector fallback and cache wrap
  around it, they don't replace it).
- Do not implement full entity-resolution/dedup (fuzzy id merging) as part of this
  task — that's a separate, already-identified follow-up.

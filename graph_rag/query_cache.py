"""Local cache mapping normalized questions to final answers, for the query router.

Backed by SQLite (stdlib only - no new service) so answers survive process restarts.
Cache keys combine the normalized question with a `graph_version` marker stored in
Neo4j, so a full re-ingestion invalidates every previously cached answer without any
per-key eviction logic - see `bump_graph_version`, called once at the end of
`graph_rag.pipeline.run_ingestion_pipeline`.
"""
from __future__ import annotations

import hashlib
import logging
import re
import sqlite3
import time
from pathlib import Path

from langchain_neo4j import Neo4jGraph

logger = logging.getLogger(__name__)

DEFAULT_CACHE_PATH = Path(".cache/query_cache.sqlite3")

_WHITESPACE_RE = re.compile(r"\s+")

# Read once per process (see module docstring) rather than once per query, since it
# only changes when ingestion runs, not per question.
_graph_version_cache: str | None = None


def _normalize_question(question: str) -> str:
    """Lowercase/trim/collapse whitespace so trivially different phrasing of the same
    question (extra spaces, capitalization) still hits the same cache entry."""
    return _WHITESPACE_RE.sub(" ", question.strip().lower())


def get_graph_version(graph: Neo4jGraph) -> str:
    """Return the current graph version marker, initializing it to 0 if absent."""
    global _graph_version_cache
    if _graph_version_cache is None:
        rows = graph.query(
            "MERGE (v:GraphMeta {key: 'version'}) "
            "ON CREATE SET v.value = 0 "
            "RETURN v.value AS value"
        )
        _graph_version_cache = str(rows[0]["value"]) if rows else "0"
    return _graph_version_cache


def bump_graph_version(graph: Neo4jGraph) -> None:
    """Advance the graph version marker - call once ingestion has finished writing,
    so every answer cached against the old graph is treated as stale."""
    global _graph_version_cache
    graph.query(
        "MERGE (v:GraphMeta {key: 'version'}) "
        "SET v.value = coalesce(v.value, 0) + 1"
    )
    _graph_version_cache = None  # force a fresh read next time this process needs it


class QueryCache:
    """SQLite-backed cache of (question, graph_version) -> answer, with a TTL and a
    max entry count (oldest entries evicted first once the cap is exceeded)."""

    def __init__(
        self,
        path: Path | str = DEFAULT_CACHE_PATH,
        ttl_seconds: int = 3600,
        max_entries: int = 1000,
    ) -> None:
        self._ttl_seconds = ttl_seconds
        self._max_entries = max_entries
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS query_cache ("
            "cache_key TEXT PRIMARY KEY, answer TEXT NOT NULL, created_at REAL NOT NULL)"
        )
        self._conn.commit()

    def _make_key(self, question: str, graph_version: str) -> str:
        normalized = _normalize_question(question)
        return hashlib.sha256(f"{graph_version}:{normalized}".encode("utf-8")).hexdigest()

    def get(self, question: str, graph_version: str) -> str | None:
        """Return the cached answer, or None on a miss or an expired entry."""
        key = self._make_key(question, graph_version)
        row = self._conn.execute(
            "SELECT answer, created_at FROM query_cache WHERE cache_key = ?", (key,)
        ).fetchone()
        if row is None:
            return None

        answer, created_at = row
        if time.time() - created_at > self._ttl_seconds:
            self._conn.execute("DELETE FROM query_cache WHERE cache_key = ?", (key,))
            self._conn.commit()
            return None
        return answer

    def set(self, question: str, graph_version: str, answer: str) -> None:
        key = self._make_key(question, graph_version)
        self._conn.execute(
            "INSERT OR REPLACE INTO query_cache (cache_key, answer, created_at) VALUES (?, ?, ?)",
            (key, answer, time.time()),
        )
        self._evict_oldest_if_over_capacity()
        self._conn.commit()

    def _evict_oldest_if_over_capacity(self) -> None:
        (count,) = self._conn.execute("SELECT COUNT(*) FROM query_cache").fetchone()
        excess = count - self._max_entries
        if excess > 0:
            self._conn.execute(
                "DELETE FROM query_cache WHERE cache_key IN ("
                "SELECT cache_key FROM query_cache ORDER BY created_at ASC LIMIT ?)",
                (excess,),
            )

    def close(self) -> None:
        self._conn.close()


# Module-level singleton so `get_cached_answer`/`set_cached_answer` are simple
# functions for callers (matching the style of the rest of `graph_rag`), while still
# reusing one SQLite connection per process.
_cache_singleton: QueryCache | None = None


def _get_cache(ttl_seconds: int, max_entries: int) -> QueryCache:
    global _cache_singleton
    if _cache_singleton is None:
        _cache_singleton = QueryCache(ttl_seconds=ttl_seconds, max_entries=max_entries)
    return _cache_singleton


def get_cached_answer(
    graph: Neo4jGraph, question: str, ttl_seconds: int = 3600, max_entries: int = 1000
) -> str | None:
    """Return a cached answer for this question if present and not expired/stale."""
    cache = _get_cache(ttl_seconds, max_entries)
    answer = cache.get(question, get_graph_version(graph))
    if answer is not None:
        logger.debug("Query cache hit for question: %s", question)
    return answer


def set_cached_answer(
    graph: Neo4jGraph, question: str, answer: str, ttl_seconds: int = 3600, max_entries: int = 1000
) -> None:
    """Store an answer in the cache, keyed to the current graph version."""
    cache = _get_cache(ttl_seconds, max_entries)
    cache.set(question, get_graph_version(graph), answer)

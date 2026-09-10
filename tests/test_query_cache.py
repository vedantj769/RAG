"""Offline unit tests for graph_rag.query_cache - no live Neo4j/LLM required."""
from __future__ import annotations

import time
from unittest.mock import MagicMock

import pytest

from graph_rag import query_cache
from graph_rag.query_cache import QueryCache, bump_graph_version, get_graph_version


@pytest.fixture(autouse=True)
def _reset_module_singletons(monkeypatch):
    """Each test gets a clean slate: the module caches a graph version and a
    QueryCache singleton at import scope, which would otherwise leak between tests."""
    monkeypatch.setattr(query_cache, "_graph_version_cache", None)
    monkeypatch.setattr(query_cache, "_cache_singleton", None)


def _mock_graph(version: int = 0) -> MagicMock:
    graph = MagicMock()
    graph.query.return_value = [{"value": version}]
    return graph


class TestQueryCacheClass:
    def test_miss_then_hit(self, tmp_path):
        cache = QueryCache(path=tmp_path / "cache.sqlite3", ttl_seconds=3600, max_entries=10)
        assert cache.get("What is OEE?", "1") is None

        cache.set("What is OEE?", "1", "OEE stands for Overall Equipment Effectiveness.")
        assert cache.get("What is OEE?", "1") == "OEE stands for Overall Equipment Effectiveness."

    def test_normalization_makes_equivalent_questions_share_a_key(self, tmp_path):
        cache = QueryCache(path=tmp_path / "cache.sqlite3")
        cache.set("What is OEE?", "1", "answer-a")

        assert cache.get("  what is oee?  ", "1") == "answer-a"
        assert cache.get("What   is OEE?", "1") == "answer-a"

    def test_different_graph_version_is_a_miss(self, tmp_path):
        cache = QueryCache(path=tmp_path / "cache.sqlite3")
        cache.set("What is OEE?", "1", "answer-a")

        assert cache.get("What is OEE?", "2") is None

    def test_entry_expires_after_ttl(self, tmp_path, monkeypatch):
        cache = QueryCache(path=tmp_path / "cache.sqlite3", ttl_seconds=100)
        cache.set("What is OEE?", "1", "answer-a")

        real_time = time.time
        monkeypatch.setattr(time, "time", lambda: real_time() + 1000)
        assert cache.get("What is OEE?", "1") is None

    def test_max_entries_evicts_oldest_first(self, tmp_path):
        cache = QueryCache(path=tmp_path / "cache.sqlite3", max_entries=2)
        cache.set("question one", "1", "answer-1")
        cache.set("question two", "1", "answer-2")
        cache.set("question three", "1", "answer-3")

        assert cache.get("question one", "1") is None
        assert cache.get("question two", "1") == "answer-2"
        assert cache.get("question three", "1") == "answer-3"


class TestGraphVersion:
    def test_get_graph_version_reads_once_per_process(self):
        graph = _mock_graph(version=5)
        assert get_graph_version(graph) == "5"
        assert get_graph_version(graph) == "5"
        # Only the first call should hit Neo4j - the second is served from the module cache.
        assert graph.query.call_count == 1

    def test_bump_graph_version_forces_a_fresh_read(self):
        graph = _mock_graph(version=5)
        get_graph_version(graph)

        bump_graph_version(graph)
        graph.query.return_value = [{"value": 6}]
        assert get_graph_version(graph) == "6"

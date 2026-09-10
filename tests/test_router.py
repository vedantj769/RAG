"""Offline unit tests for graph_rag.router's path-selection logic.

Every retrieval/caching dependency is monkeypatched at the point of use (i.e. on the
`graph_rag.router` module, where they were imported into) so these tests exercise only
the router's own branching decisions - no live Neo4j, LLM, or embedding model needed.
"""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from graph_rag import router as router_module
from graph_rag.config import Settings
from graph_rag.router import route_and_answer


def _settings(**overrides) -> Settings:
    defaults = dict(
        groq_api_key="test-key",
        groq_model="test-model",
        neo4j_uri="bolt://localhost:7687",
        neo4j_username="neo4j",
        neo4j_password="password",
        neo4j_database="neo4j",
        documents_dir="data/documents",
        chunk_size=1000,
        chunk_overlap=200,
        retrieval_top_k=5,
        retrieval_hops=2,
        retrieval_max_context_chars=8000,
        min_graph_context_chars=200,
        embedding_model="sentence-transformers/all-MiniLM-L6-v2",
        query_cache_ttl_seconds=3600,
        query_cache_max_entries=1000,
        log_level="INFO",
    )
    defaults.update(overrides)
    return Settings(**defaults)


@pytest.fixture(autouse=True)
def _patch_dependencies(monkeypatch):
    """Stub every external dependency to a sane, overridable default per test."""
    monkeypatch.setattr(router_module, "ensure_entity_fulltext_index", MagicMock())
    monkeypatch.setattr(router_module, "get_cached_answer", MagicMock(return_value=None))
    monkeypatch.setattr(router_module, "set_cached_answer", MagicMock())
    monkeypatch.setattr(router_module, "extract_entities", MagicMock(return_value=["OEE"]))
    monkeypatch.setattr(router_module, "match_entities", MagicMock(return_value=["kpi:oee"]))
    monkeypatch.setattr(router_module, "structured_retriever", MagicMock(return_value="x" * 500))
    monkeypatch.setattr(router_module, "source_text_retriever", MagicMock(return_value=""))
    monkeypatch.setattr(router_module, "vector_search", MagicMock(return_value="vector context"))
    monkeypatch.setattr(router_module, "generate_answer", MagicMock(return_value="the final answer"))


def test_cache_hit_short_circuits_everything_else(monkeypatch):
    monkeypatch.setattr(router_module, "get_cached_answer", MagicMock(return_value="cached answer"))

    answer = route_and_answer(MagicMock(), MagicMock(), "What is OEE?", _settings(), vector_store=MagicMock())

    assert answer == "cached answer"
    router_module.extract_entities.assert_not_called()
    router_module.vector_search.assert_not_called()
    router_module.generate_answer.assert_not_called()
    router_module.set_cached_answer.assert_not_called()


def test_graph_path_used_when_anchors_resolve_with_rich_context():
    answer = route_and_answer(MagicMock(), MagicMock(), "What is OEE?", _settings(), vector_store=MagicMock())

    assert answer == "the final answer"
    router_module.vector_search.assert_not_called()
    router_module.set_cached_answer.assert_called_once()


def test_vector_fallback_used_when_no_anchors_resolve():
    router_module.match_entities.return_value = []

    route_and_answer(MagicMock(), MagicMock(), "why did throughput drop?", _settings(), vector_store=MagicMock())

    router_module.vector_search.assert_called_once()


def test_vector_fallback_used_when_graph_context_too_thin():
    router_module.structured_retriever.return_value = "short"

    route_and_answer(MagicMock(), MagicMock(), "What is OEE?", _settings(min_graph_context_chars=200), vector_store=MagicMock())

    router_module.vector_search.assert_called_once()


def test_no_vector_store_disables_fallback_even_with_no_anchors():
    router_module.match_entities.return_value = []

    route_and_answer(MagicMock(), MagicMock(), "why did throughput drop?", _settings(), vector_store=None)

    router_module.vector_search.assert_not_called()


def test_answer_is_cached_after_generation():
    graph = MagicMock()
    route_and_answer(graph, MagicMock(), "What is OEE?", _settings(), vector_store=MagicMock())

    router_module.set_cached_answer.assert_called_once_with(
        graph, "What is OEE?", "the final answer", 3600, 1000
    )

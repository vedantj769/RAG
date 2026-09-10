"""Query router: dispatches each question to the cheapest retrieval path that yields
enough context, instead of always running full graph retrieval.

Order: query cache (near-zero latency on repeats) -> entity-anchored graph traversal
(existing, hop-bounded/char-budgeted `graph_rag.retrieval`) -> vector similarity search,
added only when no entity anchors resolve or the graph context is too thin to be
useful. This keeps the common case (a named entity with a rich neighborhood) as fast
as today, while still answering questions the entity-anchored path alone cannot.
"""
from __future__ import annotations

import logging

from langchain_core.language_models import BaseLanguageModel
from langchain_neo4j import Neo4jGraph, Neo4jVector

from graph_rag.config import Settings
from graph_rag.query_cache import get_cached_answer, set_cached_answer
from graph_rag.retrieval import (
    ensure_entity_fulltext_index,
    extract_entities,
    generate_answer,
    match_entities,
    source_text_retriever,
    structured_retriever,
)
from graph_rag.vector_store import vector_search

logger = logging.getLogger(__name__)


def route_and_answer(
    graph: Neo4jGraph,
    llm: BaseLanguageModel,
    question: str,
    settings: Settings,
    vector_store: Neo4jVector | None = None,
) -> str:
    """Answer a question using the cheapest retrieval path that yields enough context.

    `vector_store` is optional - pass None to disable the vector fallback entirely
    (e.g. if it hasn't been built yet), in which case this behaves like
    `graph_rag.retrieval.answer_question` plus caching.
    """
    cached = get_cached_answer(
        graph, question, settings.query_cache_ttl_seconds, settings.query_cache_max_entries
    )
    if cached is not None:
        logger.info("Query cache hit for question: %s", question)
        return cached

    ensure_entity_fulltext_index(graph)

    entities = extract_entities(llm, question)
    node_ids = match_entities(graph, entities, settings.retrieval_top_k)

    paths_used: list[str] = []
    sections: list[str] = []

    graph_context = ""
    if node_ids:
        relationships = structured_retriever(
            graph, node_ids, hops=settings.retrieval_hops, max_chars=settings.retrieval_max_context_chars
        )
        source_text = source_text_retriever(graph, node_ids, settings.retrieval_top_k)
        graph_context = "\n\n".join(part for part in (relationships, source_text) if part)
        if graph_context:
            paths_used.append("graph")
            sections.append(f"Relevant relationships and source text:\n{graph_context}")

    needs_vector_fallback = not node_ids or len(graph_context) < settings.min_graph_context_chars
    if vector_store is not None and needs_vector_fallback:
        vector_context = vector_search(vector_store, question, settings.retrieval_top_k)
        if vector_context:
            paths_used.append("vector")
            sections.append(f"Relevant passages (semantic search):\n{vector_context}")

    logger.info("Retrieval path(s) used for question %r: %s", question, paths_used or ["none"])

    context = "\n\n".join(sections)
    if not context:
        logger.warning("No context found via graph or vector search for question: %s", question)
        context = "No relevant information was found."

    answer = generate_answer(llm, question, context)
    set_cached_answer(graph, question, answer, settings.query_cache_ttl_seconds, settings.query_cache_max_entries)
    return answer

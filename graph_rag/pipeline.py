"""Ingestion pipeline: load PDFs, chunk, extract graph data, and write it to Neo4j."""
from __future__ import annotations

import logging

from graph_rag.chunking import split_documents
from graph_rag.config import Settings
from graph_rag.llm import build_groq_llm
from graph_rag.loader import load_pdf_documents
from graph_rag.neo4j_store import build_neo4j_graph, verify_graph_written, write_graph_documents
from graph_rag.query_cache import bump_graph_version
from graph_rag.skill_extraction import extract_with_skills
from graph_rag.vector_store import build_vector_store

logger = logging.getLogger(__name__)


def run_ingestion_pipeline(settings: Settings) -> dict[str, int]:
    """Run the full ingestion pipeline and return verification counts from Neo4j."""
    documents = load_pdf_documents(settings.documents_dir)
    chunks = split_documents(documents, settings.chunk_size, settings.chunk_overlap)

    llm = build_groq_llm(settings.groq_api_key, settings.groq_model)
    graph_documents = extract_with_skills(llm, chunks)

    graph = build_neo4j_graph(
        settings.neo4j_uri,
        settings.neo4j_username,
        settings.neo4j_password,
        settings.neo4j_database,
    )
    try:
        write_graph_documents(graph, graph_documents)
        counts = verify_graph_written(graph)

        # Embed the newly-written Document chunks (incremental - see build_vector_store)
        # so the query router's vector fallback has up-to-date data to search.
        build_vector_store(
            settings.neo4j_uri,
            settings.neo4j_username,
            settings.neo4j_password,
            settings.neo4j_database,
            settings.embedding_model,
        )

        # Must run last: invalidates every cached answer computed against the old graph.
        bump_graph_version(graph)

        return counts
    finally:
        graph.close()


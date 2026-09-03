"""Ingestion pipeline: load PDFs, chunk, extract graph data, and write it to Neo4j."""
from __future__ import annotations

import logging

from graph_rag.chunking import split_documents
from graph_rag.config import Settings
from graph_rag.llm import build_groq_llm
from graph_rag.loader import load_pdf_documents
from graph_rag.neo4j_store import build_neo4j_graph, verify_graph_written, write_graph_documents
from graph_rag.skill_extraction import extract_with_skills

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
        return verify_graph_written(graph)
    finally:
        graph.close()


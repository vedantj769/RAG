"""Entry point: ingest a KPI-definitions style DOCX using the constrained KPI graph schema."""
from __future__ import annotations

import logging
import sys

from graph_rag.chunking import split_by_headings
from graph_rag.config import ConfigError, load_settings
from graph_rag.graph_extraction import build_graph_transformer, extract_graph_documents
from graph_rag.llm import build_groq_llm
from graph_rag.loader import load_docx_documents
from graph_rag.logging_config import setup_logging
from graph_rag.neo4j_store import build_neo4j_graph, verify_graph_written, write_graph_documents
from graph_rag.retrieval import ensure_entity_fulltext_index
from graph_rag.schemas.kpi_definition import (
    ALLOWED_NODES,
    ALLOWED_RELATIONSHIPS,
    EXTRACTION_INSTRUCTIONS,
)

logger = logging.getLogger(__name__)


def main() -> int:
    try:
        settings = load_settings()
    except ConfigError:
        logging.basicConfig(level="INFO")
        logging.getLogger(__name__).exception("Configuration error")
        return 1

    setup_logging(settings.log_level)

    documents = load_docx_documents(settings.documents_dir)
    chunks = split_by_headings(documents)

    llm = build_groq_llm(settings.groq_api_key, settings.groq_model)
    transformer = build_graph_transformer(
        llm,
        allowed_nodes=ALLOWED_NODES,
        allowed_relationships=ALLOWED_RELATIONSHIPS,
        node_properties=True,
        additional_instructions=EXTRACTION_INSTRUCTIONS,
    )
    graph_documents = extract_graph_documents(transformer, chunks)

    graph = build_neo4j_graph(
        settings.neo4j_uri,
        settings.neo4j_username,
        settings.neo4j_password,
        settings.neo4j_database,
    )
    try:
        write_graph_documents(graph, graph_documents)
        ensure_entity_fulltext_index(graph)
        counts = verify_graph_written(graph)
    finally:
        graph.close()

    logger.info(
        "KPI ingestion complete. Neo4j now has %d node(s) and %d relationship(s).",
        counts["nodes"],
        counts["relationships"],
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())

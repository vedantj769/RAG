"""Entry point: ingest a pre-chunked, pre-classified JSON export (see
`graph_rag.loader.load_chunk_export`, e.g. EdgeOps_Knowledge_Sample_chunks_full.json)
into Neo4j, using each chunk's own `knowledge_type` to pick its skills/<type>/SKILL.md
schema.

Unlike graph_builder.py, no LLM routing call is needed here - the chunk export already
classifies each table entry, so this only needs to look up the matching skill and
extract with its allowed_nodes/allowed_relationships/prompt.
"""
from __future__ import annotations

import logging
import sys
from collections import defaultdict

from graph_rag.config import ConfigError, load_settings
from graph_rag.graph_extraction import build_graph_transformer, extract_graph_documents
from graph_rag.llm import build_groq_llm
from graph_rag.loader import load_chunk_export
from graph_rag.logging_config import setup_logging
from graph_rag.neo4j_store import build_neo4j_graph, verify_graph_written, write_graph_documents
from graph_rag.retrieval import ensure_entity_fulltext_index
from skills.registry import list_skills

logger = logging.getLogger(__name__)


def main() -> int:
    chunk_export_path = sys.argv[1] if len(sys.argv) > 1 else None
    if not chunk_export_path:
        logging.basicConfig(level="INFO")
        logging.getLogger(__name__).error("Usage: python ingest_chunk_export.py <path-to-chunks.json>")
        return 1

    try:
        settings = load_settings()
    except ConfigError:
        logging.basicConfig(level="INFO")
        logging.getLogger(__name__).exception("Configuration error")
        return 1

    setup_logging(settings.log_level)

    # graph_schema is reference-only (see its SKILL.md); operational_data has no schema.
    skills_by_type = {
        skill.knowledge_type: skill
        for skill in list_skills()
        if skill.allowed_nodes and skill.knowledge_type != "graph_schema"
    }

    documents = load_chunk_export(chunk_export_path)

    chunks_by_type: dict[str, list] = defaultdict(list)
    for document in documents:
        knowledge_type = document.metadata.get("knowledge_type", "")
        if knowledge_type not in skills_by_type:
            logger.info(
                "Skipping chunk with unknown/non-extraction knowledge_type %r: %s",
                knowledge_type,
                document.metadata.get("heading"),
            )
            continue
        chunks_by_type[knowledge_type].append(document)

    llm = build_groq_llm(settings.groq_api_key, settings.groq_model)

    graph_documents = []
    for knowledge_type, chunks in chunks_by_type.items():
        skill = skills_by_type[knowledge_type]
        logger.info("Extracting %d chunk(s) using skill '%s'", len(chunks), knowledge_type)
        transformer = build_graph_transformer(
            llm,
            allowed_nodes=skill.allowed_nodes,
            allowed_relationships=skill.allowed_relationships,
            node_properties=True,
            additional_instructions=skill.prompt,
        )
        graph_documents.extend(extract_graph_documents(transformer, chunks))

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
        "Chunk-export ingestion complete. Neo4j now has %d node(s) and %d relationship(s).",
        counts["nodes"],
        counts["relationships"],
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())

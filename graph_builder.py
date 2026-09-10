"""Entry point: route each document section to its matching skills/<type>/SKILL.md
schema (see skills/registry.py, skills/__init__.py) and ingest it into Neo4j.

Unlike ingest_kpi_definitions.py (one fixed schema for every chunk), this shows the LLM
every skill's short description and lets it pick the relevant skill per section; only
that skill's allowed_nodes/allowed_relationships/prompt then constrain extraction for it.
"""
from __future__ import annotations

import logging
import sys
from collections import defaultdict

from graph_rag.chunking import split_by_headings, split_by_top_level_sections
from graph_rag.config import ConfigError, load_settings
from graph_rag.graph_extraction import build_graph_transformer, extract_graph_documents
from graph_rag.llm import build_groq_llm
from graph_rag.loader import load_docx_documents
from graph_rag.logging_config import setup_logging
from graph_rag.neo4j_store import build_neo4j_graph, verify_graph_written, write_graph_documents
from graph_rag.retrieval import ensure_entity_fulltext_index
from graph_rag.skill_router import select_skill
from skills.registry import list_skills

logger = logging.getLogger(__name__)


def main() -> int:
    try:
        settings = load_settings()
    except ConfigError:
        logging.basicConfig(level="INFO")
        logging.getLogger(__name__).exception("Configuration error")
        return 1

    setup_logging(settings.log_level)

    # operational_data has no schema (retrieval-only gate, see its SKILL.md);
    # graph_schema documents the union of every OTHER skill's schema and is reference-only
    # - neither is ever assigned to a document section by the router.
    skills = [
        skill
        for skill in list_skills()
        if skill.allowed_nodes and skill.knowledge_type != "graph_schema"
    ]
    if not skills:
        logger.error("No skills found under skills/ - nothing to route sections to.")
        return 1

    documents = load_docx_documents(settings.documents_dir)
    sections = split_by_top_level_sections(documents)

    llm = build_groq_llm(settings.groq_api_key, settings.groq_model)

    chunks_by_skill: dict[str, list] = defaultdict(list)
    for section in sections:
        heading = section.metadata.get("heading", "")
        skill = select_skill(llm, skills, heading, section.page_content)
        if skill is None:
            logger.info("Skipping unrouted section: %s", heading)
            continue
        chunks_by_skill[skill.knowledge_type].extend(split_by_headings([section]))

    skills_by_type = {skill.knowledge_type: skill for skill in skills}
    graph_documents = []
    for knowledge_type, chunks in chunks_by_skill.items():
        skill = skills_by_type[knowledge_type]
        logger.info("Extracting %d chunk(s) using skill '%s'", len(chunks), knowledge_type)
        transformer = build_graph_transformer(
            llm,
            allowed_nodes=skill.allowed_nodes,
            allowed_relationships=skill.allowed_relationships,
            node_properties=True,
            additional_instructions=skill.prompt,
            knowledge_type=knowledge_type,
        )
        graph_documents.extend(extract_graph_documents(transformer, chunks, knowledge_type=knowledge_type))

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
        "Skill-routed ingestion complete. Neo4j now has %d node(s) and %d relationship(s).",
        counts["nodes"],
        counts["relationships"],
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())

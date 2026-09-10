"""Entry point: answer a natural language question using the existing Neo4j graph."""
from __future__ import annotations

import logging
import sys

from graph_rag.config import ConfigError, load_settings
from graph_rag.llm import build_groq_llm
from graph_rag.logging_config import setup_logging
from graph_rag.neo4j_store import build_neo4j_graph
from graph_rag.router import route_and_answer
from graph_rag.vector_store import build_vector_store

logger = logging.getLogger(__name__)


def main() -> int:
    try:
        settings = load_settings()
    except ConfigError:
        logging.basicConfig(level="INFO")
        logging.getLogger(__name__).exception("Configuration error")
        return 1

    setup_logging(settings.log_level)

    question = " ".join(sys.argv[1:]).strip() or input("Question: ").strip()
    if not question:
        logger.error("No question provided")
        return 1

    llm = build_groq_llm(settings.groq_api_key, settings.groq_model)
    graph = build_neo4j_graph(
        settings.neo4j_uri,
        settings.neo4j_username,
        settings.neo4j_password,
        settings.neo4j_database,
    )
    try:
        try:
            vector_store = build_vector_store(
                settings.neo4j_uri,
                settings.neo4j_username,
                settings.neo4j_password,
                settings.neo4j_database,
                settings.embedding_model,
            )
        except Exception:
            logger.warning("Vector store unavailable; falling back to graph-only retrieval", exc_info=True)
            vector_store = None

        answer = route_and_answer(graph, llm, question, settings, vector_store=vector_store)
    finally:
        graph.close()

    print(f"\nAnswer: {answer}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())

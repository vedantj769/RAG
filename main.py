"""Entry point: run the ingestion pipeline that loads PDFs and writes a graph to Neo4j."""
from __future__ import annotations

import logging
import sys

from graph_rag.config import ConfigError, load_settings
from graph_rag.logging_config import setup_logging
from graph_rag.pipeline import run_ingestion_pipeline

logger = logging.getLogger(__name__)


def main() -> int:
    try:
        settings = load_settings()
    except ConfigError:
        logging.basicConfig(level="INFO")
        logging.getLogger(__name__).exception("Configuration error")
        return 1

    setup_logging(settings.log_level)
    counts = run_ingestion_pipeline(settings)
    logger.info(
        "Ingestion complete. Neo4j now has %d node(s) and %d relationship(s).",
        counts["nodes"],
        counts["relationships"],
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())

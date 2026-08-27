"""Entry point placeholder. Pipeline wiring will be added in a later step."""
from __future__ import annotations

import logging
import sys

from graph_rag.config import ConfigError, load_settings
from graph_rag.logging_config import setup_logging

logger = logging.getLogger(__name__)


def main() -> int:
    try:
        settings = load_settings()
    except ConfigError:
        logging.basicConfig(level="INFO")
        logging.getLogger(__name__).exception("Configuration error")
        return 1

    setup_logging(settings.log_level)
    logger.info("Configuration loaded successfully. Pipeline not implemented yet.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

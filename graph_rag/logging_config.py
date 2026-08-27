"""Centralized logging configuration."""
import logging


def setup_logging(level: str = "INFO") -> None:
    """Configure root logging format and level for the application."""
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    )

"""Application configuration loaded from environment variables / a .env file."""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


class ConfigError(RuntimeError):
    """Raised when required configuration is missing or invalid."""


def _require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise ConfigError(f"Missing required environment variable: {name}")
    return value


@dataclass(frozen=True)
class Settings:
    groq_api_key: str
    groq_model: str

    neo4j_uri: str
    neo4j_username: str
    neo4j_password: str
    neo4j_database: str

    documents_dir: str
    chunk_size: int
    chunk_overlap: int

    retrieval_top_k: int

    log_level: str


def load_settings() -> Settings:
    """Load and validate application settings from the environment."""
    settings = Settings(
        groq_api_key=_require_env("GROQ_API_KEY"),
        groq_model=os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile"),
        neo4j_uri=_require_env("NEO4J_URI"),
        neo4j_username=_require_env("NEO4J_USERNAME"),
        neo4j_password=_require_env("NEO4J_PASSWORD"),
        neo4j_database=os.getenv("NEO4J_DATABASE", "neo4j"),
        documents_dir=os.getenv("DOCUMENTS_DIR", "data/documents"),
        chunk_size=int(os.getenv("CHUNK_SIZE", "1000")),
        chunk_overlap=int(os.getenv("CHUNK_OVERLAP", "200")),
        retrieval_top_k=int(os.getenv("RETRIEVAL_TOP_K", "5")),
        log_level=os.getenv("LOG_LEVEL", "INFO"),
    )
    logger.debug("Settings loaded: %s", _redact(settings))
    return settings


def _redact(settings: Settings) -> dict:
    """Return settings as a dict with secrets masked, for safe logging."""
    data = settings.__dict__.copy()
    for key in ("groq_api_key", "neo4j_password"):
        if data.get(key):
            data[key] = "***"
    return data

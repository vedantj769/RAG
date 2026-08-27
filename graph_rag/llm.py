"""Factory for the Groq-backed chat model used for graph extraction."""
from __future__ import annotations

import logging

from langchain_groq import ChatGroq

logger = logging.getLogger(__name__)


def build_groq_llm(api_key: str, model: str) -> ChatGroq:
    """Create a ChatGroq LLM instance configured for deterministic extraction."""
    logger.info("Initializing ChatGroq with model=%s", model)
    return ChatGroq(api_key=api_key, model=model, temperature=0)

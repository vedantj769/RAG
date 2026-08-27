"""Live smoke test for the Groq LLM connection (requires a real .env with GROQ_API_KEY)."""
from __future__ import annotations

import pytest

from graph_rag.config import ConfigError, load_settings
from graph_rag.llm import build_groq_llm


def test_groq_llm_responds_to_simple_prompt() -> None:
    try:
        settings = load_settings()
    except ConfigError as exc:
        pytest.skip(f"Skipping live Groq test: {exc}")

    llm = build_groq_llm(settings.groq_api_key, settings.groq_model)

    response = llm.invoke("Reply with exactly one word: pong")

    print(f"\nGroq response: {response.content}")
    assert response.content

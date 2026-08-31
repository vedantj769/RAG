"""Reusable node/relationship schemas for constrained graph extraction.

Each schema module mirrors a domain-specific extraction skill (see the project's
SKILL.md files) as plain Python constants, so `graph_rag.graph_extraction` can pass
them straight to `LLMGraphTransformer` without parsing markdown at ingestion time.
"""

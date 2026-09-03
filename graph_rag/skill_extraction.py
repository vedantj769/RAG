"""Classify document chunks against `skills/<knowledge_type>/SKILL.md` packages and
extract graph data using the matched skill's schema/prompt.

Unlike `graph_rag.graph_extraction.build_graph_transformer` (one fixed schema for every
chunk), this shows the LLM every skill's short description and lets it pick which
knowledge_type applies to a given chunk before extraction, so a single ingestion run
can mix KPI definitions, business rules, data models, etc. Chunks that match no skill
fall back to unconstrained extraction (no allowed_nodes/allowed_relationships).
"""
from __future__ import annotations

import logging
from typing import Optional

from langchain_core.documents import Document
from langchain_core.language_models import BaseLanguageModel
from langchain_core.prompts import ChatPromptTemplate
from langchain_neo4j.graphs.graph_document import GraphDocument
from pydantic import BaseModel, Field

from graph_rag.graph_extraction import build_graph_transformer
from skills.registry import SkillPackage, list_skills

logger = logging.getLogger(__name__)

_SKILL_SELECTION_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "You classify a document chunk against a fixed list of knowledge types. "
            "Pick the single knowledge_type whose description best matches what the "
            "chunk is about. If none of them apply, return an empty knowledge_type.\n\n"
            "Knowledge types:\n{skill_descriptions}",
        ),
        ("human", "{chunk_text}"),
    ]
)


class _SkillClassification(BaseModel):
    """The knowledge_type (if any) that best matches a chunk of text."""

    knowledge_type: str = Field(
        default="", description="One of the given knowledge_type values, or empty if none match."
    )


def _format_skill_descriptions(skills: list[SkillPackage]) -> str:
    return "\n".join(f"- {skill.knowledge_type}: {skill.description}" for skill in skills)


def classify_chunk_skill(
    llm: BaseLanguageModel, chunk_text: str, skills: list[SkillPackage]
) -> Optional[SkillPackage]:
    """Ask the LLM which skill (if any) applies to a chunk of text."""
    if not skills:
        return None

    chain = _SKILL_SELECTION_PROMPT | llm.with_structured_output(_SkillClassification)
    result = chain.invoke(
        {"skill_descriptions": _format_skill_descriptions(skills), "chunk_text": chunk_text}
    )
    knowledge_type = result.knowledge_type.strip() if isinstance(result, _SkillClassification) else ""
    return next((skill for skill in skills if skill.knowledge_type == knowledge_type), None)


def extract_with_skills(llm: BaseLanguageModel, chunks: list[Document]) -> list[GraphDocument]:
    """Classify each chunk against `skills/` and extract graph data with the matched schema.

    Transformers are built once per matched knowledge_type (and once for the
    unconstrained fallback) and reused across chunks, since building one is cheap but
    unnecessary to repeat per chunk.
    """
    if not chunks:
        return []

    skills = list_skills()
    logger.info("Loaded %d skill(s): %s", len(skills), [s.knowledge_type for s in skills])

    transformers: dict[str, object] = {}
    graph_documents: list[GraphDocument] = []

    for chunk in chunks:
        skill = classify_chunk_skill(llm, chunk.page_content, skills)
        cache_key = skill.knowledge_type if skill else ""

        if cache_key not in transformers:
            if skill:
                logger.debug("Building transformer for skill: %s", skill.knowledge_type)
                transformers[cache_key] = build_graph_transformer(
                    llm,
                    allowed_nodes=skill.allowed_nodes,
                    allowed_relationships=skill.allowed_relationships,
                    node_properties=True,
                    additional_instructions=skill.prompt,
                )
            else:
                logger.debug("No skill matched chunk; using unconstrained extraction")
                transformers[cache_key] = build_graph_transformer(llm)

        transformer = transformers[cache_key]
        graph_documents.extend(transformer.convert_to_graph_documents([chunk]))

    logger.info(
        "Extracted %d graph document(s) via skills: %d node(s), %d relationship(s)",
        len(graph_documents),
        sum(len(gd.nodes) for gd in graph_documents),
        sum(len(gd.relationships) for gd in graph_documents),
    )
    return graph_documents

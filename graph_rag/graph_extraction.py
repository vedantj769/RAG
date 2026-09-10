"""Convert text chunks into graph documents using an LLM graph transformer."""
from __future__ import annotations

import logging

from langchain_core.documents import Document
from langchain_core.language_models import BaseLanguageModel
from langchain_neo4j.graph_transformers.llm import LLMGraphTransformer
from langchain_neo4j.graphs.graph_document import GraphDocument

logger = logging.getLogger(__name__)

# Every extracted node must carry these, regardless of skill/label, so retrieval never
# has to guess whether a property exists (see skills/*/SKILL.md "Retrieval Notes").
UNIVERSAL_NODE_PROPERTIES: list[str] = ["knowledge_name", "knowledge_type", "description"]

_UNIVERSAL_PROPERTIES_INSTRUCTIONS = """
Every single node you extract MUST include these three properties, in addition to any
other properties allowed for its label:
- knowledge_name: the entity's human-readable name, exactly as written in the source
  text (e.g. "Overall Equipment Effectiveness"). Use the SAME text every time the same
  entity is referenced, so nodes merge instead of duplicating.
- knowledge_type: the fixed value "{knowledge_type}" (the knowledge category this
  content belongs to) — use this exact string for every node extracted from this text.
- description: a short (1-2 sentence) human-readable summary of what this node is,
  even if a more detailed/structured property is also captured for it.
These three are required with no exceptions, including for nodes where you also invent
other named properties.
""".strip()


def build_graph_transformer(
    llm: BaseLanguageModel,
    allowed_nodes: list[str] | None = None,
    allowed_relationships: list[tuple[str, str, str]] | None = None,
    node_properties: bool | list[str] = False,
    additional_instructions: str = "",
    knowledge_type: str = "",
) -> LLMGraphTransformer:
    """Create an LLMGraphTransformer bound to the given LLM.

    Passing `allowed_nodes`/`allowed_relationships` constrains extraction to a fixed
    schema (see `graph_rag.schemas`); `node_properties=True` lets the LLM also extract
    named properties per node (e.g. a Formula's `expression`), which is required for
    those properties to end up in Neo4j and be retrievable later.

    When `node_properties` is truthy, `knowledge_name`/`knowledge_type`/`description`
    are always requested (merged into the list, or included under `True`'s "any
    property" case) via a prepended instruction — see `UNIVERSAL_NODE_PROPERTIES`.
    Use `knowledge_type` to fill in the fixed value the LLM should stamp on every node.
    """
    instructions = additional_instructions
    if node_properties:
        if isinstance(node_properties, list):
            node_properties = list(
                dict.fromkeys([*UNIVERSAL_NODE_PROPERTIES, *node_properties])
            )
        instructions = (
            _UNIVERSAL_PROPERTIES_INSTRUCTIONS.format(knowledge_type=knowledge_type or "unknown")
            + "\n\n"
            + additional_instructions
        ).strip()

    return LLMGraphTransformer(
        llm=llm,
        allowed_nodes=allowed_nodes or [],
        allowed_relationships=allowed_relationships or [],
        node_properties=node_properties,
        additional_instructions=instructions,
    )


def backfill_universal_properties(
    graph_documents: list[GraphDocument], knowledge_type: str
) -> None:
    """Guarantee `knowledge_name`/`knowledge_type`/`description` on every node, in
    place, regardless of whether the extraction LLM actually populated them.

    This is the enforcement layer behind `UNIVERSAL_NODE_PROPERTIES`: the prompt asks
    for these properties, but nothing stops the LLM from omitting them, so retrieval
    code must never rely on the prompt alone.
    """
    for graph_document in graph_documents:
        for node in graph_document.nodes:
            node.properties.setdefault("knowledge_name", node.id)
            node.properties.setdefault("knowledge_type", knowledge_type or "uncategorized")
            node.properties.setdefault("description", "")


def extract_graph_documents(
    transformer: LLMGraphTransformer, chunks: list[Document], knowledge_type: str = ""
) -> list[GraphDocument]:
    """Extract entities and relationships from document chunks as GraphDocuments."""
    if not chunks:
        return []

    logger.info("Extracting graph data from %d chunk(s)", len(chunks))
    graph_documents = transformer.convert_to_graph_documents(chunks)
    backfill_universal_properties(graph_documents, knowledge_type)
    logger.info(
        "Extracted %d graph document(s): %d node(s), %d relationship(s)",
        len(graph_documents),
        sum(len(gd.nodes) for gd in graph_documents),
        sum(len(gd.relationships) for gd in graph_documents),
    )
    return graph_documents

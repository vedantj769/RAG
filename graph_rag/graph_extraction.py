"""Convert text chunks into graph documents using an LLM graph transformer."""
from __future__ import annotations

import logging

from langchain_core.documents import Document
from langchain_core.language_models import BaseLanguageModel
from langchain_neo4j.graph_transformers.llm import LLMGraphTransformer
from langchain_neo4j.graphs.graph_document import GraphDocument

logger = logging.getLogger(__name__)


def build_graph_transformer(
    llm: BaseLanguageModel,
    allowed_nodes: list[str] | None = None,
    allowed_relationships: list[tuple[str, str, str]] | None = None,
    node_properties: bool | list[str] = False,
    additional_instructions: str = "",
) -> LLMGraphTransformer:
    """Create an LLMGraphTransformer bound to the given LLM.

    Passing `allowed_nodes`/`allowed_relationships` constrains extraction to a fixed
    schema (see `graph_rag.schemas`); `node_properties=True` lets the LLM also extract
    named properties per node (e.g. a Formula's `expression`), which is required for
    those properties to end up in Neo4j and be retrievable later.
    """
    return LLMGraphTransformer(
        llm=llm,
        allowed_nodes=allowed_nodes or [],
        allowed_relationships=allowed_relationships or [],
        node_properties=node_properties,
        additional_instructions=additional_instructions,
    )


def extract_graph_documents(
    transformer: LLMGraphTransformer, chunks: list[Document]
) -> list[GraphDocument]:
    """Extract entities and relationships from document chunks as GraphDocuments."""
    if not chunks:
        return []

    logger.info("Extracting graph data from %d chunk(s)", len(chunks))
    graph_documents = transformer.convert_to_graph_documents(chunks)
    logger.info(
        "Extracted %d graph document(s): %d node(s), %d relationship(s)",
        len(graph_documents),
        sum(len(gd.nodes) for gd in graph_documents),
        sum(len(gd.relationships) for gd in graph_documents),
    )
    return graph_documents

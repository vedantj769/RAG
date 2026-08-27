"""Convert text chunks into graph documents using an LLM graph transformer."""
from __future__ import annotations

import logging

from langchain_core.documents import Document
from langchain_core.language_models import BaseLanguageModel
from langchain_neo4j.graph_transformers.llm import LLMGraphTransformer
from langchain_neo4j.graphs.graph_document import GraphDocument

logger = logging.getLogger(__name__)


def build_graph_transformer(llm: BaseLanguageModel) -> LLMGraphTransformer:
    """Create an LLMGraphTransformer bound to the given LLM."""
    return LLMGraphTransformer(llm=llm)


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

"""Semantic fallback retrieval over the same Document chunks written during ingestion.

Reuses the `Document` nodes already created by `graph_rag.neo4j_store.write_graph_documents`
(`include_source=True`) instead of storing a second copy of chunk text in a separate
vector database. This exists to answer questions that name no clear entity - where
`graph_rag.retrieval`'s entity-anchored graph traversal has nothing to anchor on.
"""
from __future__ import annotations

import logging

from langchain_huggingface import HuggingFaceEmbeddings
from langchain_neo4j import Neo4jVector

logger = logging.getLogger(__name__)

DEFAULT_INDEX_NAME = "document_vector_index"


def build_vector_store(
    uri: str,
    username: str,
    password: str,
    database: str,
    embedding_model: str,
) -> Neo4jVector:
    """Build (or reuse) a vector index over existing `Document.text` properties.

    Safe to call repeatedly (e.g. once per ingestion run): `from_existing_graph` only
    computes embeddings for `Document` nodes that don't already have one, so re-running
    ingestion embeds just the newly-written chunks instead of redoing all of them.
    """
    logger.info("Building/refreshing vector store using embedding model: %s", embedding_model)
    embeddings = HuggingFaceEmbeddings(model_name=embedding_model)
    return Neo4jVector.from_existing_graph(
        embedding=embeddings,
        node_label="Document",
        embedding_node_property="embedding",
        text_node_properties=["text"],
        index_name=DEFAULT_INDEX_NAME,
        url=uri,
        username=username,
        password=password,
        database=database,
    )


def vector_search(store: Neo4jVector, question: str, k: int = 5) -> str:
    """Return joined chunk text from the `k` most semantically similar Document chunks."""
    results = store.similarity_search(question, k=k)
    chunks = [doc.page_content for doc in results if doc.page_content]
    return "\n\n".join(dict.fromkeys(chunks))

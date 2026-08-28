"""Retrieve relevant context from the existing Neo4j knowledge graph for a question.

Assumes graph documents were written with ``baseEntityLabel=True`` and
``include_source=True`` (see ``graph_rag.neo4j_store.write_graph_documents``), so
entities carry the ``__Entity__`` label with an ``id`` property, and source chunks
are stored as ``Document`` nodes linked to the entities they mention via
``MENTIONS`` relationships.
"""
from __future__ import annotations

import logging

from langchain_core.language_models import BaseLanguageModel
from langchain_core.prompts import ChatPromptTemplate
from langchain_neo4j import Neo4jGraph
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

ENTITY_FULLTEXT_INDEX = "entity_fulltext_index"

_LUCENE_SPECIAL_CHARS = set('+-&|!(){}[]^"~*?:\\/')

_ENTITY_EXTRACTION_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "You extract entity names (people, organizations, places, products, and "
            "other concepts) mentioned in a user question. List each entity exactly "
            "as it appears in the question.",
        ),
        ("human", "{question}"),
    ]
)

_ANSWER_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "You answer questions using only the graph context provided below. "
            "If the context does not contain enough information to answer, say so.\n\n"
            "Graph context:\n{context}",
        ),
        ("human", "{question}"),
    ]
)


class ExtractedEntities(BaseModel):
    """Entity names extracted from a natural language question."""

    names: list[str] = Field(default_factory=list, description="Entity names mentioned in the question.")


def ensure_entity_fulltext_index(graph: Neo4jGraph) -> None:
    """Create the full-text index used to fuzzy-match entity names, if it doesn't exist."""
    graph.query(
        f"CREATE FULLTEXT INDEX {ENTITY_FULLTEXT_INDEX} IF NOT EXISTS "
        "FOR (n:__Entity__) ON EACH [n.id]"
    )


def extract_entities(llm: BaseLanguageModel, question: str) -> list[str]:
    """Ask the LLM to pull candidate entity names out of the question."""
    chain = _ENTITY_EXTRACTION_PROMPT | llm.with_structured_output(ExtractedEntities)
    result = chain.invoke({"question": question})
    names = result.names if isinstance(result, ExtractedEntities) else []
    logger.debug("Extracted entities from question: %s", names)
    return names


def _to_fulltext_query(entity: str) -> str:
    """Build a fuzzy Lucene query for an entity name, tolerating minor spelling differences."""
    cleaned = "".join(" " if char in _LUCENE_SPECIAL_CHARS else char for char in entity)
    words = [word for word in cleaned.split() if word]
    return " AND ".join(f"{word}~2" for word in words)


def structured_retriever(graph: Neo4jGraph, llm: BaseLanguageModel, question: str, limit: int = 5) -> str:
    """Return newline-separated relationship triples for entities mentioned in the question."""
    triples: list[str] = []
    for entity in extract_entities(llm, question):
        fulltext_query = _to_fulltext_query(entity)
        if not fulltext_query:
            continue

        rows = graph.query(
            """
            CALL db.index.fulltext.queryNodes($index_name, $query, {limit: $limit})
            YIELD node
            CALL {
                WITH node
                MATCH (node)-[r]->(neighbor)
                WHERE type(r) <> 'MENTIONS'
                RETURN node.id + ' - ' + type(r) + ' -> ' + neighbor.id AS output
                UNION ALL
                WITH node
                MATCH (node)<-[r]-(neighbor)
                WHERE type(r) <> 'MENTIONS'
                RETURN neighbor.id + ' - ' + type(r) + ' -> ' + node.id AS output
            }
            RETURN DISTINCT output
            LIMIT $limit
            """,
            {"index_name": ENTITY_FULLTEXT_INDEX, "query": fulltext_query, "limit": limit},
        )
        triples.extend(row["output"] for row in rows)

    return "\n".join(triples)


def source_text_retriever(graph: Neo4jGraph, llm: BaseLanguageModel, question: str, limit: int = 3) -> str:
    """Return source chunk text from Document nodes that mention entities in the question."""
    chunks: list[str] = []
    for entity in extract_entities(llm, question):
        fulltext_query = _to_fulltext_query(entity)
        if not fulltext_query:
            continue

        rows = graph.query(
            """
            CALL db.index.fulltext.queryNodes($index_name, $query, {limit: 3})
            YIELD node
            MATCH (doc:Document)-[:MENTIONS]->(node)
            RETURN DISTINCT doc.text AS text
            LIMIT $limit
            """,
            {"index_name": ENTITY_FULLTEXT_INDEX, "query": fulltext_query, "limit": limit},
        )
        chunks.extend(row["text"] for row in rows if row["text"])

    return "\n\n".join(dict.fromkeys(chunks))


def retrieve_context(graph: Neo4jGraph, llm: BaseLanguageModel, question: str, limit: int = 5) -> str:
    """Combine graph relationship triples and source chunk text into one context string."""
    relationships = structured_retriever(graph, llm, question, limit)
    source_text = source_text_retriever(graph, llm, question, limit)

    sections = []
    if relationships:
        sections.append(f"Relevant relationships:\n{relationships}")
    if source_text:
        sections.append(f"Relevant source text:\n{source_text}")
    return "\n\n".join(sections)


def answer_question(graph: Neo4jGraph, llm: BaseLanguageModel, question: str, top_k: int = 5) -> str:
    """Retrieve graph context for the question and use the LLM to produce a final answer."""
    ensure_entity_fulltext_index(graph)
    context = retrieve_context(graph, llm, question, top_k)
    if not context:
        logger.warning("No graph context found for question: %s", question)
        context = "No relevant information was found in the graph."

    chain = _ANSWER_PROMPT | llm
    response = chain.invoke({"question": question, "context": context})
    return response.content

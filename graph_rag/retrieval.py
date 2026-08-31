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
            "You identify the key named entities (people, organizations, places, "
            "products, or specific named concepts) that a question is asking about. "
            "Write each entity using its full, canonical name as it would appear in a "
            "reference document - resolve nicknames/initials to full names if the "
            "question makes them clear, and use consistent capitalization. Do not "
            "include generic terms, question words, or pronouns with no clear "
            "referent. If the question names no specific entity, return an empty list.\n\n"
            "Example:\n"
            'Question: "What prize did Marie curie win in 1903?"\n'
            'Entities: ["Marie Curie"]',
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
    deduped = list(dict.fromkeys(name.strip() for name in names if name and name.strip()))
    logger.debug("Extracted entities from question: %s", deduped)
    return deduped


def _to_fulltext_query(entity: str) -> str:
    """Build a fuzzy Lucene query for an entity name, tolerating minor spelling differences."""
    cleaned = "".join(" " if char in _LUCENE_SPECIAL_CHARS else char for char in entity)
    words = [word for word in cleaned.split() if word]
    return " AND ".join(f"{word}~2" for word in words)


def _match_entity_ids(graph: Neo4jGraph, entity: str, limit: int) -> list[str]:
    """Find the `id`(s) of graph entities matching a name, ranked by full-text relevance.

    Falls back to a case-insensitive substring match when the fuzzy full-text search
    finds nothing (e.g. for very short names, or names with unusual punctuation).
    """
    fulltext_query = _to_fulltext_query(entity)
    if fulltext_query:
        rows = graph.query(
            """
            CALL db.index.fulltext.queryNodes($index_name, $query, {limit: $limit})
            YIELD node, score
            RETURN node.id AS id
            ORDER BY score DESC
            """,
            {"index_name": ENTITY_FULLTEXT_INDEX, "query": fulltext_query, "limit": limit},
        )
        ids = [row["id"] for row in rows]
        if ids:
            return ids

    rows = graph.query(
        "MATCH (node:__Entity__) WHERE toLower(node.id) CONTAINS toLower($entity) "
        "RETURN node.id AS id LIMIT $limit",
        {"entity": entity, "limit": limit},
    )
    return [row["id"] for row in rows]


def _match_entities(graph: Neo4jGraph, entities: list[str], limit: int) -> list[str]:
    """Resolve extracted entity names to graph node ids, deduplicated and order-preserved."""
    node_ids: list[str] = []
    for entity in entities:
        node_ids.extend(_match_entity_ids(graph, entity, limit))
    return list(dict.fromkeys(node_ids))


def _format_triple(source: str, source_type: str | None, rel: str, target: str, target_type: str | None) -> str:
    """Render a relationship as a readable triple, including entity types when known."""
    source_label = f"{source} ({source_type})" if source_type else source
    target_label = f"{target} ({target_type})" if target_type else target
    return f"{source_label} - {rel} -> {target_label}"


def structured_retriever(graph: Neo4jGraph, node_ids: list[str], limit: int = 5) -> str:
    """Return newline-separated relationship triples for the given graph entity ids."""
    triples: list[str] = []
    for node_id in node_ids:
        rows = graph.query(
            """
            MATCH (node:__Entity__ {id: $node_id})
            CALL {
                WITH node
                MATCH (node)-[r]->(neighbor)
                WHERE type(r) <> 'MENTIONS'
                RETURN node.id AS source,
                       [l IN labels(node) WHERE l <> '__Entity__'][0] AS source_type,
                       type(r) AS rel,
                       neighbor.id AS target,
                       [l IN labels(neighbor) WHERE l <> '__Entity__'][0] AS target_type
                UNION ALL
                WITH node
                MATCH (node)<-[r]-(neighbor)
                WHERE type(r) <> 'MENTIONS'
                RETURN neighbor.id AS source,
                       [l IN labels(neighbor) WHERE l <> '__Entity__'][0] AS source_type,
                       type(r) AS rel,
                       node.id AS target,
                       [l IN labels(node) WHERE l <> '__Entity__'][0] AS target_type
            }
            RETURN DISTINCT source, source_type, rel, target, target_type
            LIMIT $limit
            """,
            {"node_id": node_id, "limit": limit},
        )
        triples.extend(
            _format_triple(row["source"], row["source_type"], row["rel"], row["target"], row["target_type"])
            for row in rows
        )

    return "\n".join(dict.fromkeys(triples))


def source_text_retriever(graph: Neo4jGraph, node_ids: list[str], limit: int = 3) -> str:
    """Return source chunk text from Document nodes that mention the given graph entity ids."""
    chunks: list[str] = []
    for node_id in node_ids:
        rows = graph.query(
            """
            MATCH (doc:Document)-[:MENTIONS]->(node:__Entity__ {id: $node_id})
            RETURN DISTINCT doc.text AS text
            LIMIT $limit
            """,
            {"node_id": node_id, "limit": limit},
        )
        chunks.extend(row["text"] for row in rows if row["text"])

    return "\n\n".join(dict.fromkeys(chunks))


def retrieve_context(graph: Neo4jGraph, llm: BaseLanguageModel, question: str, limit: int = 5) -> str:
    """Combine graph relationship triples and source chunk text into one context string."""
    entities = extract_entities(llm, question)
    node_ids = _match_entities(graph, entities, limit)
    if not node_ids:
        logger.warning("No graph entities matched for question: %s (entities: %s)", question, entities)
        return ""

    relationships = structured_retriever(graph, node_ids, limit)
    source_text = source_text_retriever(graph, node_ids, limit)

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

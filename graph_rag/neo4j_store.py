"""Write extracted GraphDocuments into Neo4j and verify the write."""
from __future__ import annotations

import logging

from langchain_neo4j import Neo4jGraph
from langchain_neo4j.graphs.graph_document import GraphDocument

logger = logging.getLogger(__name__)


def build_neo4j_graph(uri: str, username: str, password: str, database: str) -> Neo4jGraph:
    """Create a Neo4jGraph connection using credentials sourced from environment variables."""
    logger.info("Connecting to Neo4j at %s (database=%s)", uri, database)
    return Neo4jGraph(url=uri, username=username, password=password, database=database)


def write_graph_documents(graph: Neo4jGraph, graph_documents: list[GraphDocument]) -> None:
    """Write extracted nodes and relationships from GraphDocuments into Neo4j."""
    if not graph_documents:
        logger.warning("No graph documents to write; skipping Neo4j write")
        return

    logger.info("Writing %d graph document(s) to Neo4j", len(graph_documents))
    graph.add_graph_documents(
        graph_documents,
        baseEntityLabel=True,
        include_source=True,
    )
    logger.info(
        "Wrote %d node(s) and %d relationship(s) to Neo4j",
        sum(len(gd.nodes) for gd in graph_documents),
        sum(len(gd.relationships) for gd in graph_documents),
    )


def verify_graph_written(graph: Neo4jGraph) -> dict[str, int]:
    """Run a simple count query confirming nodes/relationships exist in Neo4j."""
    node_result = graph.query("MATCH (n) RETURN count(n) AS count")
    rel_result = graph.query("MATCH ()-[r]->() RETURN count(r) AS count")

    node_count = int(node_result[0]["count"]) if node_result else 0
    rel_count = int(rel_result[0]["count"]) if rel_result else 0

    logger.info(
        "Verification query: %d node(s), %d relationship(s) found in Neo4j",
        node_count,
        rel_count,
    )
    return {"nodes": node_count, "relationships": rel_count}

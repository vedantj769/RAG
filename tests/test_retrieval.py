"""Live smoke test: retrieve graph context and answer a question (requires a real .env)."""
from __future__ import annotations

from pathlib import Path

import pytest
from fpdf import FPDF

from graph_rag.chunking import split_documents
from graph_rag.config import ConfigError, load_settings
from graph_rag.graph_extraction import build_graph_transformer, extract_graph_documents
from graph_rag.llm import build_groq_llm
from graph_rag.loader import load_pdf_documents
from graph_rag.neo4j_store import build_neo4j_graph, write_graph_documents
from graph_rag.retrieval import answer_question, retrieve_context

SAMPLE_TEXT = (
    "Marie Curie was a physicist and chemist who conducted pioneering research "
    "on radioactivity. She worked at the University of Paris and won the Nobel "
    "Prize in Physics in 1903 and the Nobel Prize in Chemistry in 1911."
)


def _make_sample_pdf(path: Path) -> None:
    """Write a small PDF containing named entities/relationships to extract."""
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("helvetica", size=12)
    pdf.set_x(pdf.l_margin)
    pdf.multi_cell(pdf.epw, 8, SAMPLE_TEXT)
    pdf.output(str(path))


def test_retrieve_context_and_answer_question(tmp_path: Path) -> None:
    try:
        settings = load_settings()
    except ConfigError as exc:
        pytest.skip(f"Skipping live retrieval test: {exc}")

    _make_sample_pdf(tmp_path / "sample.pdf")
    documents = load_pdf_documents(str(tmp_path))
    chunks = split_documents(documents, settings.chunk_size, settings.chunk_overlap)

    llm = build_groq_llm(settings.groq_api_key, settings.groq_model)
    transformer = build_graph_transformer(llm)
    graph_documents = extract_graph_documents(transformer, chunks)
    assert graph_documents, "Expected at least one GraphDocument to be extracted"

    graph = build_neo4j_graph(
        settings.neo4j_uri,
        settings.neo4j_username,
        settings.neo4j_password,
        settings.neo4j_database,
    )
    try:
        write_graph_documents(graph, graph_documents)

        question = "What did Marie Curie win the Nobel Prize for?"
        context = retrieve_context(graph, llm, question, limit=settings.retrieval_top_k)
        print(f"\nRetrieved context:\n{context}")
        assert context, "Expected non-empty context retrieved from the graph"

        answer = answer_question(graph, llm, question, top_k=settings.retrieval_top_k)
        print(f"\nAnswer: {answer}")
        assert answer
    finally:
        graph.close()

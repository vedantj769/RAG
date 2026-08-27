"""Tests for PDF loading and chunking (no Groq/Neo4j required)."""
from __future__ import annotations

from pathlib import Path

from fpdf import FPDF

from graph_rag.chunking import split_documents
from graph_rag.loader import load_pdf_documents

SAMPLE_TEXT = "Graph RAG combines knowledge graphs with retrieval augmented generation. "


def _make_sample_pdf(path: Path) -> None:
    """Write a small multi-paragraph PDF to `path` for use as test input."""
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("helvetica", size=12)
    for _ in range(40):
        pdf.set_x(pdf.l_margin)
        pdf.multi_cell(pdf.epw, 8, SAMPLE_TEXT)
    pdf.output(str(path))


def test_load_pdf_documents_reads_text(tmp_path: Path) -> None:
    _make_sample_pdf(tmp_path / "sample.pdf")

    documents = load_pdf_documents(str(tmp_path))

    assert documents, "Expected at least one loaded document/page"
    assert any("Graph RAG" in doc.page_content for doc in documents)


def test_load_pdf_documents_empty_directory_returns_empty_list(tmp_path: Path) -> None:
    documents = load_pdf_documents(str(tmp_path))
    assert documents == []


def test_split_documents_creates_multiple_chunks(tmp_path: Path) -> None:
    _make_sample_pdf(tmp_path / "sample.pdf")
    documents = load_pdf_documents(str(tmp_path))

    chunks = split_documents(documents, chunk_size=200, chunk_overlap=20)

    assert len(chunks) > 1
    assert all(chunk.page_content for chunk in chunks)
    assert any("Graph RAG" in chunk.page_content for chunk in chunks)


def test_split_documents_handles_empty_input() -> None:
    assert split_documents([], chunk_size=200, chunk_overlap=20) == []

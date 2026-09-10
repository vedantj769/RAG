"""Tests for heading-based chunking helpers (no Groq/Neo4j required)."""
from __future__ import annotations

from langchain_core.documents import Document

from graph_rag.chunking import split_by_headings, split_by_top_level_sections


def test_split_by_top_level_sections_groups_nested_content() -> None:
    text = "\n".join(
        [
            "# 2. KPI Definitions",
            "## 2.1 OEE",
            "OEE body text",
            "# 3. Data Models",
            "## 3.1 Data Model - Shift OEE",
            "Data model body text",
        ]
    )
    documents = [Document(page_content=text, metadata={"source": "sample.docx"})]

    sections = split_by_top_level_sections(documents)

    assert [s.metadata["heading"] for s in sections] == ["2. KPI Definitions", "3. Data Models"]
    assert "OEE body text" in sections[0].page_content
    assert "Data model body text" not in sections[0].page_content
    assert sections[0].metadata["source"] == "sample.docx"


def test_split_by_top_level_sections_handles_empty_input() -> None:
    assert split_by_top_level_sections([]) == []


def test_split_by_headings_further_splits_a_section() -> None:
    text = "\n".join(
        [
            "# 2. KPI Definitions",
            "## 2.1 OEE",
            "OEE body text",
            "## 2.2 Availability",
            "Availability body text",
        ]
    )
    section = Document(page_content=text, metadata={"heading": "2. KPI Definitions"})

    chunks = split_by_headings([section])

    assert len(chunks) == 2
    assert "OEE body text" in chunks[0].page_content
    assert "Availability body text" in chunks[1].page_content
    assert all(chunk.page_content.startswith("# 2. KPI Definitions") for chunk in chunks)

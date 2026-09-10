"""Tests for the pre-chunked/pre-classified JSON export loader (no Groq/Neo4j needed)."""
from __future__ import annotations

import json
from pathlib import Path

from graph_rag.loader import load_chunk_export

SAMPLE_CHUNKS = [
    {
        "chunk_index": 0,
        "knowledge_type": "data_model",
        "section_heading": "3.1 Data Model",
        "table_index": 0,
        "headers": ["Field", "Entry"],
        "records": [
            {"Field": "Model / Table / Entity Name", "Entry": "tOEEShiftDetailsForWorkCenter"},
        ],
    },
    {
        "chunk_index": 1,
        "knowledge_type": "data_model",
        "section_heading": "3.1 Data Model",
        "table_index": 1,
        "headers": ["Field Name", "Data Type", "Business Meaning"],
        "records": [
            {"Field Name": "OEE", "Data Type": "decimal", "Business Meaning": "Shift OEE percentage"},
        ],
    },
    {
        "chunk_index": 2,
        "knowledge_type": "kpi_definition",
        "section_heading": "3.1 Data Model",
        "table_index": 2,
        "headers": ["Metric", "Formula"],
        "records": [
            {"Metric": "OEE", "Formula": "Availability x Performance x Quality"},
        ],
    },
]


def _write_sample(path: Path) -> Path:
    file_path = path / "chunks.json"
    file_path.write_text(json.dumps(SAMPLE_CHUNKS), encoding="utf-8")
    return file_path


def test_load_chunk_export_merges_same_heading_and_type(tmp_path: Path) -> None:
    documents = load_chunk_export(str(_write_sample(tmp_path)))

    data_model_docs = [d for d in documents if d.metadata["knowledge_type"] == "data_model"]
    assert len(data_model_docs) == 1
    assert "tOEEShiftDetailsForWorkCenter" in data_model_docs[0].page_content
    assert "Shift OEE percentage" in data_model_docs[0].page_content


def test_load_chunk_export_keeps_same_heading_different_type_separate(tmp_path: Path) -> None:
    documents = load_chunk_export(str(_write_sample(tmp_path)))

    kpi_docs = [d for d in documents if d.metadata["knowledge_type"] == "kpi_definition"]
    assert len(kpi_docs) == 1
    assert "Availability x Performance x Quality" in kpi_docs[0].page_content
    assert len(documents) == 2


def test_load_chunk_export_renders_wide_table_with_header_row(tmp_path: Path) -> None:
    documents = load_chunk_export(str(_write_sample(tmp_path)))

    data_model_doc = next(d for d in documents if d.metadata["knowledge_type"] == "data_model")
    assert "Field Name | Data Type | Business Meaning" in data_model_doc.page_content


def test_load_chunk_export_missing_file_raises(tmp_path: Path) -> None:
    try:
        load_chunk_export(str(tmp_path / "missing.json"))
        assert False, "Expected FileNotFoundError"
    except FileNotFoundError:
        pass

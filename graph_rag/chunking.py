"""Split loaded documents into smaller chunks suitable for LLM processing."""
from __future__ import annotations

import logging

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

logger = logging.getLogger(__name__)


def split_documents(
    documents: list[Document], chunk_size: int, chunk_overlap: int
) -> list[Document]:
    """Split documents into overlapping chunks."""
    if not documents:
        return []

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
    )
    chunks = splitter.split_documents(documents)
    logger.info("Split %d document(s) into %d chunk(s)", len(documents), len(chunks))
    return chunks


def split_by_headings(documents: list[Document], section_marker: str = "##") -> list[Document]:
    """Split each document into one chunk per `section_marker` heading (see
    `graph_rag.loader.load_docx_documents`, which prefixes headings with `#`/`##`/`###`).

    Unlike `split_documents`, this never splits a heading and its data (e.g. a table)
    across two chunks - important for extraction, since a small record like a single
    KPI definition must stay intact in one chunk for the LLM to link its fields
    together correctly. The most recent top-level (`#`) heading is carried forward as
    context on every section.
    """
    if not documents:
        return []

    chunks: list[Document] = []
    for document in documents:
        top_level_heading = ""
        current_section: list[str] = []

        def flush(section: list[str]) -> None:
            if section:
                text = "\n".join(([top_level_heading] if top_level_heading else []) + section)
                chunks.append(Document(page_content=text, metadata=document.metadata))

        for line in document.page_content.splitlines():
            if line.startswith("# "):
                top_level_heading = line
                continue
            if line.startswith(f"{section_marker} "):
                flush(current_section)
                current_section = [line]
            else:
                current_section.append(line)
        flush(current_section)

    logger.info("Split %d document(s) into %d heading-based section(s)", len(documents), len(chunks))
    return chunks

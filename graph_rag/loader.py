"""Load PDF documents from the configured documents directory."""
from __future__ import annotations

import json
import logging
from pathlib import Path

import docx
from docx.table import Table
from docx.text.paragraph import Paragraph
from langchain_community.document_loaders import PyPDFLoader
from langchain_core.documents import Document

logger = logging.getLogger(__name__)

_HEADING_STYLES = {"Heading 1": "#", "Heading 2": "##", "Heading 3": "###"}


def load_pdf_documents(documents_dir: str) -> list[Document]:
    """Load all PDF files found in `documents_dir` into LangChain Documents."""
    directory = Path(documents_dir)
    if not directory.exists():
        raise FileNotFoundError(f"Documents directory not found: {directory}")

    pdf_paths = sorted(directory.glob("*.pdf"))
    if not pdf_paths:
        logger.warning("No PDF files found in %s", directory)
        return []

    documents: list[Document] = []
    for pdf_path in pdf_paths:
        try:
            logger.info("Loading PDF: %s", pdf_path)
            loader = PyPDFLoader(str(pdf_path))
            documents.extend(loader.load())
        except Exception:
            logger.exception("Failed to load PDF file: %s", pdf_path)

    logger.info("Loaded %d page(s) from %d PDF file(s)", len(documents), len(pdf_paths))
    return documents


def load_docx_documents(documents_dir: str) -> list[Document]:
    """Load all DOCX files found in `documents_dir` into LangChain Documents.

    Headings are prefixed with markdown-style `#`/`##`/`###` markers and tables are
    flattened into `key: value` (2-column) or `|`-separated (wider) lines, so table
    content survives downstream text chunking instead of being silently dropped, and
    stays visible to the extraction LLM.
    """
    directory = Path(documents_dir)
    if not directory.exists():
        raise FileNotFoundError(f"Documents directory not found: {directory}")

    docx_paths = sorted(directory.glob("*.docx"))
    if not docx_paths:
        logger.warning("No DOCX files found in %s", directory)
        return []

    documents: list[Document] = []
    for docx_path in docx_paths:
        try:
            logger.info("Loading DOCX: %s", docx_path)
            text = _docx_to_text(docx_path)
            if text.strip():
                documents.append(Document(page_content=text, metadata={"source": str(docx_path)}))
        except Exception:
            logger.exception("Failed to load DOCX file: %s", docx_path)

    logger.info("Loaded %d DOCX file(s)", len(documents))
    return documents


def load_chunk_export(path: str) -> list[Document]:
    """Load a pre-chunked, pre-classified JSON export (one entry per source table:
    chunk_index, knowledge_type, section_heading, table_index, headers, records).

    Unlike `load_docx_documents` + `split_by_headings`/`split_by_top_level_sections`,
    each entry here already carries its own `knowledge_type` - matching a
    `skills/<knowledge_type>/SKILL.md` folder name - so no LLM routing call is needed;
    callers can group the returned Documents by `metadata["knowledge_type"]` directly.

    Entries are merged by `(section_heading, knowledge_type)` (preserving order of
    first appearance) before being rendered, since one knowledge item is often split
    across multiple table entries in the export (e.g. a data_model's metadata block
    and its field-breakdown table are two entries with the same heading/type but
    different `table_index` - they must land in ONE chunk, same reasoning as
    `split_by_headings` for DOCX content).
    """
    file_path = Path(path)
    if not file_path.is_file():
        raise FileNotFoundError(f"Chunk export file not found: {file_path}")

    chunks = json.loads(file_path.read_text(encoding="utf-8"))

    grouped: dict[tuple[str, str], list[str]] = {}
    for chunk in chunks:
        key = (chunk.get("section_heading", ""), chunk.get("knowledge_type", ""))
        grouped.setdefault(key, []).append(
            _render_chunk_table(chunk.get("headers", []), chunk.get("records", []))
        )

    documents = [
        Document(
            page_content="\n".join([f"# {heading}"] + blocks),
            metadata={"source": str(file_path), "knowledge_type": knowledge_type, "heading": heading},
        )
        for (heading, knowledge_type), blocks in grouped.items()
    ]
    logger.info("Loaded %d chunk(s) from %d table entr(y/ies) in %s", len(documents), len(chunks), file_path)
    return documents


def _render_chunk_table(headers: list[str], records: list[dict]) -> str:
    """Render one chunk-export table entry as text, mirroring `_docx_to_text`'s
    conventions: 2-column tables become `key: value` lines (using each row's own
    first-column value as the key, e.g. "KPI Name: OEE"); wider tables include the
    header row once, then each row's values `|`-joined, so column meaning isn't lost.
    """
    if not records:
        return "\n".join(headers)

    if len(headers) == 2:
        return "\n".join(f"{record.get(headers[0], '')}: {record.get(headers[1], '')}" for record in records)

    lines = [" | ".join(headers)]
    lines.extend(" | ".join(str(record.get(h, "")) for h in headers) for record in records)
    return "\n".join(lines)


def _docx_to_text(path: Path) -> str:
    """Flatten a DOCX's paragraphs and tables, in document order, into plain text."""
    document = docx.Document(str(path))
    lines: list[str] = []

    for child in document.element.body.iterchildren():
        tag = child.tag.split("}")[-1]
        if tag == "p":
            paragraph = Paragraph(child, document)
            text = paragraph.text.strip()
            if not text:
                continue
            marker = _HEADING_STYLES.get(paragraph.style.name if paragraph.style else "")
            lines.append(f"{marker} {text}" if marker else text)
        elif tag == "tbl":
            table = Table(child, document)
            for row in table.rows:
                cells = [cell.text.strip() for cell in row.cells]
                if not any(cells):
                    continue
                lines.append(": ".join(cells) if len(cells) == 2 else " | ".join(cells))

    return "\n".join(lines)

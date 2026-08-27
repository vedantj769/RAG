"""Load PDF documents from the configured documents directory."""
from __future__ import annotations

import logging
from pathlib import Path

from langchain_community.document_loaders import PyPDFLoader
from langchain_core.documents import Document

logger = logging.getLogger(__name__)


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

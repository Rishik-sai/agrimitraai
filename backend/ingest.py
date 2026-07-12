# ingest.py
"""Document ingestion script for AgriMitra Multi-RAG backend.
Loads agricultural documents from the `data/docs` directory, splits them into chunks,
creates embeddings using a lightweight model, and stores them in a local FAISS vector store.
"""

import os
import logging
from pathlib import Path
from typing import List

from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import DirectoryLoader, TextLoader, PDFMinerLoader
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# Directory containing raw documents (txt or pdf)
DOCS_DIR = Path(__file__).parent / "data" / "docs"
# Persisted FAISS index location
FAISS_INDEX_PATH = Path(__file__).parent / "faiss_index"

# Embedding model — switched to a smaller English-centric model to fit Render 512MB limit
EMBEDDING_MODEL_NAME = "all-MiniLM-L6-v2"


def load_documents() -> List:
    """Load text and PDF documents from DOCS_DIR."""
    if not DOCS_DIR.exists():
        logger.error(f"Documents directory not found: {DOCS_DIR}")
        raise FileNotFoundError(f"Documents directory not found: {DOCS_DIR}")

    txt_loader = DirectoryLoader(
        str(DOCS_DIR),
        glob="*.txt",
        loader_cls=TextLoader,
        loader_kwargs={"encoding": "utf-8"},
        show_progress=True,
    )
    txt_docs = txt_loader.load()
    logger.info(f"Loaded {len(txt_docs)} text documents from {DOCS_DIR}")

    pdf_loader = DirectoryLoader(
        str(DOCS_DIR),
        glob="*.pdf",
        loader_cls=PDFMinerLoader,
        show_progress=True,
    )
    try:
        pdf_docs = pdf_loader.load()
        logger.info(f"Loaded {len(pdf_docs)} PDF documents from {DOCS_DIR}")
    except Exception as e:
        logger.error(f"Error loading PDFs: {e}")
        pdf_docs = []

    docs = txt_docs + pdf_docs
    logger.info(f"Total documents loaded: {len(docs)}")
    return docs


def split_documents(docs, chunk_size=800, chunk_overlap=150):
    """Split documents into manageable chunks for embedding.

    Uses smaller chunks (800 chars) with overlap for better retrieval precision
    in a multi-agent context where each agent needs focused, relevant snippets.
    """
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=["\n\n", "\n", "SECTION:", "SCHEME:", "CROP:", ". ", " "],
    )
    chunks = splitter.split_documents(docs)
    logger.info(f"Split into {len(chunks)} chunks (size={chunk_size}, overlap={chunk_overlap})")
    return chunks


def create_vector_store(chunks):
    """Create a FAISS vector store from document chunks and save to disk."""
    logger.info(f"Creating embeddings with model: {EMBEDDING_MODEL_NAME}")
    import torch
    torch.set_num_threads(1)
    embedding_model = HuggingFaceEmbeddings(
        model_name=EMBEDDING_MODEL_NAME,
        model_kwargs={'device': 'cpu'}
    )

    logger.info("Building FAISS index...")
    vectordb = FAISS.from_documents(chunks, embedding_model)

    # Save to disk
    FAISS_INDEX_PATH.mkdir(parents=True, exist_ok=True)
    vectordb.save_local(str(FAISS_INDEX_PATH))
    logger.info(f"FAISS index saved to {FAISS_INDEX_PATH}")
    return vectordb


def ingest():
    """Run the full ingestion pipeline."""
    logger.info("=" * 60)
    logger.info("Starting AgriMitra document ingestion pipeline")
    logger.info("=" * 60)

    docs = load_documents()
    if not docs:
        logger.warning("No documents found. Exiting.")
        return

    chunks = split_documents(docs)
    vectordb = create_vector_store(chunks)

    logger.info("=" * 60)
    logger.info(f"✅ Ingestion complete: {len(docs)} docs → {len(chunks)} chunks")
    logger.info(f"   FAISS index saved at: {FAISS_INDEX_PATH}")
    logger.info("=" * 60)
    return vectordb


if __name__ == "__main__":
    ingest()

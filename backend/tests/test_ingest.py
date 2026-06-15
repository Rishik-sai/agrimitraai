import pytest
from langchain_core.documents import Document
from ingest import split_documents

def test_split_documents_chunks_created_correctly():
    # Create a mock document that is longer than the chunk size, with spaces to allow splitting
    long_text = "A " * 500 + "B " * 250
    docs = [Document(page_content=long_text, metadata={"source": "mock.txt"})]
    
    # Use smaller chunk size for testing
    chunk_size = 800
    chunk_overlap = 150
    
    chunks = split_documents(docs, chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    
    # Ensure multiple chunks are created
    assert len(chunks) > 1, "Should create more than one chunk for long text"
    
    # Ensure chunks don't exceed chunk_size
    for chunk in chunks:
        assert len(chunk.page_content) <= chunk_size, f"Chunk size {len(chunk.page_content)} exceeds limit {chunk_size}"
    
    # Check that metadata is preserved
    assert chunks[0].metadata["source"] == "mock.txt"

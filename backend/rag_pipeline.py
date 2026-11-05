"""
rag_pipeline.py
───────────────
Retrieval-Augmented Generation (RAG) pipeline.

Steps:
  1. Chunk – split long text into overlapping segments.
  2. Embed  – convert chunks to vectors using IBM Granite embedding model
              via watsonx.ai SDK.
  3. Store  – persist vectors in a FAISS in-memory index (saved to disk).
  4. Query  – embed the question, find the nearest chunks, return them as
              context for the Granite LLM.
"""

import json
import logging
import os
import pickle
from pathlib import Path
from typing import List, Tuple

import numpy as np

logger = logging.getLogger(__name__)

# Path where the FAISS index + chunk list are saved between requests
_INDEX_DIR = Path(__file__).parent.parent / "uploads" / "vector_store"
_INDEX_FILE = _INDEX_DIR / "faiss.index"
_CHUNKS_FILE = _INDEX_DIR / "chunks.pkl"

# IBM Granite embedding model identifier
EMBED_MODEL_ID = "ibm/granite-embedding-278m-multilingual"


# ─────────────────────────────────────────────────────────────────────────────
# 1. Chunking
# ─────────────────────────────────────────────────────────────────────────────

def chunk_text(text: str, chunk_size: int = 400, overlap: int = 80) -> List[str]:
    """
    Split `text` into overlapping word-based chunks.

    Args:
        text:       raw extracted text
        chunk_size: approximate number of words per chunk
        overlap:    number of words shared between consecutive chunks

    Returns:
        list of text chunk strings
    """
    words = text.split()
    chunks = []
    start = 0
    while start < len(words):
        end = start + chunk_size
        chunk = " ".join(words[start:end])
        chunks.append(chunk)
        start += chunk_size - overlap  # slide forward with overlap
    logger.info("Created %d chunks from %d words.", len(chunks), len(words))
    return chunks


# ─────────────────────────────────────────────────────────────────────────────
# 2. Embedding via watsonx.ai
# ─────────────────────────────────────────────────────────────────────────────

def _get_watsonx_client():
    """Build and return a watsonx.ai APIClient (lazy import)."""
    from ibm_watsonx_ai import APIClient, Credentials
    api_key = os.environ.get("WATSONX_API_KEY")
    url = os.environ.get("WATSONX_URL", "https://us-south.ml.cloud.ibm.com")
    if not api_key:
        raise EnvironmentError("WATSONX_API_KEY is not set. Check your .env file.")
    creds = Credentials(url=url, api_key=api_key)
    return APIClient(creds)


def embed_chunks(chunks: List[str]) -> Tuple[np.ndarray, int]:
    """
    Embed a list of text chunks using the Granite embedding model.

    Returns:
        (matrix of shape [N, D], total tokens used)
    """
    from ibm_watsonx_ai.foundation_models import Embeddings
    from ibm_watsonx_ai.metanames import EmbedTextParamsMetaNames as EmbedParams

    project_id = os.environ.get("WATSONX_PROJECT_ID")
    if not project_id:
        raise EnvironmentError("WATSONX_PROJECT_ID is not set. Check your .env file.")

    client = _get_watsonx_client()

    embed_model = Embeddings(
        model_id=EMBED_MODEL_ID,
        credentials=client.credentials,
        project_id=project_id,
        params={EmbedParams.TRUNCATE_INPUT_TOKENS: 512},
    )

    # watsonx embed API accepts a list of strings
    response = embed_model.embed_documents(texts=chunks)

    vectors = np.array(response, dtype="float32")
    # token usage is not exposed by the embeddings endpoint; estimate from chars
    token_estimate = sum(len(c) // 4 for c in chunks)
    logger.info("Embedded %d chunks → shape %s.", len(chunks), vectors.shape)
    return vectors, token_estimate


# ─────────────────────────────────────────────────────────────────────────────
# 3. FAISS vector store
# ─────────────────────────────────────────────────────────────────────────────

def build_index(vectors: np.ndarray) -> "faiss.IndexFlatL2":  # type: ignore[name-defined]
    """Create a new FAISS flat-L2 index from a vector matrix."""
    import faiss
    dim = vectors.shape[1]
    index = faiss.IndexFlatL2(dim)
    index.add(vectors)
    logger.info("FAISS index built with %d vectors (dim=%d).", index.ntotal, dim)
    return index


def save_index(index, chunks: List[str]) -> None:
    """Persist the FAISS index and chunk list to disk."""
    import faiss
    _INDEX_DIR.mkdir(parents=True, exist_ok=True)
    faiss.write_index(index, str(_INDEX_FILE))
    with open(_CHUNKS_FILE, "wb") as f:
        pickle.dump(chunks, f)
    logger.info("Saved vector store to %s", _INDEX_DIR)


def load_index():
    """Load a previously saved index + chunks. Returns (index, chunks) or (None, [])."""
    import faiss
    if _INDEX_FILE.exists() and _CHUNKS_FILE.exists():
        index = faiss.read_index(str(_INDEX_FILE))
        with open(_CHUNKS_FILE, "rb") as f:
            chunks = pickle.load(f)
        logger.info("Loaded vector store: %d vectors.", index.ntotal)
        return index, chunks
    return None, []


# ─────────────────────────────────────────────────────────────────────────────
# 4. Query – retrieve relevant chunks
# ─────────────────────────────────────────────────────────────────────────────

def retrieve_context(query: str, top_k: int = 5) -> str:
    """
    Embed the query and retrieve the top-k most relevant text chunks
    from the stored FAISS index.

    Returns:
        A single string with the top-k chunks joined by newlines.
    """
    index, chunks = load_index()
    if index is None or not chunks:
        logger.warning("No vector store found. Returning empty context.")
        return ""

    query_vec, _ = embed_chunks([query])
    distances, indices = index.search(query_vec, top_k)
    retrieved = [chunks[i] for i in indices[0] if i < len(chunks)]
    logger.info("Retrieved %d chunks for query.", len(retrieved))
    return "\n\n---\n\n".join(retrieved)


# ─────────────────────────────────────────────────────────────────────────────
# Public helper: ingest new documents into the vector store
# ─────────────────────────────────────────────────────────────────────────────

def ingest_text(text: str) -> dict:
    """
    Full ingestion pipeline for a single document's text.

    1. Chunk the text.
    2. Embed with Granite.
    3. Merge with any existing FAISS index (for Update mode).
    4. Save.

    Returns:
        dict with "chunks_added" and "embed_tokens" for the dashboard.
    """
    import faiss

    new_chunks = chunk_text(text)
    if not new_chunks:
        return {"chunks_added": 0, "embed_tokens": 0}

    new_vectors, token_est = embed_chunks(new_chunks)

    # Load existing index if present, otherwise start fresh
    existing_index, existing_chunks = load_index()

    if existing_index is not None:
        # Merge: add new vectors into the existing index
        existing_index.add(new_vectors)
        all_chunks = existing_chunks + new_chunks
        save_index(existing_index, all_chunks)
    else:
        new_index = build_index(new_vectors)
        save_index(new_index, new_chunks)

    return {"chunks_added": len(new_chunks), "embed_tokens": token_est}

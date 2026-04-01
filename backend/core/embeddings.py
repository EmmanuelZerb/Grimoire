"""Grimoire — ChromaDB vector store for code chunk embeddings.

Provides functions to index code chunks and query similar documents.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import chromadb

from graph.state import CodeChunk

logger = logging.getLogger(__name__)

_client: chromadb.ClientAPI | None = None
_collection: chromadb.Collection | None = None


def _get_client(persist_dir: str = "./data/chroma") -> chromadb.ClientAPI:
    """Get or create the ChromaDB client."""
    global _client
    if _client is None:
        Path(persist_dir).mkdir(parents=True, exist_ok=True)
        _client = chromadb.PersistentClient(path=persist_dir)
    return _client


def get_collection(
    job_id: str, persist_dir: str = "./data/chroma"
) -> chromadb.Collection:
    """Get or create a ChromaDB collection for a specific job."""
    client = _get_client(persist_dir)
    collection_name = f"grimoire_{job_id}"
    try:
        return client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"},
        )
    except Exception:
        # If collection exists with different config, get it
        return client.get_collection(name=collection_name)


def index_chunks(
    job_id: str,
    chunks: list[CodeChunk],
    persist_dir: str = "./data/chroma",
) -> int:
    """Index code chunks into a ChromaDB collection.

    Args:
        job_id: Unique job identifier.
        chunks: Code chunks to index.
        persist_dir: Directory for ChromaDB persistence.

    Returns:
        Number of chunks indexed.
    """
    if not chunks:
        return 0

    collection = get_collection(job_id, persist_dir)

    # Delete existing documents for this job (idempotent re-index)
    existing = collection.count()
    if existing > 0:
        try:
            collection.delete(where={"job_id": job_id})
        except Exception:
            pass

    ids: list[str] = []
    documents: list[str] = []
    metadatas: list[dict[str, Any]] = []

    for chunk in chunks:
        ids.append(chunk.chunk_id)
        # Combine path + name + content for better retrieval
        documents.append(
            f"File: {chunk.file_path}\n"
            f"Type: {chunk.node_type}\n"
            f"Name: {chunk.name}\n"
            f"Lines: {chunk.start_line}-{chunk.end_line}\n"
            f"Language: {chunk.language}\n"
            f"Dependencies: {', '.join(chunk.dependencies) or 'none'}\n\n"
            f"{chunk.content}"
        )
        metadatas.append({
            "job_id": job_id,
            "file_path": chunk.file_path,
            "node_type": chunk.node_type,
            "name": chunk.name,
            "start_line": chunk.start_line,
            "end_line": chunk.end_line,
            "language": chunk.language,
        })

    # ChromaDB has a batch size limit, chunk if needed
    batch_size = 500
    total_indexed = 0

    for i in range(0, len(ids), batch_size):
        batch_ids = ids[i : i + batch_size]
        batch_docs = documents[i : i + batch_size]
        batch_meta = metadatas[i : i + batch_size]

        collection.upsert(
            ids=batch_ids,
            documents=batch_docs,
            metadatas=batch_meta,
        )
        total_indexed += len(batch_ids)

    logger.info(
        "[%s] Indexed %d chunks into ChromaDB (collection: grimoire_%s)",
        job_id,
        total_indexed,
        job_id,
    )

    return total_indexed


def query_chunks(
    job_id: str,
    question: str,
    n_results: int = 5,
    persist_dir: str = "./data/chroma",
) -> list[dict[str, Any]]:
    """Query the vector store for chunks similar to the question.

    Args:
        job_id: Unique job identifier.
        question: The user's question.
        n_results: Number of results to return.
        persist_dir: Directory for ChromaDB persistence.

    Returns:
        List of dicts with chunk content and metadata.
    """
    collection = get_collection(job_id, persist_dir)

    if collection.count() == 0:
        return []

    try:
        results = collection.query(
            query_texts=[question],
            n_results=min(n_results, collection.count()),
            include=["documents", "metadatas", "distances"],
        )
    except Exception as e:
        logger.warning("[%s] ChromaDB query failed: %s", job_id, e)
        return []

    if not results["documents"] or not results["documents"][0]:
        return []

    chunks_out: list[dict[str, Any]] = []
    for i, doc in enumerate(results["documents"][0]):
        meta = results["metadatas"][0][i] if results["metadatas"] else {}
        distance = results["distances"][0][i] if results["distances"] else 0
        chunks_out.append({
            "content": doc,
            "metadata": meta,
            "distance": round(distance, 4),
        })

    return chunks_out


def delete_collection(job_id: str, persist_dir: str = "./data/chroma") -> None:
    """Delete the ChromaDB collection for a job."""
    try:
        client = _get_client(persist_dir)
        client.delete_collection(name=f"grimoire_{job_id}")
        logger.info("[%s] Deleted ChromaDB collection", job_id)
    except Exception:
        pass

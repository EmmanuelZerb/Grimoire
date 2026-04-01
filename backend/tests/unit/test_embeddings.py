"""Unit tests for core/embeddings.py."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from graph.state import CodeChunk


# --- Helpers ---


def _chunk(file_path: str = "main.py", name: str = "foo", content: str = "pass") -> CodeChunk:
    return CodeChunk(
        chunk_id=f"test:{file_path}:{name}",
        content=content,
        file_path=file_path,
        start_line=1,
        end_line=1,
        language="Python",
        node_type="function",
        name=name,
        dependencies=(),
    )


# --- index_chunks ---


class TestIndexChunks:
    @patch("core.embeddings.get_collection")
    def test_empty_chunks_returns_zero(self, mock_get_collection):
        mock_collection = MagicMock()
        mock_get_collection.return_value = mock_collection
        from core.embeddings import index_chunks
        assert index_chunks("job1", []) == 0

    @patch("core.embeddings.get_collection")
    def test_indexes_all_chunks(self, mock_get_collection):
        mock_collection = MagicMock()
        mock_collection.count.return_value = 0
        mock_get_collection.return_value = mock_collection
        from core.embeddings import index_chunks

        chunks = [_chunk("a.py"), _chunk("b.py")]
        result = index_chunks("job1", chunks)

        assert result == 2
        mock_collection.upsert.assert_called_once()
        call_kwargs = mock_collection.upsert.call_args[1]
        assert len(call_kwargs["ids"]) == 2
        assert len(call_kwargs["documents"]) == 2
        assert len(call_kwargs["metadatas"]) == 2

    @patch("core.embeddings.get_collection")
    def test_deletes_existing_before_reindex(self, mock_get_collection):
        mock_collection = MagicMock()
        mock_collection.count.return_value = 5
        mock_get_collection.return_value = mock_collection
        from core.embeddings import index_chunks

        index_chunks("job1", [_chunk()])
        mock_collection.delete.assert_called_once_with(where={"job_id": "job1"})


# --- query_chunks ---


class TestQueryChunks:
    @patch("core.embeddings.get_collection")
    def test_empty_collection_returns_empty(self, mock_get_collection):
        mock_collection = MagicMock()
        mock_collection.count.return_value = 0
        mock_get_collection.return_value = mock_collection
        from core.embeddings import query_chunks

        assert query_chunks("job1", "hello") == []

    @patch("core.embeddings.get_collection")
    def test_returns_formatted_results(self, mock_get_collection):
        mock_collection = MagicMock()
        mock_collection.count.return_value = 2
        mock_collection.query.return_value = {
            "documents": [["doc1", "doc2"]],
            "metadatas": [[{"file_path": "a.py"}, {"file_path": "b.py"}]],
            "distances": [[0.1, 0.5]],
        }
        mock_get_collection.return_value = mock_collection
        from core.embeddings import query_chunks

        results = query_chunks("job1", "hello")
        assert len(results) == 2
        assert results[0]["content"] == "doc1"
        assert results[0]["metadata"]["file_path"] == "a.py"
        assert results[0]["distance"] == 0.1

    @patch("core.embeddings.get_collection")
    def test_query_failure_returns_empty(self, mock_get_collection):
        mock_collection = MagicMock()
        mock_collection.count.return_value = 5
        mock_collection.query.side_effect = Exception("boom")
        mock_get_collection.return_value = mock_collection
        from core.embeddings import query_chunks

        assert query_chunks("job1", "hello") == []


# --- delete_collection ---


class TestDeleteCollection:
    @patch("core.embeddings._get_client")
    def test_deletes_collection(self, mock_get_client):
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        from core.embeddings import delete_collection

        delete_collection("job1")
        mock_client.delete_collection.assert_called_once_with(name="grimoire_job1")

    @patch("core.embeddings._get_client")
    def test_handles_missing_collection(self, mock_get_client):
        mock_client = MagicMock()
        mock_client.delete_collection.side_effect = Exception("not found")
        mock_get_client.return_value = mock_client
        from core.embeddings import delete_collection

        # Should not raise
        delete_collection("job1")

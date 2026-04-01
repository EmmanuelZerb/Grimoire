"""Unit tests for core/rag.py."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from graph.state import (
    AgentName,
    ArchitectureReport,
    CodeChunk,
    GrimoireState,
    LanguageStats,
    PipelineStatus,
    RepoManifest,
    TechDebtCategory,
    TechDebtReport,
)


# --- Helpers ---


def _make_state(**overrides: object) -> GrimoireState:
    manifest = RepoManifest(
        repo_name="test-repo",
        repo_url="https://github.com/test/repo",
        clone_path="/tmp/test",
        total_files=3,
        total_lines=60,
        languages=(LanguageStats(name="Python", file_count=2, total_lines=40, extensions=(".py",)),),
        contributors=(),
        last_commits=(),
        directory_tree={},
        detected_patterns=("Layered",),
    )

    arch = ArchitectureReport(
        dependency_graph={"main": ["utils"], "utils": []},
        entry_points=("main",),
        core_modules=(),
        orphan_modules=(),
        dependency_cycles=(),
        detected_pattern="layered",
        mermaid_diagram="graph TD",
        module_descriptions={"main": "Entry point"},
    )

    debt = TechDebtReport(
        overall_score=25.0,
        categories=(TechDebtCategory(name="Complexity", score=30.0, findings=(), severity="medium"),),
        outdated_dependencies=(),
        todos_fixmes=(),
        summary_markdown="# Test",
    )

    state: GrimoireState = {
        "job_id": "test123",
        "github_url": "https://github.com/test/repo",
        "status": PipelineStatus.COMPLETED,
        "current_agent": AgentName.QA_INTERFACE,
        "repo_manifest": manifest,
        "chunks": [],
        "total_chunks": 0,
        "architecture_report": arch,
        "tech_debt_report": debt,
        "qa_history": [],
        "agent_logs": [],
        "total_tokens_used": 0,
        "error_message": None,
        "started_at": 1000.0,
        "completed_at": 2000.0,
    }
    state.update(overrides)
    return state


# --- _build_context ---


class TestBuildContext:
    @patch("core.rag.query_chunks", return_value=[])
    def test_includes_manifest_info(self, mock_query):
        from core.rag import _build_context
        state = _make_state()
        ctx = _build_context([], state["repo_manifest"], state["architecture_report"], state["tech_debt_report"])
        assert "test-repo" in ctx
        assert "Python" in ctx

    @patch("core.rag.query_chunks", return_value=[])
    def test_includes_architecture_info(self, mock_query):
        from core.rag import _build_context
        state = _make_state()
        ctx = _build_context([], state["repo_manifest"], state["architecture_report"], None)
        assert "layered" in ctx
        assert "main" in ctx

    @patch("core.rag.query_chunks", return_value=[])
    def test_includes_tech_debt_info(self, mock_query):
        from core.rag import _build_context
        state = _make_state()
        ctx = _build_context([], None, None, state["tech_debt_report"])
        assert "25.0" in ctx

    def test_includes_retrieved_chunks(self):
        from core.rag import _build_context
        retrieved = [
            {
                "content": "def hello(): pass",
                "metadata": {"file_path": "main.py", "node_type": "function", "name": "hello", "start_line": 1, "end_line": 1},
                "distance": 0.1,
            }
        ]
        ctx = _build_context(retrieved, None, None, None)
        assert "main.py" in ctx
        assert "def hello(): pass" in ctx

    def test_handles_all_none(self):
        from core.rag import _build_context
        ctx = _build_context([], None, None, None)
        assert isinstance(ctx, str)


# --- ask_question ---


class TestAskQuestion:
    @patch.dict("os.environ", {}, clear=True)
    @patch("core.rag.query_chunks", return_value=[])
    def test_no_api_key_returns_error(self, mock_query):
        from core.rag import ask_question
        state = _make_state()
        result = ask_question(state, "What does main do?")
        assert "ANTHROPIC_API_KEY" in result["answer"]
        assert result["chunks_used"] == 0

    @patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"})
    @patch("core.rag.query_chunks", return_value=[])
    @patch("core.rag.Anthropic")
    def test_calls_claude_with_context(self, mock_anthropic_cls, mock_query):
        mock_client = MagicMock()
        mock_anthropic_cls.return_value = mock_client
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="The main module handles entry.")]
        mock_client.messages.create.return_value = mock_response

        from core.rag import ask_question
        state = _make_state()
        result = ask_question(state, "What does main do?")

        assert result["answer"] == "The main module handles entry."
        assert result["chunks_used"] == 0
        mock_client.messages.create.assert_called_once()
        call_kwargs = mock_client.messages.create.call_args[1]
        assert "main" in call_kwargs["messages"][0]["content"]

    @patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"})
    @patch("core.rag.query_chunks")
    @patch("core.rag.Anthropic")
    def test_includes_sources_from_retrieved_chunks(self, mock_anthropic_cls, mock_query):
        mock_client = MagicMock()
        mock_anthropic_cls.return_value = mock_client
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="Answer.")]
        mock_client.messages.create.return_value = mock_response

        mock_query.return_value = [
            {
                "content": "def foo(): pass",
                "metadata": {"file_path": "utils.py", "node_type": "function", "name": "foo", "start_line": 1, "end_line": 2},
                "distance": 0.2,
            }
        ]

        from core.rag import ask_question
        state = _make_state()
        result = ask_question(state, "What is foo?")

        assert result["chunks_used"] == 1
        assert len(result["sources"]) == 1
        assert result["sources"][0]["file_path"] == "utils.py"

    @patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"})
    @patch("core.rag.query_chunks", return_value=[])
    @patch("core.rag.Anthropic")
    def test_claude_error_returns_error_message(self, mock_anthropic_cls, mock_query):
        mock_client = MagicMock()
        mock_anthropic_cls.return_value = mock_client
        mock_client.messages.create.side_effect = Exception("API down")

        from core.rag import ask_question
        state = _make_state()
        result = ask_question(state, "hello?")

        assert "API down" in result["answer"]

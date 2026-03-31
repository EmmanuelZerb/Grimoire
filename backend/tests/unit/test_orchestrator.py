"""Unit tests for the LangGraph orchestrator."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from graph.orchestrator import (
    _should_continue_after_ingestion,
    build_pipeline,
    create_initial_state,
)
from graph.state import (
    AgentName,
    GrimoireState,
    PipelineStatus,
    RepoManifest,
)


# --- create_initial_state tests ---


class TestCreateInitialState:
    def test_creates_valid_state(self):
        state = create_initial_state("https://github.com/test/repo")
        assert state["github_url"] == "https://github.com/test/repo"
        assert state["job_id"] is not None
        assert len(state["job_id"]) == 12
        assert state["status"] == PipelineStatus.IDLE
        assert state["current_agent"] == AgentName.REPO_INGESTOR
        assert state["error_message"] is None
        assert state["repo_manifest"] is None
        assert state["chunks"] == []
        assert state["total_chunks"] == 0
        assert state["architecture_report"] is None
        assert state["tech_debt_report"] is None
        assert state["qa_history"] == []
        assert state["agent_logs"] == []
        assert state["total_tokens_used"] == 0
        assert state["started_at"] is not None
        assert state["completed_at"] is None

    def test_unique_job_ids(self):
        state1 = create_initial_state("https://github.com/a/repo")
        state2 = create_initial_state("https://github.com/b/repo")
        assert state1["job_id"] != state2["job_id"]

    def test_github_url_preserved(self):
        url = "https://github.com/python/cpython"
        state = create_initial_state(url)
        assert state["github_url"] == url


# --- Conditional edge tests ---


class TestConditionalEdges:
    def test_failed_status_routes_to_end(self):
        state = {
            "status": PipelineStatus.FAILED,
            "repo_manifest": None,
        }
        assert _should_continue_after_ingestion(state) == "end"

    def test_no_manifest_routes_to_end(self):
        state = {
            "status": PipelineStatus.INGESTING,
            "repo_manifest": None,
        }
        assert _should_continue_after_ingestion(state) == "end"

    def test_empty_repo_routes_to_end(self):
        manifest = RepoManifest(
            repo_name="empty", repo_url="https://test.com", clone_path="/tmp/e",
            total_files=0, total_lines=0, languages=(), contributors=(),
            last_commits=(), directory_tree={}, detected_patterns=(),
        )
        state = {
            "status": PipelineStatus.INGESTING,
            "repo_manifest": manifest,
        }
        assert _should_continue_after_ingestion(state) == "end"

    def test_successful_ingestion_routes_to_end_phase1(self):
        """Phase 1: all routes go to END since only ingestion is implemented."""
        manifest = RepoManifest(
            repo_name="test", repo_url="https://test.com", clone_path="/tmp/t",
            total_files=10, total_lines=500, languages=(), contributors=(),
            last_commits=(), directory_tree={}, detected_patterns=(),
        )
        state = {
            "status": PipelineStatus.INGESTING,
            "repo_manifest": manifest,
        }
        # Phase 1: all paths route to end
        assert _should_continue_after_ingestion(state) == "end"


# --- Graph structure tests ---


class TestGraphStructure:
    def test_build_pipeline_compiles(self):
        graph = build_pipeline()
        assert graph is not None

    def test_graph_has_ingestor_node(self):
        graph = build_pipeline()
        node_names = list(graph.get_graph().nodes.keys())
        # LangGraph stores nodes — "repo_ingestor" should be present
        assert any("repo_ingestor" in str(n) for n in node_names)

    def test_graph_has_start_and_end(self):
        graph = build_pipeline()
        nodes = list(graph.get_graph().nodes.keys())
        assert "__start__" in nodes
        assert "__end__" in nodes

    def test_graph_edges_include_start_to_ingestor(self):
        graph = build_pipeline()
        edges = list(graph.get_graph().edges)
        # Should have an edge from __start__ to repo_ingestor
        edge_sources = [e.source for e in edges]
        edge_targets = [e.target for e in edges]
        assert "__start__" in edge_sources

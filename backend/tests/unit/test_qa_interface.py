"""Unit tests for QAInterfaceAgent."""

from __future__ import annotations

from graph.state import (
    AgentName,
    AgentStatus,
    GrimoireState,
    PipelineStatus,
)

from agents.qa_interface import qa_interface, should_continue_after_qa


# --- Helpers ---


def _make_state(**overrides: object) -> GrimoireState:
    state: GrimoireState = {
        "job_id": "test123",
        "github_url": "https://github.com/test/repo",
        "status": PipelineStatus.ANALYZING_DEBT,
        "current_agent": AgentName.QA_INTERFACE,
        "repo_manifest": None,
        "chunks": [],
        "total_chunks": 0,
        "architecture_report": None,
        "tech_debt_report": None,
        "qa_history": [],
        "agent_logs": [],
        "total_tokens_used": 0,
        "error_message": None,
        "started_at": 1000.0,
        "completed_at": None,
    }
    state.update(overrides)
    return state


# --- qa_interface ---


class TestQAInterface:
    def test_sets_qa_ready_status(self):
        result = qa_interface(_make_state())
        assert result["status"] == PipelineStatus.QA_READY

    def test_preserves_existing_state(self):
        state = _make_state(total_tokens_used=42)
        result = qa_interface(state)
        assert result["total_tokens_used"] == 42
        assert result["job_id"] == "test123"

    def test_adds_completed_agent_log(self):
        state = _make_state(agent_logs=[])
        result = qa_interface(state)
        assert len(result["agent_logs"]) == 1
        assert result["agent_logs"][0].agent == AgentName.QA_INTERFACE
        assert result["agent_logs"][0].status == AgentStatus.COMPLETED

    def test_initializes_qa_history_if_missing(self):
        state = _make_state()
        del state["qa_history"]
        result = qa_interface(state)
        assert result["qa_history"] == []

    def test_preserves_existing_qa_history(self):
        state = _make_state(qa_history=[{"question": "hello"}])  # type: ignore[dict-item]
        result = qa_interface(state)
        assert len(result["qa_history"]) == 1


# --- should_continue_after_qa ---


class TestShouldContinueAfterQA:
    def test_always_routes_to_end(self):
        state: GrimoireState = {"status": PipelineStatus.QA_READY}
        assert should_continue_after_qa(state) == "end"

    def test_routes_to_end_even_on_failure(self):
        state: GrimoireState = {"status": PipelineStatus.FAILED}
        assert should_continue_after_qa(state) == "end"

"""Unit tests for LangGraph State and dataclasses."""

from __future__ import annotations

from dataclasses import fields

import pytest

from graph.state import (
    AgentLog,
    AgentName,
    AgentStatus,
    ArchitectureReport,
    CodeChunk,
    Contributor,
    DependencyEdge,
    GrimoireState,
    LanguageStats,
    PipelineStatus,
    QAMessage,
    RepoManifest,
    TechDebtCategory,
    TechDebtReport,
)


# --- Enum tests ---


class TestEnums:
    def test_pipeline_status_values(self):
        statuses = list(PipelineStatus)
        assert PipelineStatus.IDLE in statuses
        assert PipelineStatus.FAILED in statuses
        assert PipelineStatus.COMPLETED in statuses
        assert len(statuses) == 8

    def test_agent_name_values(self):
        agents = list(AgentName)
        assert len(agents) == 5
        assert AgentName.REPO_INGESTOR in agents
        assert AgentName.QA_INTERFACE in agents

    def test_agent_status_values(self):
        statuses = list(AgentStatus)
        assert AgentStatus.PENDING in statuses
        assert AgentStatus.RUNNING in statuses
        assert AgentStatus.COMPLETED in statuses
        assert AgentStatus.FAILED in statuses
        assert AgentStatus.SKIPPED in statuses


# --- Dataclass tests ---


class TestLanguageStats:
    def test_creation(self):
        stats = LanguageStats(
            name="Python",
            file_count=10,
            total_lines=500,
            extensions=(".py",),
        )
        assert stats.name == "Python"
        assert stats.file_count == 10
        assert stats.total_lines == 500

    def test_immutability(self):
        stats = LanguageStats(name="Go", file_count=1, total_lines=50, extensions=(".go",))
        with pytest.raises(AttributeError):
            stats.file_count = 99


class TestContributor:
    def test_creation(self):
        c = Contributor(name="Alice", email="alice@test.com", commit_count=42)
        assert c.commit_count == 42

    def test_immutability(self):
        c = Contributor(name="Bob", email="bob@test.com", commit_count=1)
        with pytest.raises(AttributeError):
            c.name = "Eve"


class TestRepoManifest:
    def test_creation_with_all_fields(self):
        manifest = RepoManifest(
            repo_name="grimoire",
            repo_url="https://github.com/test/grimoire",
            clone_path="/tmp/grimoire",
            total_files=50,
            total_lines=5000,
            languages=(
                LanguageStats(name="Python", file_count=30, total_lines=3000, extensions=(".py",)),
                LanguageStats(name="JavaScript", file_count=20, total_lines=2000, extensions=(".js",)),
            ),
            contributors=(
                Contributor(name="Dev", email="dev@test.com", commit_count=10),
            ),
            last_commits=(),
            directory_tree={"src": {"main.py": None}},
            detected_patterns=("Layered",),
        )
        assert manifest.repo_name == "grimoire"
        assert len(manifest.languages) == 2
        assert manifest.total_files == 50

    def test_immutability(self):
        manifest = RepoManifest(
            repo_name="test", repo_url="https://test.com", clone_path="/tmp/t",
            total_files=1, total_lines=1, languages=(), contributors=(),
            last_commits=(), directory_tree={}, detected_patterns=(),
        )
        with pytest.raises(AttributeError):
            manifest.total_files = 99


class TestCodeChunk:
    def test_creation(self):
        chunk = CodeChunk(
            chunk_id="abc123",
            content="def hello():\n    pass",
            file_path="src/main.py",
            start_line=1,
            end_line=2,
            language="Python",
            node_type="function",
            name="hello",
            dependencies=("os", "sys"),
        )
        assert chunk.node_type == "function"
        assert len(chunk.dependencies) == 2

    def test_default_metadata(self):
        chunk = CodeChunk(
            chunk_id="x", content="x", file_path="f", start_line=1, end_line=1,
            language="py", node_type="fn", name="f", dependencies=(),
        )
        assert chunk.metadata == {}


class TestArchitectureReport:
    def test_creation(self):
        report = ArchitectureReport(
            dependency_graph={"main": ["utils", "config"]},
            entry_points=("main.py",),
            core_modules=("utils",),
            orphan_modules=("dead_code.py",),
            dependency_cycles=(),
            detected_pattern="Layered",
            mermaid_diagram="graph TD\n  A --> B",
            module_descriptions={"main": "Entry point"},
        )
        assert report.detected_pattern == "Layered"
        assert len(report.entry_points) == 1


class TestTechDebtReport:
    def test_creation(self):
        report = TechDebtReport(
            overall_score=45.5,
            categories=(
                TechDebtCategory(
                    name="Complexity",
                    score=60.0,
                    findings=({"file": "main.py", "function": "process"},),
                    severity="high",
                ),
            ),
            outdated_dependencies=(),
            todos_fixmes=(),
            summary_markdown="# Tech Debt Report\n\nScore: 45.5",
        )
        assert report.overall_score == 45.5
        assert len(report.categories) == 1


class TestQAMessage:
    def test_creation(self):
        msg = QAMessage(
            question="How does auth work?",
            answer="It uses JWT tokens...",
            sources=({"file": "auth.py", "lines": "10-25"},),
            timestamp=1700000000.0,
        )
        assert "JWT" in msg.answer


class TestAgentLog:
    def test_creation_minimal(self):
        log = AgentLog(agent=AgentName.REPO_INGESTOR, status=AgentStatus.RUNNING)
        assert log.tokens_used == 0
        assert log.error is None

    def test_creation_full(self):
        log = AgentLog(
            agent=AgentName.CODE_CHUNKER,
            status=AgentStatus.COMPLETED,
            started_at=1700000000.0,
            completed_at=1700000010.0,
            tokens_used=5000,
        )
        assert log.tokens_used == 5000


# --- State tests ---


class TestGrimoireState:
    def test_state_is_typed_dict(self):
        # GrimoireState should be a TypedDict
        assert hasattr(GrimoireState, "__annotations__")

    def test_all_expected_fields(self):
        expected_fields = {
            "job_id", "github_url", "status", "current_agent",
            "error_message", "repo_manifest", "chunks", "total_chunks",
            "architecture_report", "tech_debt_report", "qa_history",
            "agent_logs", "total_tokens_used", "started_at", "completed_at",
        }
        actual_fields = set(GrimoireState.__annotations__.keys())
        assert actual_fields == expected_fields

    def test_all_fields_optional(self):
        """All fields should be optional (total=False) for incremental building."""
        # TypedDict with total=False means all keys are optional
        state: GrimoireState = {}
        assert isinstance(state, dict)

    def test_state_with_all_fields(self):
        state: GrimoireState = {
            "job_id": "abc123",
            "github_url": "https://github.com/test/repo",
            "status": PipelineStatus.COMPLETED,
            "current_agent": AgentName.QA_INTERFACE,
            "error_message": None,
            "repo_manifest": None,
            "chunks": [],
            "total_chunks": 0,
            "architecture_report": None,
            "tech_debt_report": None,
            "qa_history": [],
            "agent_logs": [],
            "total_tokens_used": 0,
            "started_at": 1700000000.0,
            "completed_at": 1700000100.0,
        }
        assert state["job_id"] == "abc123"

"""Unit tests for TechDebtAnalyzerAgent."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from graph.state import (
    AgentName,
    AgentStatus,
    CodeChunk,
    GrimoireState,
    LanguageStats,
    PipelineStatus,
    RepoManifest,
    TechDebtReport,
)

from agents.tech_debt_analyzer import (
    _calculate_complexity_metrics,
    _calculate_todo_score,
    _determine_severity,
    _estimate_nesting_depth,
    _generate_summary,
    _scan_dependency_files,
    _scan_todos_fixmes,
    should_continue_after_debt_analysis,
    tech_debt_analyzer,
)


# --- Helpers ---


def _chunk(
    file_path: str = "main.py",
    content: str = "pass",
    name: str = "foo",
    node_type: str = "function",
    start_line: int = 1,
    end_line: int = 1,
    language: str = "Python",
) -> CodeChunk:
    return CodeChunk(
        chunk_id=f"test:{file_path}:{name}",
        content=content,
        file_path=file_path,
        start_line=start_line,
        end_line=end_line,
        language=language,
        node_type=node_type,
        name=name,
        dependencies=(),
    )


def _make_state(
    chunks: list[CodeChunk] | None = None,
    manifest: RepoManifest | None = None,
    **overrides: object,
) -> GrimoireState:
    state: GrimoireState = {
        "job_id": "test123",
        "github_url": "https://github.com/test/repo",
        "status": PipelineStatus.MAPPING,
        "current_agent": AgentName.TECH_DEBT_ANALYZER,
        "repo_manifest": manifest,
        "chunks": chunks or [],
        "total_chunks": len(chunks) if chunks else 0,
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


def _manifest() -> RepoManifest:
    return RepoManifest(
        repo_name="test-repo",
        repo_url="https://github.com/test/repo",
        clone_path="/tmp/test",
        total_files=5,
        total_lines=100,
        languages=(LanguageStats(name="Python", file_count=3, total_lines=60, extensions=(".py",)),),
        contributors=(),
        last_commits=(),
        directory_tree={},
        detected_patterns=("Layered",),
    )


# --- _scan_todos_fixmes ---


class TestScanTodosFixmes:
    def test_finds_python_todo(self):
        chunks = [_chunk(content="# TODO: refactor this\npass")]
        result = _scan_todos_fixmes(chunks)
        assert len(result) == 1
        assert result[0]["type"] == "TODO"

    def test_finds_js_fixme(self):
        chunks = [_chunk(content="// FIXME: broken\nlet x = 1")]
        result = _scan_todos_fixmes(chunks)
        assert len(result) == 1
        assert result[0]["type"] == "FIXME"

    def test_finds_hack_comment(self):
        chunks = [_chunk(content="# HACK: workaround\npass")]
        result = _scan_todos_fixmes(chunks)
        assert len(result) == 1
        assert result[0]["type"] == "HACK"

    def test_no_todos_returns_empty(self):
        chunks = [_chunk(content="def foo():\n    return 42")]
        assert _scan_todos_fixmes(chunks) == ()

    def test_multiple_todos_in_same_chunk(self):
        content = "# TODO: first\npass\n# FIXME: second"
        chunks = [_chunk(content=content)]
        result = _scan_todos_fixmes(chunks)
        assert len(result) == 2

    def test_case_insensitive(self):
        chunks = [_chunk(content="# todo: lowercase\npass")]
        result = _scan_todos_fixmes(chunks)
        assert len(result) == 1
        assert result[0]["type"] == "TODO"


# --- _estimate_nesting_depth ---


class TestEstimateNestingDepth:
    def test_flat_code_returns_0_or_1(self):
        depth = _estimate_nesting_depth("def foo():\n    pass\n")
        assert depth <= 1

    def test_nested_function_returns_2(self):
        content = "def foo():\n    def bar():\n        pass\n"
        depth = _estimate_nesting_depth(content)
        assert depth >= 2

    def test_deeply_nested_returns_appropriate_depth(self):
        content = "\n".join("    " * i + "pass" for i in range(8))
        depth = _estimate_nesting_depth(content)
        assert depth >= 2

    def test_empty_content_returns_0(self):
        assert _estimate_nesting_depth("") == 0


# --- _calculate_complexity_metrics ---


class TestCalculateComplexityMetrics:
    def test_small_file_low_score(self):
        chunks = [_chunk(end_line=10)]
        categories = _calculate_complexity_metrics(chunks)
        assert len(categories) == 2
        complexity_cat = categories[0]
        assert complexity_cat.name == "Complexity"
        assert complexity_cat.score < 50

    def test_large_file_high_score(self):
        chunks = [_chunk(end_line=600)]
        categories = _calculate_complexity_metrics(chunks)
        size_cat = categories[1]
        assert size_cat.name == "File Size"
        assert size_cat.score > 50

    def test_empty_chunks_returns_empty_categories(self):
        assert _calculate_complexity_metrics([]) == ()


# --- _scan_dependency_files ---


class TestScanDependencyFiles:
    def test_finds_requirements_txt(self):
        content = "django==1.3.0\nrequests==2.0.0\n"
        chunks = [_chunk(file_path="requirements.txt", content=content)]
        result = _scan_dependency_files(chunks)
        assert len(result) >= 1
        assert any(d["package"] == "django" for d in result)

    def test_ignores_non_dependency_files(self):
        chunks = [_chunk(file_path="main.py", content="import os")]
        assert _scan_dependency_files(chunks) == ()

    def test_no_old_pinned_versions(self):
        content = "django==4.2.0\nrequests==2.31.0\n"
        chunks = [_chunk(file_path="requirements.txt", content=content)]
        result = _scan_dependency_files(chunks)
        # These are not considered "old" by our heuristic
        assert all(d["package"] != "django" and d["package"] != "requests" for d in result)

    def test_no_dependency_files_returns_empty(self):
        assert _scan_dependency_files([]) == ()


# --- _calculate_todo_score ---


class TestCalculateTodoScore:
    def test_zero_todos_returns_0(self):
        assert _calculate_todo_score(0, 10) == 0.0

    def test_high_todo_ratio_returns_high_score(self):
        score = _calculate_todo_score(50, 10)
        assert score > 50

    def test_capped_at_100(self):
        score = _calculate_todo_score(1000, 1)
        assert score == 100.0


# --- _determine_severity ---


class TestDetermineSeverity:
    def test_critical_threshold(self):
        assert _determine_severity(80) == "critical"
        assert _determine_severity(75) == "critical"

    def test_high_threshold(self):
        assert _determine_severity(60) == "high"
        assert _determine_severity(50) == "high"

    def test_medium_threshold(self):
        assert _determine_severity(30) == "medium"
        assert _determine_severity(25) == "medium"

    def test_low_threshold(self):
        assert _determine_severity(10) == "low"
        assert _determine_severity(0) == "low"


# --- _generate_summary ---


class TestGenerateSummary:
    def test_contains_overall_score(self):
        summary = _generate_summary(42.0, (), (), (), None)
        assert "42.0" in summary

    def test_contains_category_names(self):
        from agents.tech_debt_analyzer import TechDebtCategory
        cat = TechDebtCategory(
            name="Complexity", score=30.0, findings=(), severity="medium"
        )
        summary = _generate_summary(30.0, (cat,), (), None)
        assert "Complexity" in summary

    def test_null_manifest_graceful(self):
        summary = _generate_summary(10.0, (), (), (), None)
        assert "Technical Debt Report" in summary


# --- tech_debt_analyzer (pipeline) ---


class TestTechDebtAnalyzerPipeline:
    def test_successful_analysis(self):
        chunks = [_chunk(content="# TODO: fix this\npass")]
        manifest = _manifest()
        state = _make_state(chunks=chunks, manifest=manifest)
        result = tech_debt_analyzer(state)

        assert result["status"] == PipelineStatus.ANALYZING_DEBT
        assert isinstance(result["tech_debt_report"], TechDebtReport)
        assert result["tech_debt_report"].overall_score >= 0
        assert len(result["tech_debt_report"].categories) == 3  # Complexity + File Size + TODOs
        assert len(result["agent_logs"]) == 1
        assert result["agent_logs"][0].status == AgentStatus.COMPLETED

    def test_no_chunks_fails(self):
        state = _make_state(chunks=[])
        result = tech_debt_analyzer(state)
        assert result["status"] == PipelineStatus.FAILED
        assert "no chunks" in result["error_message"]

    def test_exception_caught_and_reported(self):
        chunks = [_chunk()]
        state = _make_state(chunks=chunks)
        with patch(
            "agents.tech_debt_analyzer._scan_todos_fixmes",
            side_effect=RuntimeError("boom"),
        ):
            result = tech_debt_analyzer(state)
        assert result["status"] == PipelineStatus.FAILED
        assert "boom" in result["error_message"]

    def test_summary_markdown_is_populated(self):
        chunks = [_chunk()]
        manifest = _manifest()
        state = _make_state(chunks=chunks, manifest=manifest)
        result = tech_debt_analyzer(state)
        assert "Technical Debt Report" in result["tech_debt_report"].summary_markdown


# --- should_continue_after_debt_analysis ---


class TestShouldContinueAfterDebtAnalysis:
    def test_failed_routes_to_end(self):
        state: GrimoireState = {"status": PipelineStatus.FAILED, "tech_debt_report": None}
        assert should_continue_after_debt_analysis(state) == "end"

    def test_no_report_routes_to_end(self):
        state: GrimoireState = {"status": PipelineStatus.ANALYZING_DEBT, "tech_debt_report": None}
        assert should_continue_after_debt_analysis(state) == "end"

    def test_success_routes_to_qa_ready(self):
        report = TechDebtReport(
            overall_score=10.0,
            categories=(),
            outdated_dependencies=(),
            todos_fixmes=(),
            summary_markdown="",
        )
        state: GrimoireState = {
            "status": PipelineStatus.ANALYZING_DEBT,
            "tech_debt_report": report,
        }
        assert should_continue_after_debt_analysis(state) == "qa_ready"

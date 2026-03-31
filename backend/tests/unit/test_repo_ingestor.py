"""Unit tests for RepoIngestorAgent.

Tests cover: file skipping, language detection, contributor extraction,
directory tree building, and the full ingestion pipeline.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from textwrap import dedent
from unittest.mock import MagicMock, patch

import pytest

from agents.repo_ingestor import (
    _build_directory_tree,
    _build_language_stats,
    _detect_language,
    _detect_architectural_patterns,
    _extract_contributors,
    _extract_last_commits,
    _is_skipped_dir,
    _is_skipped_file,
    _walk_and_analyze,
    repo_ingestor,
)
from graph.state import (
    AgentName,
    AgentStatus,
    Contributor,
    LanguageStats,
    PipelineStatus,
    RepoManifest,
)


# --- File/directory filtering tests ---


class TestFileFiltering:
    def test_skip_common_dirs(self):
        for d in [".git", "__pycache__", "node_modules", ".venv", "dist", "build"]:
            assert _is_skipped_dir(d), f"{d} should be skipped"

    def test_do_not_skip_source_dirs(self):
        for d in ["src", "lib", "app", "backend", "frontend"]:
            assert not _is_skipped_dir(d), f"{d} should NOT be skipped"

    def test_skip_common_files(self):
        for f in [".DS_Store", "Thumbs.db", ".gitkeep"]:
            assert _is_skipped_file(f), f"{f} should be skipped"

    def test_skip_minified_files(self):
        assert _is_skipped_file("app.min.js")
        assert _is_skipped_file("styles.min.css")

    def test_do_not_skip_source_files(self):
        assert not _is_skipped_file("main.py")
        assert not _is_skipped_file("index.ts")
        assert not _is_skipped_file("app.go")

    def test_skip_lock_files(self):
        assert _is_skipped_file("package-lock.json")
        assert _is_skipped_file("yarn.lock")
        assert _is_skipped_file("pnpm-lock.yaml")


# --- Language detection tests ---


class TestLanguageDetection:
    def test_python(self):
        assert _detect_language(Path("main.py")) == "Python"

    def test_javascript(self):
        assert _detect_language(Path("index.js")) == "JavaScript"

    def test_jsx(self):
        assert _detect_language(Path("App.jsx")) == "JavaScript (JSX)"

    def test_typescript(self):
        assert _detect_language(Path("server.ts")) == "TypeScript"

    def test_tsx(self):
        assert _detect_language(Path("Button.tsx")) == "TypeScript (TSX)"

    def test_go(self):
        assert _detect_language(Path("main.go")) == "Go"

    def test_rust(self):
        assert _detect_language(Path("lib.rs")) == "Rust"

    def test_java(self):
        assert _detect_language(Path("App.java")) == "Java"

    def test_swift(self):
        assert _detect_language(Path("ViewController.swift")) == "Swift"

    def test_unknown_extension(self):
        assert _detect_language(Path("data.xyz")) is None

    def test_no_extension(self):
        assert _detect_language(Path("Makefile")) is None

    def test_case_insensitive(self):
        assert _detect_language(Path("APP.PY")) == "Python"

    def test_shebang_python(self, tmp_path):
        script = tmp_path / "script"
        script.write_text("#!/usr/bin/env python\nprint('hello')")
        assert _detect_language(script) == "Python"

    def test_shebang_bash(self, tmp_path):
        script = tmp_path / "script"
        script.write_text("#!/bin/bash\necho hello")
        assert _detect_language(script) == "Shell"


# --- Directory tree tests ---


class TestDirectoryTree:
    def test_empty_dir(self, tmp_path):
        tree = _build_directory_tree(tmp_path)
        assert tree == {}

    def test_nested_structure(self, tmp_path):
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "main.py").write_text("pass")
        (tmp_path / "src" / "utils").mkdir()
        (tmp_path / "src" / "utils" / "helpers.py").write_text("pass")
        (tmp_path / "README.md").write_text("# Test")

        tree = _build_directory_tree(tmp_path)
        assert "src" in tree
        assert "main.py" in tree["src"]
        assert "utils" in tree["src"]
        assert "helpers.py" in tree["src"]["utils"]
        assert "README.md" in tree

    def test_skips_hidden_dirs(self, tmp_path):
        (tmp_path / ".git").mkdir()
        (tmp_path / ".git" / "config").write_text("test")
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "main.py").write_text("pass")

        tree = _build_directory_tree(tmp_path)
        assert ".git" not in tree
        assert "src" in tree

    def test_max_depth_limits_recursion(self, tmp_path):
        (tmp_path / "a").mkdir()
        (tmp_path / "a" / "b").mkdir()
        (tmp_path / "a" / "b" / "c").mkdir()
        (tmp_path / "a" / "b" / "file.py").write_text("pass")

        tree = _build_directory_tree(tmp_path, max_depth=3)
        assert "a" in tree
        assert "b" in tree["a"]
        assert "file.py" in tree["a"]["b"]
        # max_depth=3: root(3)→a(2)→b(1)→c skipped (depth=1 not > 1)
        assert "c" not in tree["a"]["b"]

    def test_skips_node_modules(self, tmp_path):
        (tmp_path / "node_modules").mkdir()
        (tmp_path / "node_modules" / "lodash").mkdir()
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "app.js").write_text("const x = 1;")

        tree = _build_directory_tree(tmp_path)
        assert "node_modules" not in tree
        assert "src" in tree


# --- Walk and analyze tests ---


class TestWalkAndAnalyze:
    def test_empty_repo(self, tmp_path):
        files, lines, total_files, total_lines = _walk_and_analyze(tmp_path)
        assert total_files == 0
        assert total_lines == 0

    def test_counts_correctly(self, tmp_path):
        (tmp_path / "main.py").write_text("a\nb\nc")
        (tmp_path / "utils.py").write_text("x\ny")
        (tmp_path / "README.md").write_text("# Hello")

        files, lines, total_files, total_lines = _walk_and_analyze(tmp_path)
        # README.md is also counted since .md maps to Markdown
        assert total_files >= 2  # at least the .py files
        assert total_lines >= 5

    def test_skips_git_dir(self, tmp_path):
        (tmp_path / ".git").mkdir()
        (tmp_path / ".git" / "config").write_text("test")
        (tmp_path / "main.py").write_text("pass")

        files, lines, total_files, total_lines = _walk_and_analyze(tmp_path)
        assert total_files == 1

    def test_skips_node_modules(self, tmp_path):
        (tmp_path / "node_modules").mkdir()
        (tmp_path / "node_modules" / "pkg").mkdir()
        (tmp_path / "node_modules" / "pkg" / "index.js").write_text("module.exports = {}")
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "app.js").write_text("const x = 1;")

        files, lines, total_files, total_lines = _walk_and_analyze(tmp_path)
        assert total_files == 1


# --- Language stats tests ---


class TestLanguageStats:
    def test_single_language(self):
        from collections import Counter
        files = Counter({"Python": 3})
        lines = Counter({"Python": 150})
        stats = _build_language_stats(files, lines)
        assert len(stats) == 1
        assert stats[0].name == "Python"
        assert stats[0].file_count == 3
        assert stats[0].total_lines == 150

    def test_sorted_by_lines(self):
        from collections import Counter
        files = Counter({"Python": 5, "Go": 3})
        lines = Counter({"Python": 100, "Go": 200})
        stats = _build_language_stats(files, lines)
        assert stats[0].name == "Go"
        assert stats[0].total_lines == 200

    def test_empty(self):
        from collections import Counter
        stats = _build_language_stats(Counter(), Counter())
        assert stats == ()

    def test_extensions_included(self):
        from collections import Counter
        files = Counter({"Python": 2})
        lines = Counter({"Python": 50})
        stats = _build_language_stats(files, lines)
        assert ".py" in stats[0].extensions


# --- Contributor extraction tests ---


class TestContributorExtraction:
    def test_extracts_contributors(self):
        mock_repo = MagicMock()
        mock_commit_1 = MagicMock()
        mock_commit_1.author.name = "Alice"
        mock_commit_1.author.email = "alice@example.com"
        mock_commit_2 = MagicMock()
        mock_commit_2.author.name = "Bob"
        mock_commit_2.author.email = "bob@example.com"
        mock_commit_3 = MagicMock()
        mock_commit_3.author.name = "Alice"
        mock_commit_3.author.email = "alice@example.com"

        mock_repo.iter_commits.return_value = [
            mock_commit_1, mock_commit_2, mock_commit_3
        ]

        contributors = _extract_contributors(mock_repo)
        assert len(contributors) == 2
        # Alice has more commits, should be first
        assert contributors[0].name == "Alice"
        assert contributors[0].commit_count == 2
        assert contributors[1].name == "Bob"
        assert contributors[1].commit_count == 1

    def test_respects_limit(self):
        mock_repo = MagicMock()
        commits = []
        for i in range(30):
            c = MagicMock()
            c.author.name = f"User{i}"
            c.author.email = f"user{i}@example.com"
            commits.append(c)

        mock_repo.iter_commits.return_value = commits
        contributors = _extract_contributors(mock_repo, limit=10)
        assert len(contributors) == 10

    def test_empty_repo(self):
        mock_repo = MagicMock()
        mock_repo.iter_commits.return_value = []
        contributors = _extract_contributors(mock_repo)
        assert contributors == ()


# --- Last commits tests ---


class TestLastCommits:
    def test_extracts_commits(self):
        mock_repo = MagicMock()
        mock_commit = MagicMock()
        mock_commit.hexsha = "abcdef1234567890"
        mock_commit.message = "feat: add auth\n\nDetailed description"
        mock_commit.author.name = "Alice"
        mock_commit.committed_date = 1700000000.0

        mock_repo.iter_commits.return_value = [mock_commit]
        commits = _extract_last_commits(mock_repo)

        assert len(commits) == 1
        assert commits[0]["hash"] == "abcdef12"
        assert commits[0]["message"] == "feat: add auth"
        assert commits[0]["author"] == "Alice"

    def test_empty_repo(self):
        mock_repo = MagicMock()
        mock_repo.iter_commits.return_value = []
        commits = _extract_last_commits(mock_repo)
        assert commits == ()


# --- Architectural pattern detection tests ---


class TestPatternDetection:
    def test_mvc_pattern(self, tmp_path):
        for d in ["models", "views", "controllers"]:
            (tmp_path / d).mkdir()
        patterns = _detect_architectural_patterns(tmp_path)
        assert "MVC" in patterns

    def test_layered_pattern(self, tmp_path):
        for d in ["routes", "services", "models"]:
            (tmp_path / d).mkdir()
        patterns = _detect_architectural_patterns(tmp_path)
        assert "Layered" in patterns

    def test_hexagonal_pattern(self, tmp_path):
        for d in ["domain", "infrastructure", "application"]:
            (tmp_path / d).mkdir()
        patterns = _detect_architectural_patterns(tmp_path)
        assert "Hexagonal" in patterns

    def test_microservices_pattern(self, tmp_path):
        for d in ["auth-service", "user-service", "payment-service"]:
            (tmp_path / d).mkdir()
        patterns = _detect_architectural_patterns(tmp_path)
        assert "Microservices-like" in patterns

    def test_monolith_fallback(self, tmp_path):
        (tmp_path / "random_dir").mkdir()
        patterns = _detect_architectural_patterns(tmp_path)
        assert "Monolith" in patterns

    def test_django_detection(self, tmp_path):
        (tmp_path / "manage.py").write_text("# Django")
        (tmp_path / "settings").mkdir()
        patterns = _detect_architectural_patterns(tmp_path)
        assert "Django" in patterns

    def test_nextjs_detection(self, tmp_path):
        (tmp_path / "next.config.mjs").write_text("// Next.js")
        patterns = _detect_architectural_patterns(tmp_path)
        # next.config.mjs starts with "next.config" so it matches
        assert "Next.js" in patterns


# --- Full pipeline tests ---


class TestRepoIngestorPipeline:
    @patch("agents.repo_ingestor._walk_and_analyze")
    @patch("agents.repo_ingestor._extract_last_commits")
    @patch("agents.repo_ingestor._extract_contributors")
    @patch("agents.repo_ingestor._build_directory_tree")
    @patch("agents.repo_ingestor._detect_architectural_patterns")
    @patch("agents.repo_ingestor.Repo.clone_from")
    def test_successful_ingestion(
        self, mock_clone, mock_patterns, mock_tree, mock_contributors,
        mock_commits, mock_walk,
    ):
        """Test full ingestion with mocked internals."""
        from collections import Counter

        mock_patterns.return_value = ("Layered",)
        mock_tree.return_value = {"src": {"main.py": None}}
        mock_contributors.return_value = (
            Contributor(name="Dev", email="dev@test.com", commit_count=5),
        )
        mock_commits.return_value = ()
        mock_walk.return_value = (Counter({"Python": 2}), Counter({"Python": 100}), 2, 100)

        state = {
            "job_id": "test123",
            "github_url": "https://github.com/test/repo.git",
            "status": PipelineStatus.IDLE,
            "current_agent": AgentName.REPO_INGESTOR,
            "agent_logs": [],
        }

        with patch("agents.repo_ingestor.Path") as mock_path_cls:
            mock_clone_dir = MagicMock()
            mock_clone_dir.exists.return_value = False
            mock_clone_dir.parent = MagicMock()
            mock_path_cls.return_value = mock_clone_dir
            mock_path_cls.return_value.__str__ = lambda self: "./data/repos/test123"

            # Mock Repo() for opening after clone
            with patch("agents.repo_ingestor.Repo") as mock_repo_cls:
                mock_repo = MagicMock()
                mock_repo_cls.clone_from.return_value = None
                mock_repo_cls.return_value = mock_repo

                result = repo_ingestor(state)

        assert result["status"] != PipelineStatus.FAILED
        assert result["repo_manifest"] is not None
        manifest = result["repo_manifest"]
        assert isinstance(manifest, RepoManifest)
        assert manifest.repo_name == "repo"
        assert manifest.total_files == 2
        assert len(manifest.languages) >= 1
        assert len(result["agent_logs"]) == 1
        assert result["agent_logs"][0].status == AgentStatus.COMPLETED

    def test_invalid_url_fails(self):
        """Test that an invalid URL produces a FAILED status."""
        state = {
            "job_id": "fail123",
            "github_url": "not-a-valid-url",
            "status": PipelineStatus.IDLE,
            "current_agent": AgentName.REPO_INGESTOR,
            "agent_logs": [],
        }

        result = repo_ingestor(state)
        assert result["status"] == PipelineStatus.FAILED
        assert result["error_message"] is not None
        assert "RepoIngestorAgent failed" in result["error_message"]

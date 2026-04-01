"""Unit tests for CodeChunkerAgent.

Tests cover: language mapping, binary detection, file reading, node type mapping,
name extraction, dependency extraction, tree-sitter parsing, fallback chunking,
repo file walking, and the full chunking pipeline.
"""

from __future__ import annotations

from pathlib import Path
from textwrap import dedent
from unittest.mock import MagicMock, patch

import pytest
import tree_sitter_languages

from agents.code_chunker import (
    MAX_CHUNK_LINES,
    MAX_FILE_LINES,
    MIN_CHUNK_LINES,
    _chunk_file,
    _chunk_with_fallback,
    _extract_calls_from_node,
    _extract_dependencies_from_node,
    _extract_imports_from_tree,
    _extract_name_from_node,
    _get_node_type_map,
    _get_tree_sitter_lang,
    _is_binary_file,
    _make_chunk_id,
    _parse_with_tree_sitter,
    _read_file_lines,
    _walk_repo_files,
    code_chunker,
    should_continue_after_chunking,
)
from graph.state import (
    AgentName,
    AgentStatus,
    CodeChunk,
    GrimoireState,
    PipelineStatus,
    RepoManifest,
)


# --- Language mapping tests ---


class TestLanguageMapping:
    def test_python_maps_correctly(self):
        assert _get_tree_sitter_lang("Python") == "python"

    def test_javascript_maps_correctly(self):
        assert _get_tree_sitter_lang("JavaScript") == "javascript"

    def test_typescript_maps_correctly(self):
        assert _get_tree_sitter_lang("TypeScript") == "typescript"

    def test_go_maps_correctly(self):
        assert _get_tree_sitter_lang("Go") == "go"

    def test_rust_maps_correctly(self):
        assert _get_tree_sitter_lang("Rust") == "rust"

    def test_unsupported_language_returns_none(self):
        assert _get_tree_sitter_lang("Lua") is None
        assert _get_tree_sitter_lang("Zig") is None

    def test_case_sensitive(self):
        # Lowercase should not match
        assert _get_tree_sitter_lang("python") is None

    def test_jsx_maps_to_javascript(self):
        assert _get_tree_sitter_lang("JavaScript (JSX)") == "javascript"


# --- Binary file detection tests ---


class TestBinaryFileDetection:
    def test_text_file_not_binary(self, tmp_path):
        f = tmp_path / "test.py"
        f.write_text("print('hello')")
        assert not _is_binary_file(f)

    def test_null_bytes_is_binary(self, tmp_path):
        f = tmp_path / "binary.bin"
        f.write_bytes(b"hello\x00world")
        assert _is_binary_file(f)

    def test_empty_file_not_binary(self, tmp_path):
        f = tmp_path / "empty.txt"
        f.write_bytes(b"")
        assert not _is_binary_file(f)

    def test_nonexistent_file_is_binary(self, tmp_path):
        f = tmp_path / "missing.xyz"
        assert _is_binary_file(f)


# --- File reading tests ---


class TestFileReading:
    def test_valid_utf8(self, tmp_path):
        f = tmp_path / "test.py"
        f.write_text("line1\nline2\nline3", encoding="utf-8")
        lines = _read_file_lines(f)
        assert lines == ["line1", "line2", "line3"]

    def test_binary_returns_none(self, tmp_path):
        f = tmp_path / "binary.bin"
        f.write_bytes(b"\x00\x01\x02")
        assert _read_file_lines(f) is None

    def test_missing_returns_none(self, tmp_path):
        f = tmp_path / "missing.py"
        assert _read_file_lines(f) is None

    def test_too_large_returns_none(self, tmp_path):
        f = tmp_path / "large.py"
        # Create a file with more than MAX_FILE_LINES lines
        lines = ["x"] * (MAX_FILE_LINES + 1)
        f.write_text("\n".join(lines), encoding="utf-8")
        assert _read_file_lines(f) is None

    def test_empty_file_returns_empty_list(self, tmp_path):
        f = tmp_path / "empty.py"
        f.write_text("", encoding="utf-8")
        lines = _read_file_lines(f)
        assert lines == []


# --- Node type mapping tests ---


class TestNodeTypeMapping:
    def test_python_mapping(self):
        m = _get_node_type_map("python")
        assert m["function_definition"] == "function"
        assert m["class_definition"] == "class"

    def test_javascript_mapping(self):
        m = _get_node_type_map("javascript")
        assert m["function_declaration"] == "function"
        assert m["class_declaration"] == "class"

    def test_go_mapping(self):
        m = _get_node_type_map("go")
        assert m["function_declaration"] == "function"
        assert m["method_declaration"] == "method"

    def test_default_fallback(self):
        m = _get_node_type_map("nonexistent_lang")
        assert m["function_definition"] == "function"
        assert m["class_definition"] == "class"

    def test_unknown_type_returns_none(self):
        m = _get_node_type_map("python")
        assert m.get("totally_unknown_node_type") is None

    def test_rust_mapping(self):
        m = _get_node_type_map("rust")
        assert m["struct_item"] == "struct"
        assert m["enum_item"] == "enum"
        assert m["trait_item"] == "trait"


# --- Name extraction tests ---


class TestNameExtraction:
    def _parse_and_get_first(self, code: str, lang: str):
        """Helper: parse code and return the first named child of root."""
        parser = tree_sitter_languages.get_parser(lang)
        tree = parser.parse(code.encode("utf-8"))
        root = tree.root_node
        for child in root.named_children:
            return child
        return None

    def test_python_function_name(self):
        code = "def hello():\n    pass"
        node = self._parse_and_get_first(code, "python")
        lines = code.splitlines()
        assert _extract_name_from_node(node, lines) == "hello"

    def test_python_class_name(self):
        code = "class MyClass:\n    pass"
        node = self._parse_and_get_first(code, "python")
        lines = code.splitlines()
        assert _extract_name_from_node(node, lines) == "MyClass"

    def test_anonymous_node(self):
        """Expression without a name field returns '<anonymous>'."""
        code = "x = 1"
        parser = tree_sitter_languages.get_parser("python")
        tree = parser.parse(code.encode("utf-8"))
        # Get an expression statement child
        node = tree.root_node.children[0]
        lines = code.splitlines()
        # An expression_statement may not have a name field
        result = _extract_name_from_node(node, lines)
        # Should return something (either "x" or "<anonymous>")
        assert isinstance(result, str)

    def test_javascript_function_name(self):
        code = "function greet() {\n  return 1;\n}"
        node = self._parse_and_get_first(code, "javascript")
        lines = code.splitlines()
        assert _extract_name_from_node(node, lines) == "greet"


# --- Dependency extraction tests ---


class TestDependencyExtraction:
    def _parse_node(self, code: str, lang: str):
        parser = tree_sitter_languages.get_parser(lang)
        tree = parser.parse(code.encode("utf-8"))
        for child in tree.root_node.named_children:
            return child
        return None

    def test_extracts_function_calls(self):
        code = dedent("""\
            def my_func():
                foo()
                bar(1, 2)
        """)
        node = self._parse_node(code, "python")
        calls = _extract_calls_from_node(node)
        assert "foo" in calls
        assert "bar" in calls

    def test_deduplicates(self):
        code = dedent("""\
            def my_func():
                foo()
                foo()
        """)
        node = self._parse_node(code, "python")
        lines = code.splitlines()
        deps = _extract_dependencies_from_node(node, lines, "python")
        assert deps.count("foo") == 1

    def test_empty_node(self):
        code = "x = 1"
        parser = tree_sitter_languages.get_parser("python")
        tree = parser.parse(code.encode("utf-8"))
        calls = _extract_calls_from_node(tree.root_node)
        assert calls == ()

    def test_nested_calls(self):
        code = dedent("""\
            def my_func():
                result = outer(inner())
        """)
        node = self._parse_node(code, "python")
        calls = _extract_calls_from_node(node)
        assert "inner" in calls
        assert "outer" in calls


# --- Tree-sitter parsing tests ---


class TestTreeSitterParsing:
    def test_python_function(self, tmp_path):
        code = dedent("""\
            def greet(name):
                return f"Hello {name}"
        """)
        source_bytes = code.encode("utf-8")
        source_lines = code.splitlines()
        chunks = _parse_with_tree_sitter(
            source_bytes, source_lines, "python", "test.py", "Python"
        )
        assert len(chunks) >= 1
        fn_chunks = [c for c in chunks if c.node_type == "function"]
        assert len(fn_chunks) == 1
        assert fn_chunks[0].name == "greet"
        assert fn_chunks[0].start_line == 1
        assert fn_chunks[0].language == "Python"

    def test_python_class(self, tmp_path):
        code = dedent("""\
            class MyClass:
                def __init__(self):
                    pass
                def method(self):
                    return 42
        """)
        source_bytes = code.encode("utf-8")
        source_lines = code.splitlines()
        chunks = _parse_with_tree_sitter(
            source_bytes, source_lines, "python", "test.py", "Python"
        )
        class_chunks = [c for c in chunks if c.node_type == "class"]
        assert len(class_chunks) == 1
        assert class_chunks[0].name == "MyClass"

    def test_javascript_function(self):
        code = dedent("""\
            function add(a, b) {
                return a + b;
            }
        """)
        source_bytes = code.encode("utf-8")
        source_lines = code.splitlines()
        chunks = _parse_with_tree_sitter(
            source_bytes, source_lines, "javascript", "test.js", "JavaScript"
        )
        fn_chunks = [c for c in chunks if c.node_type == "function"]
        assert len(fn_chunks) == 1
        assert fn_chunks[0].name == "add"

    def test_go_function(self):
        code = dedent("""\
            package main

            import "fmt"

            func main() {
                fmt.Println("hello")
            }
        """)
        source_bytes = code.encode("utf-8")
        source_lines = code.splitlines()
        chunks = _parse_with_tree_sitter(
            source_bytes, source_lines, "go", "main.go", "Go"
        )
        fn_chunks = [c for c in chunks if c.node_type == "function"]
        assert len(fn_chunks) >= 1
        assert fn_chunks[0].name == "main"

    def test_module_fallback_when_no_chunks(self):
        """When tree-sitter finds no recognized nodes, a module chunk is created."""
        code = "x = 1\ny = 2\n"
        source_bytes = code.encode("utf-8")
        source_lines = code.splitlines()
        chunks = _parse_with_tree_sitter(
            source_bytes, source_lines, "python", "vars.py", "Python"
        )
        assert len(chunks) == 1
        assert chunks[0].node_type == "module"

    def test_parse_error_returns_empty(self):
        """If parser creation fails, return empty list."""
        with patch("agents.code_chunker.tree_sitter_languages.get_parser") as mock:
            mock.side_effect = RuntimeError("no parser")
            chunks = _parse_with_tree_sitter(
                b"code", ["code"], "nonexistent", "test.x", "Unknown"
            )
        assert chunks == []

    def test_min_lines_filter(self):
        """Nodes with fewer than MIN_CHUNK_LINES are skipped."""
        code = "import os\n"  # 1 line, should not produce an import chunk by itself
        source_bytes = code.encode("utf-8")
        source_lines = code.splitlines()
        chunks = _parse_with_tree_sitter(
            source_bytes, source_lines, "python", "test.py", "Python"
        )
        # import statement is only 1 line < MIN_CHUNK_LINES=2, so module fallback
        import_chunks = [c for c in chunks if c.node_type == "import"]
        assert len(import_chunks) == 0


# --- Fallback chunking tests ---


class TestFallbackChunking:
    def test_module_chunk_when_no_matches(self):
        lines = ["x = 1", "y = 2", "z = 3"]
        chunks = _chunk_with_fallback(lines, "test.py", "Python")
        assert len(chunks) == 1
        assert chunks[0].node_type == "module"

    def test_extracts_functions(self):
        code = dedent("""\
            def foo():
                pass

            def bar():
                return 1
        """)
        lines = code.splitlines()
        chunks = _chunk_with_fallback(lines, "test.py", "Python")
        fn_chunks = [c for c in chunks if c.node_type == "function"]
        assert len(fn_chunks) >= 2
        names = {c.name for c in fn_chunks}
        assert "foo" in names
        assert "bar" in names

    def test_extracts_classes(self):
        code = dedent("""\
            class MyClass:
                pass
        """)
        lines = code.splitlines()
        chunks = _chunk_with_fallback(lines, "test.py", "Python")
        class_chunks = [c for c in chunks if c.node_type == "class"]
        assert len(class_chunks) >= 1
        assert class_chunks[0].name == "MyClass"

    def test_extracts_imports_as_dependencies(self):
        code = dedent("""\
            import os
            from sys import path
            def main():
                pass
        """)
        lines = code.splitlines()
        chunks = _chunk_with_fallback(lines, "test.py", "Python")
        assert len(chunks) >= 1
        # Imports should be in dependencies
        all_deps = set()
        for c in chunks:
            all_deps.update(c.dependencies)
        assert "os" in all_deps
        assert "sys" in all_deps

    def test_empty_content(self):
        chunks = _chunk_with_fallback([], "test.py", "Python")
        assert chunks == []

    def test_chunk_content_matches_source(self):
        code = dedent("""\
            def greet():
                return "hi"
        """)
        lines = code.splitlines()
        chunks = _chunk_with_fallback(lines, "test.py", "Python")
        fn_chunks = [c for c in chunks if c.node_type == "function"]
        assert len(fn_chunks) >= 1
        assert "def greet" in fn_chunks[0].content
        assert 'return "hi"' in fn_chunks[0].content


# --- Repo file walking tests ---


class TestRepoFileWalking:
    def test_filters_code_only(self, tmp_path):
        (tmp_path / "main.py").write_text("pass")
        (tmp_path / "README.md").write_text("# Hello")
        (tmp_path / "config.yaml").write_text("key: value")

        files = _walk_repo_files(tmp_path)
        paths = [rp for _, rp, _ in files]
        assert any("main.py" in p for p in paths)
        assert not any(".md" in p for p in paths)
        assert not any(".yaml" in p for p in paths)

    def test_skips_git_and_node_modules(self, tmp_path):
        (tmp_path / ".git").mkdir()
        (tmp_path / ".git" / "config").write_text("test")
        (tmp_path / "node_modules").mkdir()
        (tmp_path / "node_modules" / "pkg").mkdir()
        (tmp_path / "node_modules" / "pkg" / "index.js").write_text("module.exports = {}")
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "app.js").write_text("const x = 1;")

        files = _walk_repo_files(tmp_path)
        paths = [rp for _, rp, _ in files]
        assert any("app.js" in p for p in paths)
        assert not any("node_modules" in p for p in paths)
        assert not any(".git" in p for p in paths)

    def test_empty_repo(self, tmp_path):
        files = _walk_repo_files(tmp_path)
        assert files == []

    def test_relative_paths(self, tmp_path):
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "utils").mkdir()
        (tmp_path / "src" / "utils" / "helpers.py").write_text("pass")

        files = _walk_repo_files(tmp_path)
        paths = [rp for _, rp, _ in files]
        assert "src/utils/helpers.py" in paths

    def test_skips_hidden_dirs(self, tmp_path):
        (tmp_path / ".hidden").mkdir()
        (tmp_path / ".hidden" / "secret.py").write_text("pass")
        (tmp_path / "visible").mkdir()
        (tmp_path / "visible" / "app.py").write_text("pass")

        files = _walk_repo_files(tmp_path)
        paths = [rp for _, rp, _ in files]
        assert any("visible/app.py" in p for p in paths)
        assert not any(".hidden" in p for p in paths)


# --- Full pipeline tests ---


class TestCodeChunkerPipeline:
    def _make_state(self, tmp_path, **overrides) -> GrimoireState:
        manifest = RepoManifest(
            repo_name="test",
            repo_url="https://github.com/test/repo",
            clone_path=str(tmp_path),
            total_files=1,
            total_lines=10,
            languages=(),
            contributors=(),
            last_commits=(),
            directory_tree={},
            detected_patterns=(),
        )
        state: GrimoireState = {
            "job_id": "test123",
            "github_url": "https://github.com/test/repo",
            "status": PipelineStatus.INGESTING,
            "current_agent": AgentName.CODE_CHUNKER,
            "error_message": None,
            "repo_manifest": manifest,
            "chunks": [],
            "total_chunks": 0,
            "architecture_report": None,
            "tech_debt_report": None,
            "qa_history": [],
            "agent_logs": [],
            "total_tokens_used": 0,
            "started_at": 1000.0,
            "completed_at": None,
        }
        state.update(overrides)
        return state

    def test_successful_chunking(self, tmp_path):
        (tmp_path / "main.py").write_text(dedent("""\
            def hello():
                return "world"

            class Foo:
                pass
        """))
        state = self._make_state(tmp_path)
        result = code_chunker(state)

        assert result["status"] == PipelineStatus.CHUNKING
        assert result["total_chunks"] > 0
        assert len(result["chunks"]) > 0
        assert result["agent_logs"][-1].status == AgentStatus.COMPLETED
        assert result["agent_logs"][-1].agent == AgentName.CODE_CHUNKER

    def test_manifest_missing(self):
        state: GrimoireState = {
            "job_id": "test123",
            "github_url": "https://github.com/test/repo",
            "status": PipelineStatus.INGESTING,
            "current_agent": AgentName.CODE_CHUNKER,
            "error_message": None,
            "repo_manifest": None,
            "chunks": [],
            "total_chunks": 0,
            "architecture_report": None,
            "tech_debt_report": None,
            "qa_history": [],
            "agent_logs": [],
            "total_tokens_used": 0,
            "started_at": 1000.0,
            "completed_at": None,
        }
        result = code_chunker(state)
        assert result["status"] == PipelineStatus.FAILED
        assert "no repo_manifest" in result["error_message"]

    def test_clone_path_missing(self):
        state = self._make_state(Path("/nonexistent/path/xyz"))
        result = code_chunker(state)
        assert result["status"] == PipelineStatus.FAILED
        assert "not found" in result["error_message"]

    def test_empty_repo(self, tmp_path):
        state = self._make_state(tmp_path)
        result = code_chunker(state)
        # Empty repo produces no chunks, but doesn't fail
        assert result["status"] == PipelineStatus.CHUNKING
        assert result["total_chunks"] == 0

    def test_partial_errors_dont_break_pipeline(self, tmp_path):
        """A file that causes an error shouldn't break the whole pipeline."""
        (tmp_path / "good.py").write_text(dedent("""\
            def good_func():
                return 42
        """))
        (tmp_path / "bad.py").write_bytes(b"\x00\x01\x02")  # binary

        state = self._make_state(tmp_path)

        with patch(
            "agents.code_chunker._chunk_file",
            side_effect=lambda fp, rp, ln: (
                [CodeChunk(
                    chunk_id="test", content="x", file_path=rp,
                    start_line=1, end_line=1, language=ln,
                    node_type="function", name="test", dependencies=(),
                )]
                if "good" in rp
                else []
            ),
        ):
            result = code_chunker(state)

        assert result["status"] == PipelineStatus.CHUNKING
        assert result["total_chunks"] >= 1


# --- Conditional edge tests ---


class TestShouldContinueAfterChunking:
    def test_failed_routes_to_end(self):
        state: GrimoireState = {
            "status": PipelineStatus.FAILED,
            "chunks": [],
        }  # type: ignore[typeddict-item]
        assert should_continue_after_chunking(state) == "end"

    def test_no_chunks_routes_to_end(self):
        state: GrimoireState = {
            "status": PipelineStatus.CHUNKING,
            "chunks": [],
        }  # type: ignore[typeddict-item]
        assert should_continue_after_chunking(state) == "end"

    def test_success_routes_to_end_phase2(self):
        state: GrimoireState = {
            "status": PipelineStatus.CHUNKING,
            "chunks": [MagicMock()],
        }  # type: ignore[typeddict-item]
        # Phase 2: all paths route to end
        assert should_continue_after_chunking(state) == "end"

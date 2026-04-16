"""Unit tests for ArchitectureMapperAgent."""

from __future__ import annotations

from textwrap import dedent
from unittest.mock import patch

import pytest

from graph.state import (
    AgentName,
    AgentStatus,
    ArchitectureReport,
    CodeChunk,
    GrimoireState,
    LanguageStats,
    PipelineStatus,
    RepoManifest,
)

from agents.architecture_mapper import (
    _build_dependency_graph,
    _detect_cycles,
    _detect_entry_points,
    _determine_pattern,
    _find_core_modules,
    _find_orphan_modules,
    _generate_mermaid,
    _generate_module_descriptions,
    _normalize_dependency_name,
    _normalize_module_path,
    architecture_mapper,
    should_continue_after_mapping,
)


# --- Helpers ---


def _chunk(
    file_path: str,
    name: str = "foo",
    node_type: str = "function",
    dependencies: tuple[str, ...] = (),
    language: str = "Python",
) -> CodeChunk:
    return CodeChunk(
        chunk_id=f"test:{file_path}:{name}",
        content="pass",
        file_path=file_path,
        start_line=1,
        end_line=1,
        language=language,
        node_type=node_type,
        name=name,
        dependencies=dependencies,
    )


def _make_state(
    chunks: list[CodeChunk] | None = None,
    manifest: RepoManifest | None = None,
    **overrides: object,
) -> GrimoireState:
    state: GrimoireState = {
        "job_id": "test123",
        "github_url": "https://github.com/test/repo",
        "status": PipelineStatus.CHUNKING,
        "current_agent": AgentName.ARCHITECTURE_MAPPER,
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


def _manifest(
    languages: tuple[str, ...] = ("Python",),
    patterns: tuple[str, ...] = ("Layered",),
) -> RepoManifest:
    return RepoManifest(
        repo_name="test-repo",
        repo_url="https://github.com/test/repo",
        clone_path="/tmp/test",
        total_files=5,
        total_lines=100,
        languages=tuple(LanguageStats(name=l, file_count=1, total_lines=20, extensions=(".py",)) for l in languages),
        contributors=(),
        last_commits=(),
        directory_tree={},
        detected_patterns=patterns,
    )


# --- _normalize_module_path ---


class TestNormalizeModulePath:
    def test_strips_leading_dot_slash(self):
        assert _normalize_module_path("./src/main.py") == "src/main"

    def test_replaces_backslashes(self):
        assert _normalize_module_path("src\\utils\\helpers.py") == "src/utils/helpers"

    def test_strips_extension(self):
        assert _normalize_module_path("app.js") == "app"

    def test_preserves_nested_path(self):
        assert _normalize_module_path("a/b/c/d.py") == "a/b/c/d"

    def test_no_extension(self):
        assert _normalize_module_path("Makefile") == "Makefile"


# --- _normalize_dependency_name ---


class TestNormalizeDependencyName:
    def test_exact_basename_match(self):
        modules = {"src/utils/helpers", "src/main"}
        assert _normalize_dependency_name("helpers", modules) == "src/utils/helpers"

    def test_dotted_name_basename_match(self):
        modules = {"src/utils/helpers", "src/main"}
        assert _normalize_dependency_name("utils.helpers", modules) == "src/utils/helpers"

    def test_no_match_returns_none(self):
        modules = {"src/main"}
        assert _normalize_dependency_name("os", modules) is None

    def test_empty_dep_returns_none(self):
        assert _normalize_dependency_name("", {"src/main"}) is None


# --- _build_dependency_graph ---


class TestBuildDependencyGraph:
    def test_empty_chunks_produce_empty_graph(self):
        g = _build_dependency_graph([])
        assert len(g.nodes) == 0
        assert len(g.edges) == 0

    def test_single_file_no_deps(self):
        chunks = [_chunk("main.py")]
        g = _build_dependency_graph(chunks)
        assert "main" in g.nodes
        assert len(g.edges) == 0

    def test_import_creates_edge(self):
        chunks = [
            _chunk("main.py", "main", "module"),
            _chunk("utils.py", "utils", "import"),
        ]
        # utils.py imports from main.py — but the import chunk name is "utils"
        # We need the import chunk to reference the target
        import_chunk = CodeChunk(
            chunk_id="test:utils.py:import",
            content="import main",
            file_path="utils.py",
            start_line=1,
            end_line=1,
            language="Python",
            node_type="import",
            name="main",
            dependencies=("main",),
        )
        chunks = [_chunk("main.py", "main", "module"), import_chunk]
        g = _build_dependency_graph(chunks)
        assert g.has_edge("utils", "main")

    def test_function_dependency_creates_edge(self):
        chunks = [
            _chunk("main.py", "main", "module"),
            _chunk("utils.py", "helper", "function", dependencies=("main",)),
        ]
        g = _build_dependency_graph(chunks)
        assert g.has_edge("utils", "main")

    def test_self_dependency_ignored(self):
        chunks = [
            _chunk("main.py", "main", "function", dependencies=("main",)),
        ]
        g = _build_dependency_graph(chunks)
        assert len(g.edges) == 0

    def test_external_dependency_not_added(self):
        chunks = [
            _chunk("main.py", "main", "function", dependencies=("os", "sys")),
        ]
        g = _build_dependency_graph(chunks)
        assert len(g.edges) == 0

    def test_deduplicates_edges(self):
        chunks = [
            _chunk("a.py", "fa", "function", dependencies=("b",)),
            _chunk("a.py", "fb", "function", dependencies=("b",)),
            _chunk("b.py", "fb", "module"),
        ]
        g = _build_dependency_graph(chunks)
        assert g.number_of_edges("a", "b") == 1


# --- _detect_entry_points ---


class TestDetectEntryPoints:
    def test_python_main_detected(self):
        chunks = [_chunk("main.py", "main", "function")]
        manifest = _manifest(("Python",))
        result = _detect_entry_points(chunks, manifest)
        assert "main" in result

    def test_python_create_app_detected(self):
        chunks = [_chunk("app.py", "create_app", "function")]
        manifest = _manifest(("Python",))
        result = _detect_entry_points(chunks, manifest)
        assert "app" in result

    def test_no_entry_points_when_none_match(self):
        chunks = [_chunk("utils.py", "helper", "function")]
        manifest = _manifest(("Python",))
        result = _detect_entry_points(chunks, manifest)
        assert result == ()

    def test_null_manifest_returns_empty(self):
        chunks = [_chunk("main.py", "main", "function")]
        assert _detect_entry_points(chunks, None) == ()


# --- _find_core_modules ---


class TestFindCoreModules:
    def test_highly_connected_modules_identified(self):
        import networkx as nx
        g = nx.DiGraph()
        g.add_edges_from([("a", "b"), ("b", "c"), ("c", "a"), ("d", "a"), ("e", "a"), ("a", "e")])
        core = _find_core_modules(g)
        assert "a" in core

    def test_isolated_modules_not_core(self):
        import networkx as nx
        g = nx.DiGraph()
        g.add_node("isolated")
        core = _find_core_modules(g)
        assert "isolated" not in core

    def test_empty_graph_returns_empty(self):
        import networkx as nx
        core = _find_core_modules(nx.DiGraph())
        assert core == ()


# --- _find_orphan_modules ---


class TestFindOrphanModules:
    def test_isolated_nodes_are_orphans(self):
        import networkx as nx
        g = nx.DiGraph()
        g.add_node("orphan")
        g.add_edge("a", "b")
        assert _find_orphan_modules(g) == ("orphan",)

    def test_connected_nodes_not_orphans(self):
        import networkx as nx
        g = nx.DiGraph()
        g.add_edge("a", "b")
        assert "a" not in _find_orphan_modules(g)
        assert "b" not in _find_orphan_modules(g)

    def test_empty_graph_returns_empty(self):
        import networkx as nx
        assert _find_orphan_modules(nx.DiGraph()) == ()


# --- _detect_cycles ---


class TestDetectCycles:
    def test_no_cycles_in_dag(self):
        import networkx as nx
        g = nx.DiGraph()
        g.add_edges_from([("a", "b"), ("b", "c")])
        assert _detect_cycles(g) == ()

    def test_simple_cycle_detected(self):
        import networkx as nx
        g = nx.DiGraph()
        g.add_edges_from([("a", "b"), ("b", "a")])
        cycles = _detect_cycles(g)
        assert len(cycles) >= 1

    def test_longer_cycle_detected(self):
        import networkx as nx
        g = nx.DiGraph()
        g.add_edges_from([("a", "b"), ("b", "c"), ("c", "a")])
        cycles = _detect_cycles(g)
        assert len(cycles) >= 1

    def test_limits_to_max_cycles(self):
        # Verify we don't return more than MAX_CYCLES_TO_REPORT
        import networkx as nx
        from agents.architecture_mapper import MAX_CYCLES_TO_REPORT
        g = nx.DiGraph()
        # Create many small cycles
        for i in range(30):
            g.add_edge(f"a{i}", f"b{i}")
            g.add_edge(f"b{i}", f"a{i}")
        cycles = _detect_cycles(g)
        assert len(cycles) <= MAX_CYCLES_TO_REPORT


# --- _determine_pattern ---


class TestDeterminePattern:
    def test_mvc_pattern_from_manifest(self):
        manifest = _manifest(patterns=("MVC", "Monolith"))
        import networkx as nx
        assert _determine_pattern(manifest, nx.DiGraph()) == "mvc"

    def test_layered_pattern_from_manifest(self):
        manifest = _manifest(patterns=("Layered",))
        import networkx as nx
        assert _determine_pattern(manifest, nx.DiGraph()) == "layered"

    def test_microservices_from_manifest(self):
        manifest = _manifest(patterns=("Microservices-like",))
        import networkx as nx
        assert _determine_pattern(manifest, nx.DiGraph()) == "microservices-like"

    def test_fallback_to_monolith(self):
        import networkx as nx
        g = nx.DiGraph()
        g.add_node("a")
        assert _determine_pattern(None, g) == "monolith"


# --- _generate_mermaid ---


class TestGenerateMermaid:
    def test_empty_graph_produces_header_only(self):
        import networkx as nx
        result = _generate_mermaid(nx.DiGraph())
        assert "graph TD" in result
        lines = result.strip().split("\n")
        # Header has init directive + graph TD = 2 lines
        assert len(lines) == 2

    def test_single_node(self):
        import networkx as nx
        g = nx.DiGraph()
        g.add_node("main")
        result = _generate_mermaid(g)
        assert "main" in result

    def test_edges_produce_arrows(self):
        import networkx as nx
        g = nx.DiGraph()
        g.add_edge("a", "b")
        result = _generate_mermaid(g)
        assert "-->" in result

    def test_entry_points_style(self):
        import networkx as nx
        g = nx.DiGraph()
        g.add_node("main")
        g.add_node("utils")
        result = _generate_mermaid(g, entry_points=("main",))
        assert "Entry Points" in result

    def test_core_modules_in_graph(self):
        import networkx as nx
        g = nx.DiGraph()
        g.add_node("core")
        g.add_node("helper")
        result = _generate_mermaid(g, core_modules=("core",))
        assert "core" in result

    def test_orphan_modules_in_graph(self):
        import networkx as nx
        g = nx.DiGraph()
        g.add_node("orphan")
        result = _generate_mermaid(g, orphan_modules=("orphan",))
        assert "orphan" in result

    def test_subgraphs_by_depth(self):
        import networkx as nx
        g = nx.DiGraph()
        g.add_edge("main", "service")
        g.add_edge("service", "utils")
        result = _generate_mermaid(g, entry_points=("main",))
        assert "subgraph" in result
        assert "Entry Points" in result

    def test_dagre_renderer_config(self):
        import networkx as nx
        result = _generate_mermaid(nx.DiGraph())
        assert "dagre" in result
        assert "rankDirection" in result


# --- _generate_module_descriptions ---


class TestGenerateModuleDescriptions:
    def test_function_only_module(self):
        chunks = [_chunk("utils.py", "helper", "function")]
        desc = _generate_module_descriptions(chunks)
        assert "Utility module" in desc["utils"]

    def test_class_module(self):
        chunks = [_chunk("models.py", "User", "class")]
        desc = _generate_module_descriptions(chunks)
        assert "1 class" in desc["models"]

    def test_mixed_module(self):
        chunks = [
            _chunk("app.py", "func1", "function"),
            _chunk("app.py", "MyClass", "class"),
        ]
        desc = _generate_module_descriptions(chunks)
        assert "function" in desc["app"]
        assert "class" in desc["app"]

    def test_empty_chunks_return_empty_dict(self):
        assert _generate_module_descriptions([]) == {}


# --- architecture_mapper (pipeline) ---


class TestArchitectureMapperPipeline:
    def test_successful_mapping(self):
        chunks = [
            _chunk("main.py", "main", "module"),
            _chunk("utils.py", "helper", "function"),
        ]
        manifest = _manifest()
        state = _make_state(chunks=chunks, manifest=manifest)
        result = architecture_mapper(state)

        assert result["status"] == PipelineStatus.MAPPING
        assert isinstance(result["architecture_report"], ArchitectureReport)
        assert result["architecture_report"].dependency_graph is not None
        assert len(result["agent_logs"]) == 1
        assert result["agent_logs"][0].status == AgentStatus.COMPLETED

    def test_no_chunks_fails(self):
        state = _make_state(chunks=[])
        result = architecture_mapper(state)
        assert result["status"] == PipelineStatus.FAILED
        assert "no chunks" in result["error_message"]

    def test_exception_caught_and_reported(self):
        chunks = [_chunk("main.py", "main", "module")]
        state = _make_state(chunks=chunks)
        with patch(
            "agents.architecture_mapper._build_dependency_graph",
            side_effect=RuntimeError("boom"),
        ):
            result = architecture_mapper(state)
        assert result["status"] == PipelineStatus.FAILED
        assert "boom" in result["error_message"]

    def test_preserves_existing_state(self):
        chunks = [_chunk("main.py", "main", "module")]
        state = _make_state(chunks=chunks)
        state["total_tokens_used"] = 42
        result = architecture_mapper(state)
        assert result["total_tokens_used"] == 42
        assert result["job_id"] == "test123"


# --- should_continue_after_mapping ---


class TestShouldContinueAfterMapping:
    def test_failed_routes_to_end(self):
        state: GrimoireState = {
            "status": PipelineStatus.FAILED,
            "architecture_report": None,
        }
        assert should_continue_after_mapping(state) == "end"

    def test_no_report_routes_to_end(self):
        state: GrimoireState = {
            "status": PipelineStatus.MAPPING,
            "architecture_report": None,
        }
        assert should_continue_after_mapping(state) == "end"

    def test_success_routes_to_tech_debt_analyzer(self):
        report = ArchitectureReport(
            dependency_graph={},
            entry_points=(),
            core_modules=(),
            orphan_modules=(),
            dependency_cycles=(),
            detected_pattern="monolith",
            mermaid_diagram="graph TD",
            module_descriptions={},
        )
        state: GrimoireState = {
            "status": PipelineStatus.MAPPING,
            "architecture_report": report,
        }
        assert should_continue_after_mapping(state) == "tech_debt_analyzer"

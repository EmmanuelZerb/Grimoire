"""Grimoire — ArchitectureMapperAgent.

Builds a dependency graph from code chunks using networkx,
detects entry points, core/orphan modules, cycles, and
generates a Mermaid diagram.

This is Agent 3 in the LangGraph pipeline.
"""

from __future__ import annotations

import logging
from collections import Counter
from datetime import datetime, timezone
from typing import Any

import networkx as nx

from graph.state import (
    AgentLog,
    AgentName,
    AgentStatus,
    ArchitectureReport,
    CodeChunk,
    GrimoireState,
    PipelineStatus,
    RepoManifest,
)

logger = logging.getLogger(__name__)

# --- Constants ---

CORE_MODULE_DEGREE_THRESHOLD = 3

MAX_CYCLES_TO_REPORT = 20

ENTRY_POINT_PATTERNS: dict[str, tuple[str, ...]] = {
    "Python": ("main", "app", "create_app", "manage"),
    "JavaScript": ("main", "app", "server", "index"),
    "JavaScript (JSX)": ("main", "app", "server", "index"),
    "TypeScript": ("main", "app", "server", "index"),
    "TypeScript (TSX)": ("main", "app", "server", "index"),
    "Go": ("main",),
    "Rust": ("main",),
    "Java": ("main", "Application"),
    "Ruby": ("Application", "Rails"),
}


# --- Helper functions ---


def _normalize_module_path(file_path: str) -> str:
    """Normalize a file path to a module path.

    Strips leading ``./``, normalizes separators, removes the file extension.
    """
    path = file_path.lstrip("./").replace("\\", "/")
    # Remove extension
    dot = path.rfind(".")
    if dot > 0:
        path = path[:dot]
    return path


def _normalize_dependency_name(
    dep: str, all_modules: set[str]
) -> str | None:
    """Try to match a raw dependency string to a known internal module path.

    Returns the matched module path, or None if the dependency is external.
    """
    dep_clean = dep.strip().split(".")[-1] if "." in dep else dep.strip()
    if not dep_clean:
        return None

    # Exact basename match
    for module in all_modules:
        if module.endswith(f"/{dep_clean}") or module == dep_clean:
            return module

    # Suffix match (e.g. "utils" matches "src/utils")
    for module in all_modules:
        parts = module.split("/")
        if parts[-1] == dep_clean:
            return module

    return None


def _build_dependency_graph(chunks: list[CodeChunk]) -> nx.DiGraph:
    """Build a directed dependency graph from code chunks.

    Nodes are normalized module paths (file paths without extension).
    Edges represent import/call dependencies between modules.
    Only internal dependencies (matching known modules) are included.
    """
    graph = nx.DiGraph()

    # Collect all module paths
    all_modules: set[str] = set()
    for chunk in chunks:
        mod = _normalize_module_path(chunk.file_path)
        all_modules.add(mod)

    # Add all modules as nodes
    for mod in all_modules:
        graph.add_node(mod)

    # Build edges from import chunks and function/class dependencies
    for chunk in chunks:
        source = _normalize_module_path(chunk.file_path)
        deps: tuple[str, ...] = ()

        if chunk.node_type == "import":
            # Import chunk: the imported module name is in chunk.name
            if chunk.name:
                deps = (chunk.name,) + chunk.dependencies
            else:
                deps = chunk.dependencies
        elif chunk.node_type in ("function", "class", "method"):
            deps = chunk.dependencies

        for dep in deps:
            if not dep or dep == source:
                continue
            target = _normalize_dependency_name(dep, all_modules)
            if target and target != source:
                if not graph.has_edge(source, target):
                    graph.add_edge(source, target, edge_type=chunk.node_type)

    return graph


def _detect_entry_points(
    chunks: list[CodeChunk], manifest: RepoManifest | None
) -> tuple[str, ...]:
    """Detect likely entry point modules from chunk names."""
    if manifest is None:
        return ()

    # Collect entry point names for all languages in the manifest
    entry_names: set[str] = set()
    for lang_stats in manifest.languages:
        patterns = ENTRY_POINT_PATTERNS.get(lang_stats.name, ())
        entry_names.update(patterns)

    if not entry_names:
        return ()

    # Find modules containing entry point functions/modules
    found: set[str] = set()
    for chunk in chunks:
        if chunk.name in entry_names and chunk.node_type in (
            "function",
            "module",
        ):
            found.add(_normalize_module_path(chunk.file_path))

    return tuple(sorted(found))


def _find_core_modules(graph: nx.DiGraph) -> tuple[str, ...]:
    """Find modules with high connectivity (in-degree + out-degree)."""
    if not graph.nodes:
        return ()

    degrees: dict[str, int] = {}
    for node in graph.nodes:
        degrees[node] = graph.in_degree(node) + graph.out_degree(node)

    core = sorted(
        (n for n, d in degrees.items() if d >= CORE_MODULE_DEGREE_THRESHOLD),
        key=lambda n: degrees[n],
        reverse=True,
    )
    return tuple(core)


def _find_orphan_modules(graph: nx.DiGraph) -> tuple[str, ...]:
    """Find modules with no dependencies (zero in-degree and zero out-degree)."""
    orphans = sorted(
        n
        for n in graph.nodes
        if graph.in_degree(n) == 0 and graph.out_degree(n) == 0
    )
    return tuple(orphans)


def _detect_cycles(graph: nx.DiGraph) -> tuple[tuple[str, ...], ...]:
    """Detect dependency cycles using networkx, capped at MAX_CYCLES_TO_REPORT."""
    try:
        cycles = list(nx.simple_cycles(graph))[:MAX_CYCLES_TO_REPORT]
    except Exception:
        cycles = []

    return tuple(tuple(c) for c in cycles)


def _determine_pattern(
    manifest: RepoManifest | None, graph: nx.DiGraph
) -> str:
    """Determine the architectural pattern, using manifest hints as primary source."""
    if manifest and manifest.detected_patterns:
        patterns = manifest.detected_patterns
        priority = ["MVC", "Hexagonal", "Layered", "Microservices-like", "Monorepo"]
        for p in priority:
            if p in patterns:
                return p.lower()

    # Fallback based on graph structure
    if not graph.nodes or not graph.edges:
        return "monolith"

    avg_degree = sum(dict(graph.degree()).values()) / max(len(graph.nodes), 1)
    if avg_degree > 4:
        return "layered"
    return "monolith"


def _generate_mermaid(graph: nx.DiGraph) -> str:
    """Generate a Mermaid graph TD diagram from the dependency graph."""
    lines = ["graph TD"]

    if not graph.nodes:
        return "\n".join(lines)

    # Create node ID mapping
    node_ids: dict[str, str] = {}
    for i, node in enumerate(sorted(graph.nodes)):
        label = node.split("/")[-1] if "/" in node else node
        # Sanitize for Mermaid
        label = label.replace('"', "'")
        node_ids[node] = f"N{i}"
        lines.append(f'    {node_ids[node]}["{label}"]')

    # Add edges
    for source, target in sorted(graph.edges):
        lines.append(f"    {node_ids[source]} --> {node_ids[target]}")

    return "\n".join(lines)


def _generate_module_descriptions(chunks: list[CodeChunk]) -> dict[str, str]:
    """Generate rule-based descriptions for each module."""
    modules: dict[str, dict[str, int]] = {}

    for chunk in chunks:
        mod = _normalize_module_path(chunk.file_path)
        if mod not in modules:
            modules[mod] = {"functions": 0, "classes": 0, "imports": 0, "other": 0}

        if chunk.node_type == "function":
            modules[mod]["functions"] += 1
        elif chunk.node_type == "class":
            modules[mod]["classes"] += 1
        elif chunk.node_type == "import":
            modules[mod]["imports"] += 1
        else:
            modules[mod]["other"] += 1

    descriptions: dict[str, str] = {}
    for mod, counts in sorted(modules.items()):
        funcs = counts["functions"]
        classes = counts["classes"]
        imports = counts["imports"]

        if imports > 0 and funcs == 0 and classes == 0:
            desc = f"Re-export module with {imports} imports"
        elif classes > 0 and funcs == 0:
            desc = f"Module defining {classes} class{'es' if classes > 1 else ''}"
        elif funcs > 0 and classes == 0:
            desc = f"Utility module with {funcs} function{'s' if funcs > 1 else ''}"
        else:
            parts = []
            if funcs:
                parts.append(f"{funcs} function{'s' if funcs > 1 else ''}")
            if classes:
                parts.append(f"{classes} class{'es' if classes > 1 else ''}")
            desc = "Module with " + " and ".join(parts)

        descriptions[mod] = desc

    return descriptions


# --- Agent function ---


def architecture_mapper(state: GrimoireState) -> GrimoireState:
    """LangGraph node function for the ArchitectureMapperAgent.

    Reads code chunks and builds a dependency graph, detects
    entry points, core/orphan modules, cycles, and generates
    a Mermaid diagram.

    Args:
        state: Current pipeline state. Must contain ``chunks``.

    Returns:
        Updated state with ``architecture_report``, updated ``status``,
        and agent log.
    """
    job_id = state["job_id"]
    chunks = state.get("chunks", [])
    manifest = state.get("repo_manifest")

    log_entry = AgentLog(
        agent=AgentName.ARCHITECTURE_MAPPER,
        status=AgentStatus.RUNNING,
        started_at=datetime.now(timezone.utc).timestamp(),
    )

    logger.info("[%s] Starting architecture mapping", job_id)

    if not chunks:
        failed_log = AgentLog(
            agent=AgentName.ARCHITECTURE_MAPPER,
            status=AgentStatus.FAILED,
            started_at=log_entry.started_at,
            completed_at=datetime.now(timezone.utc).timestamp(),
            error="No chunks in state",
        )
        return {
            **state,
            "status": PipelineStatus.FAILED,
            "error_message": "ArchitectureMapperAgent failed: no chunks",
            "agent_logs": state.get("agent_logs", []) + [failed_log],
        }

    try:
        graph = _build_dependency_graph(chunks)
        entry_points = _detect_entry_points(chunks, manifest)
        core_modules = _find_core_modules(graph)
        orphan_modules = _find_orphan_modules(graph)
        cycles = _detect_cycles(graph)
        pattern = _determine_pattern(manifest, graph)
        mermaid = _generate_mermaid(graph)
        descriptions = _generate_module_descriptions(chunks)

        # Convert graph to adjacency dict for serialization
        dep_graph_dict: dict[str, list[str]] = {}
        for node in sorted(graph.nodes):
            dep_graph_dict[node] = sorted(graph.successors(node))

        report = ArchitectureReport(
            dependency_graph=dep_graph_dict,
            entry_points=entry_points,
            core_modules=core_modules,
            orphan_modules=orphan_modules,
            dependency_cycles=cycles,
            detected_pattern=pattern,
            mermaid_diagram=mermaid,
            module_descriptions=descriptions,
        )

        logger.info(
            "[%s] Architecture mapping complete: %d modules, %d edges, pattern=%s",
            job_id,
            len(graph.nodes),
            len(graph.edges),
            pattern,
        )

        completed_log = AgentLog(
            agent=AgentName.ARCHITECTURE_MAPPER,
            status=AgentStatus.COMPLETED,
            started_at=log_entry.started_at,
            completed_at=datetime.now(timezone.utc).timestamp(),
        )

        return {
            **state,
            "status": PipelineStatus.MAPPING,
            "architecture_report": report,
            "current_agent": AgentName.ARCHITECTURE_MAPPER,
            "agent_logs": state.get("agent_logs", []) + [completed_log],
        }

    except Exception as e:
        logger.error("[%s] Architecture mapping failed: %s", job_id, e)
        failed_log = AgentLog(
            agent=AgentName.ARCHITECTURE_MAPPER,
            status=AgentStatus.FAILED,
            started_at=log_entry.started_at,
            completed_at=datetime.now(timezone.utc).timestamp(),
            error=str(e),
        )
        return {
            **state,
            "status": PipelineStatus.FAILED,
            "error_message": f"ArchitectureMapperAgent failed: {e}",
            "agent_logs": state.get("agent_logs", []) + [failed_log],
        }


# --- Conditional edge ---


def should_continue_after_mapping(state: GrimoireState) -> str:
    """Conditional edge after ArchitectureMapperAgent.

    Routes to:
    - ``"end"`` if mapping failed
    - ``"end"`` if no architecture report produced
    - ``"tech_debt_analyzer"`` on success
    """
    if state.get("status") == PipelineStatus.FAILED:
        return "end"

    report = state.get("architecture_report")
    if report is None:
        return "end"

    return "tech_debt_analyzer"

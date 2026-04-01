"""Grimoire — CodeChunkerAgent.

Parses source files with tree-sitter to extract semantic chunks
(functions, classes, imports, etc.), with a regex fallback for
unsupported languages.

This is Agent 2 in the LangGraph pipeline.
"""

from __future__ import annotations

import hashlib
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import tree_sitter_languages

from agents.repo_ingestor import (
    CODE_EXTENSIONS,
    EXTENSION_TO_LANGUAGE,
    SKIP_DIRS,
    _is_skipped_file,
)
from graph.state import (
    AgentLog,
    AgentName,
    AgentStatus,
    CodeChunk,
    GrimoireState,
    PipelineStatus,
)

logger = logging.getLogger(__name__)

# --- Constants ---

MAX_FILE_LINES = 3000
MAX_CHUNK_LINES = 500
MIN_CHUNK_LINES = 2

# Map Grimoire language names to tree-sitter language identifiers
LANGUAGE_TO_TREE_SITTER: dict[str, str] = {
    "Python": "python",
    "JavaScript": "javascript",
    "JavaScript (JSX)": "javascript",
    "TypeScript": "typescript",
    "TypeScript (TSX)": "tsx",
    "Go": "go",
    "Rust": "rust",
    "Java": "java",
    "C": "c",
    "C++": "cpp",
    "Ruby": "ruby",
    "PHP": "php",
    "Kotlin": "kotlin",
    "Swift": "swift",
    "C#": "c_sharp",
}

# Map tree-sitter language identifiers to AST node type -> canonical type
LANGUAGE_NODE_TYPE_MAP: dict[str, dict[str, str]] = {
    "python": {
        "function_definition": "function",
        "class_definition": "class",
        "import_statement": "import",
        "import_from_statement": "import",
    },
    "javascript": {
        "function_declaration": "function",
        "class_declaration": "class",
        "method_definition": "method",
        "import_statement": "import",
        "export_statement": "export",
        "lexical_declaration": "variable",
        "variable_declaration": "variable",
    },
    "typescript": {
        "function_declaration": "function",
        "class_declaration": "class",
        "method_definition": "method",
        "import_statement": "import",
        "export_statement": "export",
        "interface_declaration": "interface",
        "type_alias_declaration": "variable",
        "lexical_declaration": "variable",
    },
    "tsx": {
        "function_declaration": "function",
        "class_declaration": "class",
        "method_definition": "method",
        "import_statement": "import",
        "export_statement": "export",
        "interface_declaration": "interface",
        "lexical_declaration": "variable",
    },
    "go": {
        "function_declaration": "function",
        "method_declaration": "method",
        "type_declaration": "interface",
        "import_declaration": "import",
    },
    "rust": {
        "function_item": "function",
        "struct_item": "struct",
        "enum_item": "enum",
        "trait_item": "trait",
        "impl_item": "module",
        "use_declaration": "import",
        "mod_item": "module",
    },
    "java": {
        "class_declaration": "class",
        "method_declaration": "method",
        "interface_declaration": "interface",
        "enum_declaration": "enum",
        "import_declaration": "import",
    },
    "c": {
        "function_definition": "function",
        "struct_specifier": "struct",
        "enum_specifier": "enum",
        "preproc_include": "import",
    },
    "cpp": {
        "function_definition": "function",
        "class_specifier": "class",
        "struct_specifier": "struct",
        "enum_specifier": "enum",
        "namespace_definition": "module",
        "preproc_include": "import",
    },
    "ruby": {
        "method": "function",
        "singleton_method": "method",
        "class": "class",
        "module": "module",
    },
    "php": {
        "function_definition": "function",
        "class_declaration": "class",
        "interface_declaration": "interface",
    },
    "kotlin": {
        "function_declaration": "function",
        "class_declaration": "class",
        "object_declaration": "class",
    },
    "swift": {
        "function_declaration": "function",
        "class_declaration": "class",
        "struct_declaration": "struct",
        "protocol_declaration": "interface",
        "enum_declaration": "enum",
        "import_declaration": "import",
    },
    "c_sharp": {
        "class_declaration": "class",
        "method_declaration": "method",
        "interface_declaration": "interface",
        "enum_declaration": "enum",
        "struct_declaration": "struct",
        "using_directive": "import",
    },
}

DEFAULT_NODE_TYPES: dict[str, str] = {
    "function_definition": "function",
    "function_declaration": "function",
    "class_definition": "class",
    "class_declaration": "class",
    "method_definition": "method",
    "method_declaration": "method",
    "import_statement": "import",
    "import_declaration": "import",
    "export_statement": "export",
    "interface_declaration": "interface",
    "enum_declaration": "enum",
    "struct_specifier": "struct",
    "struct_declaration": "struct",
    "trait_item": "trait",
    "module": "module",
    "namespace_definition": "module",
    "variable_declaration": "variable",
}

# Fallback regex patterns for languages without tree-sitter support
FALLBACK_FUNCTION_PATTERNS: list[re.Pattern] = [
    re.compile(r"^\s*def\s+(\w+)", re.MULTILINE),
    re.compile(r"^\s*function\s+(\w+)", re.MULTILINE),
    re.compile(r"^\s*func\s+(\w+)", re.MULTILINE),
    re.compile(r"^\s*fn\s+(\w+)", re.MULTILINE),
    re.compile(r"^\s*pub\s+fn\s+(\w+)", re.MULTILINE),
    re.compile(r"^\s*sub\s+(\w+)", re.MULTILINE),
]

FALLBACK_CLASS_PATTERNS: list[re.Pattern] = [
    re.compile(r"^\s*class\s+(\w+)", re.MULTILINE),
    re.compile(r"^\s*interface\s+(\w+)", re.MULTILINE),
    re.compile(r"^\s*struct\s+(\w+)", re.MULTILINE),
    re.compile(r"^\s*enum\s+(\w+)", re.MULTILINE),
    re.compile(r"^\s*trait\s+(\w+)", re.MULTILINE),
    re.compile(r"^\s*module\s+(\w+)", re.MULTILINE),
]

FALLBACK_IMPORT_PATTERNS: list[re.Pattern] = [
    re.compile(r"^\s*import\s+(.+)$", re.MULTILINE),
    re.compile(r"^\s*from\s+([\w.]+)\s+import", re.MULTILINE),
    re.compile(r"^\s*require\s*\(['\"](.+?)['\"]\)", re.MULTILINE),
    re.compile(r"^\s*use\s+(.+)$", re.MULTILINE),
    re.compile(r"^\s*#include\s*[<\"](.+?)[>\"]", re.MULTILINE),
]


# --- Helper functions ---


def _get_tree_sitter_lang(language_name: str) -> str | None:
    """Map a Grimoire language name to a tree-sitter language identifier."""
    return LANGUAGE_TO_TREE_SITTER.get(language_name)


def _get_node_type_map(ts_lang: str) -> dict[str, str]:
    """Return the node type mapping for a given tree-sitter language."""
    return LANGUAGE_NODE_TYPE_MAP.get(ts_lang, DEFAULT_NODE_TYPES)


def _is_binary_file(file_path: Path) -> bool:
    """Check if a file is binary by looking for null bytes in the first 8KB."""
    try:
        with open(file_path, "rb") as f:
            chunk = f.read(8192)
        return b"\x00" in chunk
    except OSError:
        return True


def _read_file_lines(file_path: Path) -> list[str] | None:
    """Read a UTF-8 file and return its lines. Returns None if binary/error/too large."""
    try:
        if _is_binary_file(file_path):
            return None
        text = file_path.read_text(encoding="utf-8", errors="replace")
        lines = text.splitlines()
        if len(lines) > MAX_FILE_LINES:
            return None
        return lines
    except OSError:
        return None


def _extract_name_from_node(node: Any, source_lines: list[str]) -> str:
    """Extract the name from an AST node by looking for name/identifier children."""
    for field_name in ("name", "identifier", "type_identifier"):
        child = node.child_by_field_name(field_name)
        if child is not None:
            row = child.start_point[0]
            col_start = child.start_point[1]
            col_end = child.end_point[1]
            if row < len(source_lines):
                return source_lines[row][col_start:col_end]
    for child in node.named_children:
        if child.type in ("identifier", "type_identifier", "property_identifier"):
            row = child.start_point[0]
            col_start = child.start_point[1]
            col_end = child.end_point[1]
            return source_lines[row][col_start:col_end]
    return "<anonymous>"


def _extract_calls_from_node(node: Any) -> tuple[str, ...]:
    """Extract function call names from a subtree."""
    calls: list[str] = []
    _walk_for_calls(node, calls)
    return tuple(calls)


def _walk_for_calls(node: Any, calls: list[str]) -> None:
    """Recursively walk AST to find call expressions."""
    call_types = {"call", "call_expression", "method_invocation"}
    if node.type in call_types:
        func_node = None
        for child in node.named_children:
            if child.type in (
                "identifier",
                "field_access",
                "attribute",
                "member_expression",
            ):
                func_node = child
                break
        if func_node is None and node.named_children:
            func_node = node.named_children[0]
        if func_node is not None:
            text = func_node.text
            if isinstance(text, bytes):
                text = text.decode("utf-8", errors="replace")
            calls.append(text.strip())
    for child in node.named_children:
        _walk_for_calls(child, calls)


def _extract_imports_from_tree(
    root_node: Any, source_lines: list[str], ts_lang: str
) -> tuple[str, ...]:
    """Extract all imported module names from the AST."""
    imports: list[str] = []
    import_types = {
        "import_statement",
        "import_from_statement",
        "import_declaration",
        "use_declaration",
        "preproc_include",
        "using_directive",
    }
    for child in root_node.children:
        if child.type in import_types:
            row = child.start_point[0]
            line = source_lines[row] if row < len(source_lines) else ""
            for pattern in FALLBACK_IMPORT_PATTERNS:
                match = pattern.search(line)
                if match:
                    imports.append(match.group(1).strip())
                    break
    return tuple(imports)


def _extract_dependencies_from_node(
    node: Any, source_lines: list[str], ts_lang: str
) -> tuple[str, ...]:
    """Extract dependencies (calls) from a node, deduplicated."""
    calls = _extract_calls_from_node(node)
    seen: set[str] = set()
    deps: list[str] = []
    for dep in calls:
        if dep not in seen:
            seen.add(dep)
            deps.append(dep)
    return tuple(deps)


def _make_chunk_id(file_path: str, node_type: str, name: str, start_line: int) -> str:
    """Generate a deterministic chunk ID."""
    raw = f"{file_path}:{node_type}:{name}:{start_line}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


# --- Tree-sitter parsing ---


def _parse_with_tree_sitter(
    source_bytes: bytes,
    source_lines: list[str],
    ts_lang: str,
    relative_path: str,
    language_name: str,
) -> list[CodeChunk]:
    """Parse source bytes with tree-sitter and extract semantic chunks."""
    try:
        parser = tree_sitter_languages.get_parser(ts_lang)
    except Exception:
        logger.warning("tree-sitter parser not available for '%s'", ts_lang)
        return []

    try:
        tree = parser.parse(source_bytes)
    except Exception:
        logger.warning("tree-sitter parse error for '%s'", relative_path)
        return []

    root = tree.root_node
    node_type_map = _get_node_type_map(ts_lang)
    chunks: list[CodeChunk] = []

    for child in root.children:
        canonical_type = node_type_map.get(child.type)
        if canonical_type is None:
            continue

        # Handle Python decorated definitions
        if child.type == "decorated_definition" and child.named_children:
            actual = child.named_children[-1]
            canonical_type = node_type_map.get(actual.type)
            if canonical_type is None:
                continue
            name = _extract_name_from_node(actual, source_lines)
            dependencies = _extract_dependencies_from_node(actual, source_lines, ts_lang)
            start_line = child.start_point[0] + 1
            end_line = child.end_point[0] + 1
        else:
            name = _extract_name_from_node(child, source_lines)
            dependencies = _extract_dependencies_from_node(child, source_lines, ts_lang)
            start_line = child.start_point[0] + 1
            end_line = child.end_point[0] + 1

        line_count = end_line - start_line + 1
        if line_count < MIN_CHUNK_LINES:
            continue

        content = "\n".join(source_lines[start_line - 1 : end_line])
        metadata: dict[str, Any] = {}
        if line_count > MAX_CHUNK_LINES:
            metadata["oversized"] = True

        chunk = CodeChunk(
            chunk_id=_make_chunk_id(relative_path, canonical_type, name, start_line),
            content=content,
            file_path=relative_path,
            start_line=start_line,
            end_line=end_line,
            language=language_name,
            node_type=canonical_type,
            name=name,
            dependencies=dependencies,
            metadata=metadata,
        )
        chunks.append(chunk)

    # If no chunks found, create a module chunk for the entire file
    if not chunks and source_lines:
        content = "\n".join(source_lines)
        chunks.append(
            CodeChunk(
                chunk_id=_make_chunk_id(
                    relative_path, "module", Path(relative_path).name, 1
                ),
                content=content,
                file_path=relative_path,
                start_line=1,
                end_line=len(source_lines),
                language=language_name,
                node_type="module",
                name=Path(relative_path).name,
                dependencies=(),
                metadata={},
            )
        )

    return chunks


# --- Fallback regex chunking ---


def _chunk_with_fallback(
    source_lines: list[str],
    relative_path: str,
    language_name: str,
) -> list[CodeChunk]:
    """Chunk a file using regex fallback when tree-sitter is not available."""
    if not source_lines:
        return []

    text = "\n".join(source_lines)

    # Collect all matches: (line_number, match_type, name)
    boundaries: list[tuple[int, str, str]] = []

    for pattern in FALLBACK_FUNCTION_PATTERNS:
        for match in pattern.finditer(text):
            name = None
            for group in match.groups():
                if group is not None:
                    name = group
            if name:
                line_no = text[: match.start()].count("\n") + 1
                boundaries.append((line_no, "function", name))

    for pattern in FALLBACK_CLASS_PATTERNS:
        for match in pattern.finditer(text):
            name = None
            for group in match.groups():
                if group is not None:
                    name = group
            if name:
                line_no = text[: match.start()].count("\n") + 1
                boundaries.append((line_no, "class", name))

    # Sort by line number, stable sort preserves order for same line
    boundaries.sort(key=lambda x: x[0])

    # Extract imports
    imports: list[str] = []
    for pattern in FALLBACK_IMPORT_PATTERNS:
        for match in pattern.finditer(text):
            imports.append(match.group(1).strip())
    imports_tuple = tuple(dict.fromkeys(imports))

    if not boundaries:
        # No match -> module chunk for the whole file
        return [
            CodeChunk(
                chunk_id=_make_chunk_id(
                    relative_path, "module", Path(relative_path).name, 1
                ),
                content=text,
                file_path=relative_path,
                start_line=1,
                end_line=len(source_lines),
                language=language_name,
                node_type="module",
                name=Path(relative_path).name,
                dependencies=imports_tuple,
                metadata={},
            )
        ]

    chunks: list[CodeChunk] = []
    for i, (line_no, match_type, name) in enumerate(boundaries):
        if i + 1 < len(boundaries):
            end_line = boundaries[i + 1][0] - 1
        else:
            end_line = len(source_lines)

        line_count = end_line - line_no + 1
        if line_count < MIN_CHUNK_LINES:
            continue

        content = "\n".join(source_lines[line_no - 1 : end_line])
        metadata: dict[str, Any] = {}
        if line_count > MAX_CHUNK_LINES:
            metadata["oversized"] = True

        chunks.append(
            CodeChunk(
                chunk_id=_make_chunk_id(relative_path, match_type, name, line_no),
                content=content,
                file_path=relative_path,
                start_line=line_no,
                end_line=end_line,
                language=language_name,
                node_type=match_type,
                name=name,
                dependencies=imports_tuple,
                metadata=metadata,
            )
        )

    return chunks


# --- File orchestration ---


def _chunk_file(
    file_path: Path, relative_path: str, language_name: str
) -> list[CodeChunk]:
    """Orchestrate tree-sitter or fallback chunking for a single file."""
    try:
        source_bytes = file_path.read_bytes()
    except OSError:
        return []

    # Binary check
    if b"\x00" in source_bytes[:8192]:
        return []

    source_lines = source_bytes.decode("utf-8", errors="replace").splitlines()
    if len(source_lines) > MAX_FILE_LINES:
        return []

    ts_lang = _get_tree_sitter_lang(language_name)
    if ts_lang is not None:
        try:
            return _parse_with_tree_sitter(
                source_bytes, source_lines, ts_lang, relative_path, language_name
            )
        except Exception:
            logger.warning("tree-sitter failed for '%s', using fallback", relative_path)
            return _chunk_with_fallback(source_lines, relative_path, language_name)
    else:
        return _chunk_with_fallback(source_lines, relative_path, language_name)


# --- Repo walking ---


def _walk_repo_files(repo_path: Path) -> list[tuple[Path, str, str]]:
    """Walk the repo and return (file_path, relative_path, language_name) tuples."""
    results: list[tuple[Path, str, str]] = []

    for file_path in sorted(repo_path.rglob("*")):
        if not file_path.is_file():
            continue

        relative = file_path.relative_to(repo_path)
        parts = relative.parts

        # Skip directories in SKIP_DIRS
        if any(part in SKIP_DIRS for part in parts[:-1]):
            continue
        # Skip hidden directories
        if any(part.startswith(".") for part in parts[:-1]):
            continue

        # Skip files
        if _is_skipped_file(file_path.name):
            continue

        # Only code extensions
        ext = file_path.suffix.lower()
        if ext not in CODE_EXTENSIONS:
            continue

        # Detect language
        language_name = EXTENSION_TO_LANGUAGE.get(ext)
        if language_name is None:
            continue

        results.append((file_path, str(relative).replace("\\", "/"), language_name))

    return results


# --- Agent function ---


def code_chunker(state: GrimoireState) -> GrimoireState:
    """LangGraph node function for the CodeChunkerAgent.

    Reads the repo manifest, walks all source files, and extracts
    semantic code chunks using tree-sitter (with regex fallback).

    Args:
        state: Current pipeline state. Must contain ``repo_manifest``.

    Returns:
        Updated state with ``chunks``, ``total_chunks``, updated ``status``, and
        agent log.
    """
    job_id = state["job_id"]
    manifest = state.get("repo_manifest")

    log_entry = AgentLog(
        agent=AgentName.CODE_CHUNKER,
        status=AgentStatus.RUNNING,
        started_at=datetime.now(timezone.utc).timestamp(),
    )

    logger.info("[%s] Starting code chunking", job_id)

    # Fatal error: no manifest
    if manifest is None:
        logger.error("[%s] No repo_manifest in state", job_id)
        failed_log = AgentLog(
            agent=AgentName.CODE_CHUNKER,
            status=AgentStatus.FAILED,
            started_at=log_entry.started_at,
            completed_at=datetime.now(timezone.utc).timestamp(),
            error="No repo_manifest in state",
        )
        return {
            **state,
            "status": PipelineStatus.FAILED,
            "error_message": "CodeChunkerAgent failed: no repo_manifest",
            "agent_logs": state.get("agent_logs", []) + [failed_log],
        }

    clone_path = Path(manifest.clone_path)
    if not clone_path.exists():
        logger.error("[%s] Clone path does not exist: %s", job_id, clone_path)
        failed_log = AgentLog(
            agent=AgentName.CODE_CHUNKER,
            status=AgentStatus.FAILED,
            started_at=log_entry.started_at,
            completed_at=datetime.now(timezone.utc).timestamp(),
            error=f"Clone path does not exist: {clone_path}",
        )
        return {
            **state,
            "status": PipelineStatus.FAILED,
            "error_message": f"CodeChunkerAgent failed: clone path {clone_path} not found",
            "agent_logs": state.get("agent_logs", []) + [failed_log],
        }

    # Walk and chunk all files
    all_chunks: list[CodeChunk] = []
    files_with_errors = 0
    files = _walk_repo_files(clone_path)

    for file_path, relative_path, language_name in files:
        try:
            chunks = _chunk_file(file_path, relative_path, language_name)
            all_chunks.extend(chunks)
        except Exception as e:
            logger.warning("[%s] Error chunking '%s': %s", job_id, relative_path, e)
            files_with_errors += 1

    logger.info(
        "[%s] Chunking complete: %d chunks from %d files (%d errors)",
        job_id,
        len(all_chunks),
        len(files),
        files_with_errors,
    )

    completed_log = AgentLog(
        agent=AgentName.CODE_CHUNKER,
        status=AgentStatus.COMPLETED,
        started_at=log_entry.started_at,
        completed_at=datetime.now(timezone.utc).timestamp(),
    )

    return {
        **state,
        "status": PipelineStatus.CHUNKING,
        "chunks": all_chunks,
        "total_chunks": len(all_chunks),
        "current_agent": AgentName.CODE_CHUNKER,
        "agent_logs": state.get("agent_logs", []) + [completed_log],
    }


# --- Conditional edge ---


def should_continue_after_chunking(state: GrimoireState) -> str:
    """Conditional edge after CodeChunkerAgent.

    Routes to:
    - ``"end"`` if chunking failed
    - ``"end"`` if no chunks were produced
    - ``"end"`` (Phase 3 will add ``"architecture_mapper"``)
    """
    if state.get("status") == PipelineStatus.FAILED:
        return "end"

    chunks = state.get("chunks", [])
    if not chunks:
        return "end"

    return "architecture_mapper"

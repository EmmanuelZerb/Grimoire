"""Grimoire — TechDebtAnalyzerAgent.

Scans code chunks for technical debt indicators: TODO/FIXME comments,
complexity metrics, oversized files, and outdated dependency pins.

This is Agent 4 in the LangGraph pipeline.
"""

from __future__ import annotations

import logging
import re
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

from graph.state import (
    AgentLog,
    AgentName,
    AgentStatus,
    CodeChunk,
    GrimoireState,
    PipelineStatus,
    RepoManifest,
    TechDebtCategory,
    TechDebtReport,
)

logger = logging.getLogger(__name__)

# --- Constants ---

TODO_PATTERN = re.compile(
    r"(?:#\s*|//\s*|/\*\s*|\*\s*)\s*(TODO|FIXME|HACK|XXX)\b[:\s]*(.+?)(?:\n|$)",
    re.IGNORECASE,
)

DEPENDENCY_FILES: frozenset[str] = frozenset({
    "requirements.txt",
    "requirements-dev.txt",
    "requirements-prod.txt",
    "Pipfile",
    "pyproject.toml",
    "setup.py",
    "setup.cfg",
    "package.json",
    "Cargo.toml",
    "go.mod",
    "Gemfile",
    "pom.xml",
    "build.gradle",
})

# Complexity thresholds
FILE_SIZE_HIGH_THRESHOLD = 300
FILE_SIZE_CRITICAL_THRESHOLD = 500
NESTING_CRITICAL_THRESHOLD = 6
CHUNK_COUNT_CRITICAL = 20

# Version pin pattern: ==1.0.0 or ===1.0.0
PINNED_VERSION_PATTERN = re.compile(
    r"(?:==|===)\s*(\d+)\.(\d+)\.\d+",
)

# Requirement line pattern: package==version
REQUIREMENT_LINE_PATTERN = re.compile(
    r"^([a-zA-Z0-9_-]+)\s*(?:[<>=!~]+\s*(\d+(?:\.\d+)*))",
    re.MULTILINE,
)


# --- Helper functions ---


def _scan_todos_fixmes(chunks: list[CodeChunk]) -> tuple[dict[str, Any], ...]:
    """Scan chunk contents for TODO/FIXME/HACK/XXX comments."""
    findings: list[dict[str, Any]] = []

    for chunk in chunks:
        for match in TODO_PATTERN.finditer(chunk.content):
            line_offset = chunk.content[: match.start()].count("\n")
            findings.append({
                "type": match.group(1).upper(),
                "text": match.group(2).strip(),
                "file": chunk.file_path,
                "line": chunk.start_line + line_offset,
                "chunk_id": chunk.chunk_id,
            })

    return tuple(findings)


def _estimate_nesting_depth(content: str) -> int:
    """Estimate maximum nesting depth from indentation."""
    max_depth = 0
    for line in content.splitlines():
        stripped = line.lstrip()
        if not stripped or stripped.startswith("#"):
            continue
        leading = len(line) - len(stripped)
        # Detect indent unit
        if "\t" in line[:leading] if leading > 0 else False:
            depth = line[:leading].count("\t")
        else:
            depth = leading // 4
        if depth > max_depth:
            max_depth = depth
    return max_depth


def _calculate_complexity_metrics(
    chunks: list[CodeChunk],
) -> tuple[TechDebtCategory, ...]:
    """Calculate complexity and file size categories from chunks."""
    if not chunks:
        return ()

    # Group chunks by file
    file_chunks: dict[str, list[CodeChunk]] = defaultdict(list)
    for chunk in chunks:
        file_chunks[chunk.file_path].append(chunk)

    complexity_findings: list[dict[str, Any]] = []
    size_findings: list[dict[str, Any]] = []
    total_complexity_score = 0.0
    total_size_score = 0.0

    for file_path, file_file_chunks in sorted(file_chunks.items()):
        # Calculate total lines for the file
        total_lines = max(
            (c.end_line for c in file_file_chunks), default=0
        )
        chunk_count = len(file_file_chunks)

        # Nesting depth
        max_depth = max(
            (_estimate_nesting_depth(c.content) for c in file_file_chunks),
            default=0,
        )

        # Complexity score: weighted combination
        depth_score = min(100.0, (max_depth / NESTING_CRITICAL_THRESHOLD) * 100)
        density_score = min(100.0, (chunk_count / CHUNK_COUNT_CRITICAL) * 100)
        file_complexity = (depth_score * 0.6 + density_score * 0.4)

        # Size score
        file_size_score = min(100.0, (total_lines / FILE_SIZE_CRITICAL_THRESHOLD) * 100)

        total_complexity_score += file_complexity
        total_size_score += file_size_score

        complexity_findings.append({
            "file": file_path,
            "lines": total_lines,
            "nesting_depth": max_depth,
            "chunk_count": chunk_count,
            "score": round(file_complexity, 1),
        })

        if total_lines > FILE_SIZE_HIGH_THRESHOLD:
            size_findings.append({
                "file": file_path,
                "lines": total_lines,
                "score": round(file_size_score, 1),
            })

    file_count = len(file_chunks)
    avg_complexity = total_complexity_score / file_count if file_count else 0
    avg_size = total_size_score / file_count if file_count else 0

    complexity_category = TechDebtCategory(
        name="Complexity",
        score=round(avg_complexity, 1),
        findings=tuple(sorted(complexity_findings, key=lambda f: f["score"], reverse=True)[:20]),
        severity=_determine_severity(avg_complexity),
    )

    size_category = TechDebtCategory(
        name="File Size",
        score=round(avg_size, 1),
        findings=tuple(sorted(size_findings, key=lambda f: f["score"], reverse=True)[:20]),
        severity=_determine_severity(avg_size),
    )

    return (complexity_category, size_category)


def _scan_dependency_files(
    chunks: list[CodeChunk],
) -> tuple[dict[str, str], ...]:
    """Scan for dependency manifest files and extract pinned versions."""
    dep_files: dict[str, str] = {}

    for chunk in chunks:
        basename = chunk.file_path.split("/")[-1]
        if basename not in DEPENDENCY_FILES:
            continue

        # Extract package==version patterns
        for match in REQUIREMENT_LINE_PATTERN.finditer(chunk.content):
            package = match.group(1)
            version = match.group(2)
            if version:
                key = f"{chunk.file_path}:{package}"
                dep_files[key] = version

    # Check for very old pinned versions (major version <= 1, minor < 5)
    outdated: list[dict[str, str]] = []
    for key, version in dep_files.items():
        pinned = PINNED_VERSION_PATTERN.search(f"=={version}")
        if pinned:
            major = int(pinned.group(1))
            minor = int(pinned.group(2))
            if major == 0 or (major == 1 and minor < 5):
                file_path, package = key.rsplit(":", 1)
                outdated.append({
                    "file": file_path,
                    "package": package,
                    "version": version,
                    "reason": f"pinned to old version {version}",
                })

    return tuple(outdated)


def _calculate_todo_score(todo_count: int, chunk_count: int) -> float:
    """Calculate a 0-100 score based on TODO density."""
    if todo_count == 0:
        return 0.0
    return min(100.0, (todo_count / max(1, chunk_count)) * 50)


def _determine_severity(score: float) -> str:
    """Map a 0-100 score to a severity label."""
    if score >= 75:
        return "critical"
    if score >= 50:
        return "high"
    if score >= 25:
        return "medium"
    return "low"


def _generate_summary(
    overall: float,
    categories: tuple[TechDebtCategory, ...],
    todos_fixmes: tuple[dict[str, Any], ...],
    outdated_deps: tuple[dict[str, str], ...],
    manifest: RepoManifest | None,
) -> str:
    """Generate a markdown summary of the tech debt report."""
    severity = _determine_severity(overall)
    total_files = manifest.total_files if manifest else 0
    lang_count = len(manifest.languages) if manifest else 0

    lines = [
        "# Technical Debt Report",
        "",
        f"**Overall Score: {overall}/100** ({severity})",
        "",
        f"Analyzed {total_files} files across {lang_count} language{'s' if lang_count != 1 else ''}.",
        "",
        "## Categories",
        "",
    ]

    for cat in categories:
        lines.append(f"### {cat.name} — {cat.score}/100 ({cat.severity})")
        lines.append("")
        if cat.findings:
            for finding in cat.findings[:5]:
                if "file" in finding:
                    lines.append(f"- **{finding['file']}**: score {finding.get('score', 'N/A')}")
                else:
                    lines.append(f"- {finding}")
        else:
            lines.append("- No issues found.")
        lines.append("")

    if todos_fixmes:
        lines.append(f"## TODOs & FIXMEs ({len(todos_fixmes)})")
        lines.append("")
        for todo in todos_fixmes[:10]:
            lines.append(
                f"- [{todo['type']}] {todo['text']} ({todo['file']}:{todo['line']})"
            )
        lines.append("")

    if outdated_deps:
        lines.append(f"## Outdated Dependencies ({len(outdated_deps)})")
        lines.append("")
        for dep in outdated_deps[:10]:
            lines.append(
                f"- **{dep['package']}** {dep['version']} in {dep['file']} — {dep['reason']}"
            )
        lines.append("")

    return "\n".join(lines)


# --- Agent function ---


def tech_debt_analyzer(state: GrimoireState) -> GrimoireState:
    """LangGraph node function for the TechDebtAnalyzerAgent.

    Scans code chunks for technical debt: TODOs, complexity, file sizes,
    and outdated dependencies.

    Args:
        state: Current pipeline state. Must contain ``chunks``.

    Returns:
        Updated state with ``tech_debt_report``, updated ``status``,
        and agent log.
    """
    job_id = state["job_id"]
    chunks = state.get("chunks", [])
    manifest = state.get("repo_manifest")

    log_entry = AgentLog(
        agent=AgentName.TECH_DEBT_ANALYZER,
        status=AgentStatus.RUNNING,
        started_at=datetime.now(timezone.utc).timestamp(),
    )

    logger.info("[%s] Starting tech debt analysis", job_id)

    if not chunks:
        failed_log = AgentLog(
            agent=AgentName.TECH_DEBT_ANALYZER,
            status=AgentStatus.FAILED,
            started_at=log_entry.started_at,
            completed_at=datetime.now(timezone.utc).timestamp(),
            error="No chunks in state",
        )
        return {
            **state,
            "status": PipelineStatus.FAILED,
            "error_message": "TechDebtAnalyzerAgent failed: no chunks",
            "agent_logs": state.get("agent_logs", []) + [failed_log],
        }

    try:
        # Scan for TODOs/FIXMEs
        todos_fixmes = _scan_todos_fixmes(chunks)

        # Calculate complexity metrics
        complexity_categories = _calculate_complexity_metrics(chunks)

        # Scan dependency files
        outdated_deps = _scan_dependency_files(chunks)

        # Build TODO category
        todo_score = _calculate_todo_score(len(todos_fixmes), len(chunks))
        todo_findings = tuple(
            {
                "type": t["type"],
                "text": t["text"],
                "file": t["file"],
                "line": t["line"],
            }
            for t in todos_fixmes[:20]
        )
        todo_category = TechDebtCategory(
            name="TODOs & FIXMEs",
            score=round(todo_score, 1),
            findings=todo_findings,
            severity=_determine_severity(todo_score),
        )

        # Combine all categories
        all_categories = complexity_categories + (todo_category,)

        # Calculate overall score (weighted average)
        if all_categories:
            overall = sum(c.score for c in all_categories) / len(all_categories)
        else:
            overall = 0.0
        overall = round(overall, 1)

        # Generate summary before constructing frozen dataclass
        summary = _generate_summary(
            overall, all_categories, todos_fixmes, outdated_deps, manifest
        )

        report = TechDebtReport(
            overall_score=overall,
            categories=all_categories,
            outdated_dependencies=outdated_deps,
            todos_fixmes=todos_fixmes,
            summary_markdown=summary,
        )

        logger.info(
            "[%s] Tech debt analysis complete: overall_score=%.1f, %d categories",
            job_id,
            report.overall_score,
            len(report.categories),
        )

        completed_log = AgentLog(
            agent=AgentName.TECH_DEBT_ANALYZER,
            status=AgentStatus.COMPLETED,
            started_at=log_entry.started_at,
            completed_at=datetime.now(timezone.utc).timestamp(),
        )

        return {
            **state,
            "status": PipelineStatus.ANALYZING_DEBT,
            "tech_debt_report": report,
            "current_agent": AgentName.TECH_DEBT_ANALYZER,
            "agent_logs": state.get("agent_logs", []) + [completed_log],
        }

    except Exception as e:
        logger.error("[%s] Tech debt analysis failed: %s", job_id, e)
        failed_log = AgentLog(
            agent=AgentName.TECH_DEBT_ANALYZER,
            status=AgentStatus.FAILED,
            started_at=log_entry.started_at,
            completed_at=datetime.now(timezone.utc).timestamp(),
            error=str(e),
        )
        return {
            **state,
            "status": PipelineStatus.FAILED,
            "error_message": f"TechDebtAnalyzerAgent failed: {e}",
            "agent_logs": state.get("agent_logs", []) + [failed_log],
        }


# --- Conditional edge ---


def should_continue_after_debt_analysis(state: GrimoireState) -> str:
    """Conditional edge after TechDebtAnalyzerAgent.

    Routes to:
    - ``"end"`` if analysis failed
    - ``"end"`` if no tech debt report produced
    - ``"qa_ready"`` on success
    """
    if state.get("status") == PipelineStatus.FAILED:
        return "end"

    report = state.get("tech_debt_report")
    if report is None:
        return "end"

    return "qa_ready"

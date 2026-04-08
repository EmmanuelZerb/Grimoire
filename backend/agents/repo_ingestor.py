"""Grimoire — RepoIngestorAgent.

Clones a GitHub repository, walks its filesystem, detects languages,
and extracts metadata. Produces a RepoManifest for downstream agents.

This is Agent 1 in the LangGraph pipeline.
"""

from __future__ import annotations

import logging
import os
import re
import shutil
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from git import Repo

from graph.state import (
    AgentLog,
    AgentName,
    AgentStatus,
    Contributor,
    GrimoireState,
    LanguageStats,
    PipelineStatus,
    RepoManifest,
)

logger = logging.getLogger(__name__)

# Directories and files to skip during analysis
SKIP_DIRS = frozenset({
    ".git", "__pycache__", "node_modules", ".venv", "venv",
    "env", ".env", ".tox", ".mypy_cache", ".pytest_cache",
    ".ruff_cache", "dist", "build", "*.egg-info", ".next",
    "target", ".gradle", ".idea", ".vscode", "coverage",
    "htmlcov", ".nyc_output", ".terraform", ".serverless",
})

SKIP_FILES = frozenset({
    ".DS_Store", "Thumbs.db", ".gitkeep", ".gitignore",
    "*.pyc", "*.pyo", "*.so", "*.dylib", "*.dll",
    "*.min.js", "*.min.css", "*.map", "*.lock",
    "package-lock.json", "yarn.lock", "pnpm-lock.yaml",
})

# Map file extensions to language names
EXTENSION_TO_LANGUAGE: dict[str, str] = {
    ".py": "Python",
    ".js": "JavaScript",
    ".jsx": "JavaScript (JSX)",
    ".ts": "TypeScript",
    ".tsx": "TypeScript (TSX)",
    ".java": "Java",
    ".go": "Go",
    ".rs": "Rust",
    ".rb": "Ruby",
    ".php": "PHP",
    ".swift": "Swift",
    ".kt": "Kotlin",
    ".kts": "Kotlin",
    ".c": "C",
    ".h": "C",
    ".cpp": "C++",
    ".hpp": "C++",
    ".cc": "C++",
    ".cs": "C#",
    ".scala": "Scala",
    ".r": "R",
    ".R": "R",
    ".lua": "Lua",
    ".zig": "Zig",
    ".nim": "Nim",
    ".dart": "Dart",
    ".ex": "Elixir",
    ".exs": "Elixir",
    ".erl": "Erlang",
    ".hs": "Haskell",
    ".ml": "OCaml",
    ".sql": "SQL",
    ".sh": "Shell",
    ".bash": "Shell",
    ".zsh": "Shell",
    ".ps1": "PowerShell",
    ".html": "HTML",
    ".css": "CSS",
    ".scss": "SCSS",
    ".less": "Less",
    ".vue": "Vue",
    ".svelte": "Svelte",
    ".yaml": "YAML",
    ".yml": "YAML",
    ".json": "JSON",
    ".toml": "TOML",
    ".xml": "XML",
    ".md": "Markdown",
    ".rst": "reStructuredText",
    ".tex": "LaTeX",
    ".proto": "Protocol Buffers",
    ".graphql": "GraphQL",
    ".tf": "HCL",
}

# Extensions considered as "code" (not config/docs)
CODE_EXTENSIONS = frozenset({
    ".py", ".js", ".jsx", ".ts", ".tsx", ".java", ".go", ".rs",
    ".rb", ".php", ".swift", ".kt", ".kts", ".c", ".cpp", ".hpp",
    ".cc", ".cs", ".scala", ".r", ".R", ".lua", ".zig", ".nim",
    ".dart", ".ex", ".exs", ".erl", ".hs", ".ml", ".sql",
    ".sh", ".bash", ".zsh", ".ps1", ".vue", ".svelte",
})

# Regex patterns for files without standard extensions
SHEBANG_LANGUAGE: dict[re.Pattern, str] = {
    re.compile(r"^#!.*python"): "Python",
    re.compile(r"^#!.*node"): "JavaScript",
    re.compile(r"^#!.*bash"): "Shell",
    re.compile(r"^#!.*sh\b"): "Shell",
    re.compile(r"^#!.*ruby"): "Ruby",
    re.compile(r"^#!.*perl"): "Perl",
}


def _is_skipped_dir(dir_name: str) -> bool:
    """Check if a directory should be skipped."""
    return dir_name in SKIP_DIRS


def _is_skipped_file(file_name: str) -> bool:
    """Check if a file should be skipped."""
    # Check exact match
    if file_name in SKIP_FILES:
        return True
    # Check extension patterns
    for pattern in SKIP_FILES:
        if pattern.startswith("*.") and file_name.endswith(pattern[1:]):
            return True
    return False


def _detect_language(file_path: Path) -> str | None:
    """Detect the programming language of a file."""
    ext = file_path.suffix.lower()
    if ext in EXTENSION_TO_LANGUAGE:
        return EXTENSION_TO_LANGUAGE[ext]

    # Try shebang detection for files without standard extensions
    if not ext or ext in {".env", ".local"}:
        try:
            first_line = file_path.read_text(encoding="utf-8", errors="ignore").split("\n")[0]
            for pattern, language in SHEBANG_LANGUAGE.items():
                if pattern.match(first_line):
                    return language
        except (OSError, IndexError):
            pass

    return None


def _build_directory_tree(root_path: Path, max_depth: int = 4) -> dict[str, Any]:
    """Build a nested dict representing the directory structure."""
    tree: dict[str, Any] = {}

    try:
        entries = sorted(root_path.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
    except PermissionError:
        return tree

    for entry in entries:
        if _is_skipped_dir(entry.name) or _is_skipped_file(entry.name):
            continue
        if entry.name.startswith("."):
            continue

        if entry.is_dir() and max_depth > 1:
            children = _build_directory_tree(entry, max_depth - 1)
            if children:
                tree[entry.name] = children
        elif entry.is_file():
            tree[entry.name] = None

    return tree


def _extract_contributors(repo: Repo, limit: int = 20) -> tuple[Contributor, ...]:
    """Extract contributor information from git log."""
    contributor_data: dict[str, dict[str, Any]] = {}

    for commit in repo.iter_commits(max_count=500):
        author_name = commit.author.name
        email = commit.author.email
        key = f"{author_name}|{email}"

        if key not in contributor_data:
            contributor_data[key] = {
                "name": author_name,
                "email": email,
                "commit_count": 0,
            }
        contributor_data[key]["commit_count"] += 1

    sorted_contributors = sorted(
        contributor_data.values(), key=lambda c: c["commit_count"], reverse=True
    )[:limit]

    return tuple(
        Contributor(
            name=c["name"],
            email=c["email"],
            commit_count=c["commit_count"],
        )
        for c in sorted_contributors
    )


def _extract_last_commits(repo: Repo, limit: int = 10) -> tuple[dict[str, Any], ...]:
    """Extract the most recent commits."""
    commits: list[dict[str, Any]] = []

    for commit in repo.iter_commits(max_count=limit):
        commits.append({
            "hash": commit.hexsha[:8],
            "message": commit.message.strip().split("\n")[0],
            "author": commit.author.name,
            "date": datetime.fromtimestamp(
                commit.committed_date, tz=timezone.utc
            ).isoformat(),
        })

    return tuple(commits)


def _walk_and_analyze(repo_path: Path) -> tuple[Counter, int, int]:
    """Walk the repo and count languages, files, and lines."""
    language_files: Counter = Counter()
    language_lines: Counter = Counter()
    total_files = 0
    total_lines = 0

    for file_path in repo_path.rglob("*"):
        if not file_path.is_file():
            continue

        relative = file_path.relative_to(repo_path)
        parts = relative.parts

        # Skip directories
        if any(_is_skipped_dir(p) for p in parts):
            continue
        if any(p.startswith(".") for p in parts[:-1]):
            continue

        # Skip files
        if _is_skipped_file(file_path.name):
            continue

        language = _detect_language(file_path)
        if language is None:
            continue

        try:
            line_count = sum(1 for _ in file_path.read_text(encoding="utf-8", errors="ignore").splitlines())
        except OSError:
            line_count = 0

        language_files[language] += 1
        language_lines[language] += line_count
        total_files += 1
        total_lines += line_count

    return language_files, language_lines, total_files, total_lines


def _build_language_stats(
    language_files: Counter,
    language_lines: Counter,
) -> tuple[LanguageStats, ...]:
    """Build LanguageStats from counters."""
    lang_to_extensions: dict[str, set[str]] = {}
    for ext, lang in EXTENSION_TO_LANGUAGE.items():
        if lang not in lang_to_extensions:
            lang_to_extensions[lang] = set()
        lang_to_extensions[lang].add(ext)

    stats = []
    for language in language_files:
        exts = lang_to_extensions.get(language, frozenset())
        stats.append(LanguageStats(
            name=language,
            file_count=language_files[language],
            total_lines=language_lines[language],
            extensions=tuple(sorted(exts)),
        ))

    return tuple(sorted(stats, key=lambda s: s.total_lines, reverse=True))


def _read_readme(repo_path: Path) -> str | None:
    """Try to read the project README file."""
    for name in ("README.md", "README.rst", "README.txt", "README"):
        candidate = repo_path / name
        if candidate.is_file():
            try:
                return candidate.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                return None
    return None


def _detect_architectural_patterns(repo_path: Path) -> tuple[str, ...]:
    """Detect architectural patterns from directory structure.

    Checks both top-level and one level deep (e.g. src/) so that
    repos like ``src/models``, ``src/views``, ``src/controllers``
    are still recognised.
    """
    patterns: list[str] = []
    top_dirs = {d.name for d in repo_path.iterdir() if d.is_dir()}
    top_files = {f.name for f in repo_path.iterdir() if f.is_file()}

    # Also collect dirs inside src/, app/, backend/, frontend/ if they exist
    inner_dirs: set[str] = set()
    for scope in ("src", "app", "backend", "frontend"):
        scope_path = repo_path / scope
        if scope_path.is_dir():
            for d in scope_path.iterdir():
                if d.is_dir():
                    inner_dirs.add(d.name)

    all_dirs = top_dirs | inner_dirs

    # MVC pattern
    if {"models", "views", "controllers"}.issubset(all_dirs) or \
       {"model", "view", "controller"}.issubset(all_dirs):
        patterns.append("MVC")

    # Layered architecture
    if {"controllers", "services", "repositories"}.issubset(all_dirs) or \
       {"routes", "services", "models"}.issubset(all_dirs) or \
       {"handlers", "services", "repositories"}.issubset(all_dirs):
        patterns.append("Layered")

    # Hexagonal / Ports & Adapters
    if {"ports", "adapters"}.issubset(all_dirs) or \
       {"domain", "infrastructure", "application"}.issubset(all_dirs):
        patterns.append("Hexagonal")

    # Microservices-like
    services = [d for d in all_dirs if "service" in d.lower()]
    if len(services) >= 2:
        patterns.append("Microservices-like")

    # Monorepo / packages
    if "packages" in top_dirs or "libs" in top_dirs:
        patterns.append("Monorepo")

    # API structure
    if {"api", "routes", "middleware"}.issubset(all_dirs) or \
       {"api", "controllers"}.issubset(all_dirs):
        patterns.append("API")

    # Frontend SPA
    if {"components", "hooks", "pages"}.issubset(all_dirs) or \
       {"components", "hooks", "views"}.issubset(all_dirs) or \
       ("src" in top_dirs and "components" in inner_dirs and "public" in top_dirs):
        patterns.append("Frontend SPA")

    # Django
    if "manage.py" in top_files and "settings" in top_dirs:
        patterns.append("Django")

    # Next.js
    if any(f.name.startswith("next.config") for f in repo_path.iterdir() if f.is_file()):
        patterns.append("Next.js")

    # React app (Create React App / Vite)
    if ("package.json" in top_files and "components" in inner_dirs) or \
       {"components", "assets"}.issubset(inner_dirs):
        if "Frontend SPA" not in patterns:
            patterns.append("React App")

    # FastAPI / Flask backend
    if {"api", "core", "models"}.issubset(all_dirs) or \
       {"routes", "models", "schemas"}.issubset(all_dirs):
        patterns.append("API Backend")

    return tuple(patterns)


def repo_ingestor(state: GrimoireState) -> GrimoireState:
    """LangGraph node function for the RepoIngestorAgent.

    Clones the repo, walks the filesystem, detects languages,
    and produces a RepoManifest.

    Args:
        state: Current pipeline state. Must contain `github_url` and `job_id`.

    Returns:
        Updated state with `repo_manifest`, updated `status`, and agent log.
    """
    github_url = state["github_url"]
    job_id = state["job_id"]
    clone_dir = Path(f"./data/repos/{job_id}")

    log_entry = AgentLog(
        agent=AgentName.REPO_INGESTOR,
        status=AgentStatus.RUNNING,
        started_at=datetime.now(timezone.utc).timestamp(),
    )

    logger.info("[%s] Starting repo ingestion for: %s", job_id, github_url)

    try:
        # Clone the repository
        if clone_dir.exists():
            shutil.rmtree(clone_dir)

        clone_dir.parent.mkdir(parents=True, exist_ok=True)

        # Disable git's clone protection so repos with post-checkout hooks don't fail
        prev = os.environ.get("GIT_CLONE_PROTECTION_ACTIVE")
        os.environ["GIT_CLONE_PROTECTION_ACTIVE"] = "false"
        try:
            Repo.clone_from(github_url, clone_dir, depth=50)
        finally:
            if prev is None:
                os.environ.pop("GIT_CLONE_PROTECTION_ACTIVE", None)
            else:
                os.environ["GIT_CLONE_PROTECTION_ACTIVE"] = prev
        logger.info("[%s] Repository cloned to: %s", job_id, clone_dir)

        # Open for analysis
        repo = Repo(clone_dir)

        # Walk and analyze
        language_files, language_lines, total_files, total_lines = _walk_and_analyze(clone_dir)
        language_stats = _build_language_stats(language_files, language_lines)
        contributors = _extract_contributors(repo)
        last_commits = _extract_last_commits(repo)
        directory_tree = _build_directory_tree(clone_dir)
        detected_patterns = _detect_architectural_patterns(clone_dir)

        # Try to read the project README
        readme_content = _read_readme(clone_dir)

        # Extract repo name from URL
        repo_name = github_url.rstrip("/").split("/")[-1].removesuffix(".git")

        manifest = RepoManifest(
            repo_name=repo_name,
            repo_url=github_url,
            clone_path=str(clone_dir),
            total_files=total_files,
            total_lines=total_lines,
            languages=language_stats,
            contributors=contributors,
            last_commits=last_commits,
            directory_tree=directory_tree,
            detected_patterns=detected_patterns,
        )

        logger.info(
            "[%s] Ingestion complete: %d files, %d lines, %d languages",
            job_id, total_files, total_lines, len(language_stats),
        )

        completed_log = AgentLog(
            agent=AgentName.REPO_INGESTOR,
            status=AgentStatus.COMPLETED,
            started_at=log_entry.started_at,
            completed_at=datetime.now(timezone.utc).timestamp(),
        )

        return {
            **state,
            "status": PipelineStatus.INGESTING,
            "repo_manifest": manifest,
            "readme_content": readme_content,
            "agent_logs": state.get("agent_logs", []) + [completed_log],
        }

    except Exception as e:
        logger.error("[%s] Repo ingestion failed: %s", job_id, e)
        failed_log = AgentLog(
            agent=AgentName.REPO_INGESTOR,
            status=AgentStatus.FAILED,
            started_at=log_entry.started_at,
            completed_at=datetime.now(timezone.utc).timestamp(),
            error=str(e),
        )

        return {
            **state,
            "status": PipelineStatus.FAILED,
            "error_message": f"RepoIngestorAgent failed: {e}",
            "agent_logs": state.get("agent_logs", []) + [failed_log],
        }

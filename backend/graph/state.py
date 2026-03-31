"""Grimoire — LangGraph StateGraph state definition.

Central TypedDict that flows through all 5 agents in the pipeline.
Every agent reads from and writes to this state.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, TypedDict


class PipelineStatus(str, Enum):
    """Status of the overall analysis pipeline."""

    IDLE = "idle"
    INGESTING = "ingesting"
    CHUNKING = "chunking"
    MAPPING = "mapping"
    ANALYZING_DEBT = "analyzing_debt"
    QA_READY = "qa_ready"
    COMPLETED = "completed"
    FAILED = "failed"


class AgentName(str, Enum):
    """Identifiers for each agent in the pipeline."""

    REPO_INGESTOR = "repo_ingestor"
    CODE_CHUNKER = "code_chunker"
    ARCHITECTURE_MAPPER = "architecture_mapper"
    TECH_DEBT_ANALYZER = "tech_debt_analyzer"
    QA_INTERFACE = "qa_interface"


class AgentStatus(str, Enum):
    """Status of an individual agent execution."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass(frozen=True)
class LanguageStats:
    """Statistics for a single programming language detected in the repo."""

    name: str
    file_count: int
    total_lines: int
    extensions: tuple[str, ...]


@dataclass(frozen=True)
class Contributor:
    """A contributor extracted from git history."""

    name: str
    email: str
    commit_count: int


@dataclass(frozen=True)
class RepoManifest:
    """Structured output from the RepoIngestorAgent.

    Contains everything needed to understand what we're analyzing.
    """

    repo_name: str
    repo_url: str
    clone_path: str
    total_files: int
    total_lines: int
    languages: tuple[LanguageStats, ...]
    contributors: tuple[Contributor, ...]
    last_commits: tuple[dict[str, Any], ...]
    directory_tree: dict[str, Any]
    detected_patterns: tuple[str, ...]


@dataclass(frozen=True)
class CodeChunk:
    """A single chunk of code extracted by the CodeChunkerAgent."""

    chunk_id: str
    content: str
    file_path: str
    start_line: int
    end_line: int
    language: str
    node_type: str  # function, class, import, export, etc.
    name: str
    dependencies: tuple[str, ...]
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class DependencyEdge:
    """An edge in the dependency graph."""

    source: str
    target: str
    edge_type: str  # import, export, call, etc.


@dataclass(frozen=True)
class ArchitectureReport:
    """Output from the ArchitectureMapperAgent."""

    dependency_graph: dict[str, list[str]]
    entry_points: tuple[str, ...]
    core_modules: tuple[str, ...]
    orphan_modules: tuple[str, ...]
    dependency_cycles: tuple[tuple[str, ...], ...]
    detected_pattern: str  # MVC, layered, microservices-like, monolith
    mermaid_diagram: str
    module_descriptions: dict[str, str]


@dataclass(frozen=True)
class TechDebtCategory:
    """A single category of technical debt."""

    name: str
    score: float  # 0-100
    findings: tuple[dict[str, Any], ...]
    severity: str  # low, medium, high, critical


@dataclass(frozen=True)
class TechDebtReport:
    """Output from the TechDebtAnalyzerAgent."""

    overall_score: float  # 0-100 (100 = worst debt)
    categories: tuple[TechDebtCategory, ...]
    outdated_dependencies: tuple[dict[str, str], ...]
    todos_fixmes: tuple[dict[str, Any], ...]
    summary_markdown: str


@dataclass(frozen=True)
class QAMessage:
    """A single Q&A exchange."""

    question: str
    answer: str
    sources: tuple[dict[str, Any], ...]
    timestamp: float


@dataclass(frozen=True)
class AgentLog:
    """Execution log for a single agent run."""

    agent: AgentName
    status: AgentStatus
    started_at: float | None = None
    completed_at: float | None = None
    tokens_used: int = 0
    error: str | None = None


class GrimoireState(TypedDict, total=False):
    """The complete state that flows through the LangGraph pipeline.

    Every agent reads from this state and writes its results back.
    The orchestrator uses this to decide which agent to run next.
    """

    # --- Input ---
    job_id: str
    github_url: str

    # --- Pipeline control ---
    status: PipelineStatus
    current_agent: AgentName
    error_message: str | None

    # --- Agent 1: RepoIngestor ---
    repo_manifest: RepoManifest | None

    # --- Agent 2: CodeChunker ---
    chunks: list[CodeChunk]
    total_chunks: int

    # --- Agent 3: ArchitectureMapper ---
    architecture_report: ArchitectureReport | None

    # --- Agent 4: TechDebtAnalyzer ---
    tech_debt_report: TechDebtReport | None

    # --- Agent 5: QA Interface ---
    qa_history: list[QAMessage]

    # --- Observability ---
    agent_logs: list[AgentLog]
    total_tokens_used: int
    started_at: float | None
    completed_at: float | None

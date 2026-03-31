"""Grimoire — LangGraph StateGraph orchestrator.

Wires all 5 agents into a single pipeline with conditional edges.
Phase 1: Only RepoIngestorAgent is active.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from langgraph.graph import END, START, StateGraph

from agents.repo_ingestor import repo_ingestor
from graph.state import AgentName, GrimoireState, PipelineStatus


def _should_continue_after_ingestion(state: GrimoireState) -> str:
    """Conditional edge after RepoIngestorAgent.

    Routes to:
    - END if ingestion failed (early exit with error)
    - "chunker" if ingestion succeeded and repo has files
    - END if repo is empty (nothing to analyze)
    """
    if state.get("status") == PipelineStatus.FAILED:
        return "end"

    manifest = state.get("repo_manifest")
    if manifest is None:
        return "end"

    if manifest.total_files == 0:
        return "end"

    # Phase 1: only ingestion is implemented
    # Future phases will route to "chunker"
    return "end"


def build_pipeline() -> StateGraph:
    """Build the complete LangGraph pipeline.

    Phase 1 graph:
        START → repo_ingestor → (conditional) → END

    Future phases will add:
        chunker → architecture_mapper → tech_debt_analyzer → qa_ready → END
    """
    graph = StateGraph(GrimoireState)

    # Add nodes (one per agent)
    graph.add_node("repo_ingestor", repo_ingestor)

    # Future phases:
    # graph.add_node("chunker", code_chunker)
    # graph.add_node("architecture_mapper", architecture_mapper)
    # graph.add_node("tech_debt_analyzer", tech_debt_analyzer)
    # graph.add_node("qa_ready", qa_interface)

    # Add edges
    graph.add_edge(START, "repo_ingestor")
    graph.add_conditional_edges(
        "repo_ingestor",
        _should_continue_after_ingestion,
        {
            "end": END,
        },
    )

    return graph.compile()


def create_initial_state(github_url: str) -> GrimoireState:
    """Create the initial state for a new analysis job.

    Args:
        github_url: The GitHub repository URL to analyze.

    Returns:
        Fresh GrimoireState ready to be fed into the pipeline.
    """
    return {
        "job_id": uuid.uuid4().hex[:12],
        "github_url": github_url,
        "status": PipelineStatus.IDLE,
        "current_agent": AgentName.REPO_INGESTOR,
        "error_message": None,
        "repo_manifest": None,
        "chunks": [],
        "total_chunks": 0,
        "architecture_report": None,
        "tech_debt_report": None,
        "qa_history": [],
        "agent_logs": [],
        "total_tokens_used": 0,
        "started_at": datetime.now(timezone.utc).timestamp(),
        "completed_at": None,
    }

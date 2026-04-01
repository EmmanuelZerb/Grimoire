"""Grimoire — QAInterfaceAgent.

Minimal state transition marker that sets the pipeline status
to QA_READY, indicating the analysis is complete and ready
for interactive Q&A.

This is Agent 5 in the LangGraph pipeline.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from graph.state import (
    AgentLog,
    AgentName,
    AgentStatus,
    GrimoireState,
    PipelineStatus,
)

logger = logging.getLogger(__name__)


def qa_interface(state: GrimoireState) -> GrimoireState:
    """LangGraph node function for the QAInterfaceAgent.

    Marks the pipeline as ready for interactive Q&A.
    The actual Q&A logic lives in the API routes.

    Args:
        state: Current pipeline state.

    Returns:
        Updated state with ``status`` set to ``QA_READY`` and a completed
        agent log.
    """
    job_id = state["job_id"]

    log_entry = AgentLog(
        agent=AgentName.QA_INTERFACE,
        status=AgentStatus.RUNNING,
        started_at=datetime.now(timezone.utc).timestamp(),
    )

    logger.info("[%s] QA interface ready", job_id)

    completed_log = AgentLog(
        agent=AgentName.QA_INTERFACE,
        status=AgentStatus.COMPLETED,
        started_at=log_entry.started_at,
        completed_at=datetime.now(timezone.utc).timestamp(),
    )

    return {
        **state,
        "status": PipelineStatus.QA_READY,
        "current_agent": AgentName.QA_INTERFACE,
        "qa_history": state.get("qa_history", []),
        "agent_logs": state.get("agent_logs", []) + [completed_log],
    }


def should_continue_after_qa(state: GrimoireState) -> str:
    """Conditional edge after QAInterfaceAgent.

    QA is the final agent — always routes to END.
    """
    return "end"

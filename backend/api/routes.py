"""Grimoire — API routes.

Phase 1: Minimal endpoints. Full SSE + analysis in Phase 6.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel, HttpUrl

from graph.orchestrator import build_pipeline, create_initial_state

router = APIRouter()

# In-memory job storage (Phase 1 — will move to proper storage later)
_jobs: dict[str, dict] = {}
_analysis_lock = asyncio.Lock()


class AnalyzeRequest(BaseModel):
    github_url: HttpUrl


class AnalyzeResponse(BaseModel):
    job_id: str
    github_url: str
    status: str


class StatusResponse(BaseModel):
    job_id: str
    status: str
    current_step: str | None = None
    error: str | None = None
    completed_at: str | None = None


class ChatRequest(BaseModel):
    question: str


@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze_repo(request: AnalyzeRequest, background_tasks: BackgroundTasks):
    """Launch a full codebase analysis pipeline."""
    if _analysis_lock.locked():
        raise HTTPException(status_code=429, detail="An analysis is already running. Please wait.")

    url = str(request.github_url)
    initial_state = create_initial_state(url)
    job_id = initial_state["job_id"]

    _jobs[job_id] = {
        "state": initial_state,
        "status": "queued",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    background_tasks.add_task(_run_pipeline, job_id)

    return AnalyzeResponse(job_id=job_id, github_url=url, status="queued")


@router.get("/status/{job_id}", response_model=StatusResponse)
async def get_status(job_id: str):
    """Get the current status of an analysis job."""
    if job_id not in _jobs:
        raise HTTPException(status_code=404, detail="Job not found")

    job = _jobs[job_id]
    state = job["state"]

    return StatusResponse(
        job_id=job_id,
        status=state.get("status", "unknown"),
        current_step=state.get("current_agent"),
        error=state.get("error_message"),
        completed_at=(
            datetime.fromtimestamp(state["completed_at"], tz=timezone.utc).isoformat()
            if state.get("completed_at")
            else None
        ),
    )


@router.get("/report/{job_id}")
async def get_report(job_id: str):
    """Get the full analysis report for a completed job."""
    if job_id not in _jobs:
        raise HTTPException(status_code=404, detail="Job not found")

    state = _jobs[job_id]["state"]
    if state.get("status") != "completed":
        raise HTTPException(status_code=400, detail="Analysis not completed yet")

    return {
        "job_id": job_id,
        "manifest": _serialize_dataclass(state.get("repo_manifest")),
        "architecture": _serialize_dataclass(state.get("architecture_report")),
        "tech_debt": _serialize_dataclass(state.get("tech_debt_report")),
    }


@router.post("/chat/{job_id}")
async def chat(job_id: str, request: ChatRequest):
    """Q&A on an analyzed codebase. Phase 5 implementation."""
    if job_id not in _jobs:
        raise HTTPException(status_code=404, detail="Job not found")

    raise HTTPException(status_code=501, detail="Q&A not yet implemented (Phase 5)")


@router.get("/diagram/{job_id}")
async def get_diagram(job_id: str):
    """Get the Mermaid architecture diagram. Phase 3 implementation."""
    if job_id not in _jobs:
        raise HTTPException(status_code=404, detail="Job not found")

    raise HTTPException(status_code=501, detail="Diagram not yet implemented (Phase 3)")


async def _run_pipeline(job_id: str):
    """Run the full LangGraph pipeline for a job."""
    async with _analysis_lock:
        try:
            state = _jobs[job_id]["state"]
            pipeline = build_pipeline()

            # LangGraph invoke is synchronous in Phase 1
            # Future phases will use .astream() for SSE
            result = pipeline.invoke(state)

            from graph.state import PipelineStatus
            if result.get("status") != PipelineStatus.FAILED:
                result["status"] = PipelineStatus.COMPLETED
                result["completed_at"] = datetime.now(timezone.utc).timestamp()

            _jobs[job_id]["state"] = result

        except Exception as e:
            _jobs[job_id]["state"]["status"] = "failed"
            _jobs[job_id]["state"]["error_message"] = str(e)


def _serialize_dataclass(obj):
    """Convert a dataclass or tuple of dataclasses to dict/list."""
    if obj is None:
        return None
    if hasattr(obj, "__dataclass_fields__"):
        return {k: _serialize_dataclass(v) for k, v in obj.__dict__.items()}
    if isinstance(obj, tuple):
        return [_serialize_dataclass(item) for item in obj]
    if isinstance(obj, dict):
        return {k: _serialize_dataclass(v) for k, v in obj.items()}
    if isinstance(obj, (str, int, float, bool)) or obj is None:
        return obj
    return str(obj)

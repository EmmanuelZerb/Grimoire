"""Grimoire — API routes.

Endpoints for launching analysis, checking status, fetching reports,
viewing architecture diagrams, and Q&A.
"""

from __future__ import annotations

import asyncio
import threading
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel, HttpUrl

from graph.orchestrator import build_pipeline, create_initial_state
from graph.state import PipelineStatus

router = APIRouter()

# In-memory job storage (Phase 1 — will move to proper storage later)
_jobs: dict[str, dict] = {}
_analysis_lock = threading.Lock()


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


class ChatResponse(BaseModel):
    job_id: str
    question: str
    answer: str
    sources: list[dict]
    chunks_used: int


@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze_repo(request: AnalyzeRequest, background_tasks: BackgroundTasks):
    """Launch a full codebase analysis pipeline."""
    if _analysis_lock.locked():
        raise HTTPException(
            status_code=429, detail="An analysis is already running. Please wait."
        )

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
    status = state.get("status")

    if status not in (PipelineStatus.COMPLETED, PipelineStatus.QA_READY, "completed", "qa_ready"):
        raise HTTPException(status_code=400, detail="Analysis not completed yet")

    return {
        "job_id": job_id,
        "status": status,
        "manifest": _serialize_dataclass(state.get("repo_manifest")),
        "architecture": _serialize_dataclass(state.get("architecture_report")),
        "tech_debt": _serialize_dataclass(state.get("tech_debt_report")),
    }


@router.get("/diagram/{job_id}")
async def get_diagram(job_id: str):
    """Get the Mermaid architecture diagram for a completed job."""
    if job_id not in _jobs:
        raise HTTPException(status_code=404, detail="Job not found")

    state = _jobs[job_id]["state"]
    report = state.get("architecture_report")

    if report is None:
        raise HTTPException(
            status_code=400, detail="Architecture analysis not completed yet"
        )

    return {
        "job_id": job_id,
        "detected_pattern": report.detected_pattern,
        "diagram": report.mermaid_diagram,
        "dependency_graph": report.dependency_graph,
        "entry_points": report.entry_points,
        "core_modules": report.core_modules,
        "orphan_modules": report.orphan_modules,
        "dependency_cycles": report.dependency_cycles,
        "module_count": len(report.dependency_graph),
    }


@router.post("/chat/{job_id}", response_model=ChatResponse)
async def chat(job_id: str, request: ChatRequest):
    """Q&A on an analyzed codebase using RAG + Claude."""
    if job_id not in _jobs:
        raise HTTPException(status_code=404, detail="Job not found")

    state = _jobs[job_id]["state"]
    status = state.get("status")

    if status not in (PipelineStatus.COMPLETED, PipelineStatus.QA_READY, "completed", "qa_ready"):
        raise HTTPException(
            status_code=400, detail="Analysis not completed yet. Wait for the pipeline to finish."
        )

    if not request.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty")

    from core.rag import ask_question

    result = ask_question(state, request.question.strip())

    # Append to qa_history
    from graph.state import QAMessage

    qa_message = QAMessage(
        question=request.question.strip(),
        answer=result["answer"],
        sources=tuple(result["sources"]),
        timestamp=datetime.now(timezone.utc).timestamp(),
    )
    existing_history = state.get("qa_history", [])
    state["qa_history"] = list(existing_history) + [qa_message]

    return ChatResponse(
        job_id=job_id,
        question=request.question,
        answer=result["answer"],
        sources=result["sources"],
        chunks_used=result["chunks_used"],
    )


# --- README endpoints ---


class ReadmeResponse(BaseModel):
    content: str | None
    source: str | None  # "repo" | "generated" | None


@router.get("/readme/{job_id}", response_model=ReadmeResponse)
async def get_readme(job_id: str):
    """Get the README for an analyzed repo (original or generated)."""
    if job_id not in _jobs:
        raise HTTPException(status_code=404, detail="Job not found")

    state = _jobs[job_id]["state"]

    readme = state.get("readme_content")
    if readme:
        return ReadmeResponse(content=readme, source="repo")

    generated = state.get("generated_readme")
    if generated:
        return ReadmeResponse(content=generated, source="generated")

    return ReadmeResponse(content=None, source=None)


@router.post("/readme/{job_id}/generate", response_model=ReadmeResponse)
async def generate_readme(job_id: str):
    """Generate a README for an analyzed repo using the LLM."""
    if job_id not in _jobs:
        raise HTTPException(status_code=404, detail="Job not found")

    state = _jobs[job_id]["state"]
    manifest = state.get("repo_manifest")
    arch = state.get("architecture_report")

    if manifest is None:
        raise HTTPException(status_code=400, detail="Analysis not completed yet")

    # Build context for the LLM
    lang_summary = ", ".join(f"{l.name} ({l.total_lines} LOC)" for l in manifest.languages)
    contributors_summary = ", ".join(c.name for c in manifest.contributors[:5])
    arch_pattern = arch.detected_pattern if arch else "unknown"
    core_modules = ", ".join(arch.core_modules[:10]) if arch else ""
    entry_points = ", ".join(arch.entry_points[:5]) if arch else ""

    tech_debt = state.get("tech_debt_report")
    debt_summary = ""
    if tech_debt:
        debt_summary = f"Overall tech debt score: {tech_debt.overall_score}/100"

    prompt = f"""Generate a clear, professional README.md for this project.

Project: {manifest.repo_name}
Repository: {manifest.repo_url}
Languages: {lang_summary}
Total files: {manifest.total_files}
Total lines: {manifest.total_lines}
Architecture pattern: {arch_pattern}
Core modules: {core_modules}
Entry points: {entry_points}
Top contributors: {contributors_summary}
{debt_summary}

Directory structure:
```
{_dict_to_tree(manifest.directory_tree)}
```

Write the README in Markdown format. Include:
- A concise project description
- Key features
- Project structure overview
- How to get started (installation, usage)
- Tech stack / languages used
Keep it factual and based only on the information provided above. Do NOT invent features or details that aren't supported by the data."""

    import os
    from openai import OpenAI

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise HTTPException(status_code=503, detail="No OPENAI_API_KEY configured")

    client = OpenAI(api_key=api_key)

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            max_tokens=2048,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a technical writer. Generate clear, concise README files "
                        "for software projects. Write in Markdown. Be factual — only include "
                        "information that can be inferred from the project data provided."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
        )
        content = response.choices[0].message.content if response.choices else ""
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"LLM generation failed: {e}")

    state["generated_readme"] = content
    return ReadmeResponse(content=content, source="generated")


def _dict_to_tree(d: dict, prefix: str = "") -> str:
    """Convert a nested dict directory tree to a text representation."""
    lines = []
    items = list(d.items())
    for i, (name, children) in enumerate(items):
        is_last = i == len(items) - 1
        connector = "`-- " if is_last else "|-- "
        lines.append(f"{prefix}{connector}{name}")
        if children:
            extension = "    " if is_last else "|   "
            lines.append(_dict_to_tree(children, prefix + extension))
    return "\n".join(lines)


# Map each graph node name to the next agent key the frontend expects.
# Graph nodes: "repo_ingestor", "chunker", "architecture_mapper",
#              "tech_debt_analyzer", "qa_ready"
_NODE_TO_NEXT_AGENT: dict[str, str | None] = {
    "repo_ingestor": "code_chunker",
    "chunker": "architecture_mapper",
    "architecture_mapper": "tech_debt_analyzer",
    "tech_debt_analyzer": "qa_ready",
    "qa_ready": None,
}


def _run_pipeline(job_id: str):
    """Run the full LangGraph pipeline for a job.

    Uses ``stream`` so the job state is updated after each node,
    letting the frontend poll and show per-step progress.
    Runs synchronously so FastAPI BackgroundTasks places it in a
    thread pool, avoiding blocking the asyncio event loop.
    """
    with _analysis_lock:
        try:
            state = _jobs[job_id]["state"]
            pipeline = build_pipeline()

            for event in pipeline.stream(state, stream_mode="updates"):
                for node_name, updates in event.items():
                    state.update(updates)
                    # Point current_agent to the NEXT step so the
                    # frontend knows this node is done.
                    next_agent = _NODE_TO_NEXT_AGENT.get(node_name)
                    if next_agent is not None:
                        state["current_agent"] = next_agent
                    _jobs[job_id]["state"] = dict(state)

            if state.get("status") != PipelineStatus.FAILED:
                state["status"] = PipelineStatus.COMPLETED
                state["completed_at"] = datetime.now(timezone.utc).timestamp()

                # Index chunks into ChromaDB for RAG
                chunks = state.get("chunks", [])
                if chunks:
                    try:
                        from core.embeddings import index_chunks

                        indexed = index_chunks(job_id, chunks)
                        state["chunks_indexed"] = indexed
                    except Exception as e:
                        import logging

                        logging.getLogger(__name__).warning(
                            "[%s] ChromaDB indexing failed (Q&A will be limited): %s",
                            job_id,
                            e,
                        )

            _jobs[job_id]["state"] = dict(state)

        except Exception as e:
            _jobs[job_id]["state"]["status"] = PipelineStatus.FAILED
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

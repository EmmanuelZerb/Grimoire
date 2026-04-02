"""Grimoire — RAG query engine.

Uses Claude to answer questions about a codebase, grounded in
retrieved code chunks from ChromaDB.
"""

from __future__ import annotations

import logging
import os
from typing import Any

from openai import OpenAI

from core.embeddings import query_chunks
from graph.state import ArchitectureReport, GrimoireState, RepoManifest, TechDebtReport

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """\
You are Grimoire, an AI codebase intelligence assistant. You answer questions about a \
codebase based on the analysis data and retrieved code chunks provided below.

Rules:
- Answer in the same language as the question.
- Be precise and reference specific files and line numbers when relevant.
- If the retrieved chunks don't contain enough information, say so honestly.
- Keep answers concise but thorough.
- Use markdown formatting for code references and file paths.
"""


def _build_context(
    retrieved_chunks: list[dict[str, Any]],
    manifest: RepoManifest | None,
    architecture: ArchitectureReport | None,
    tech_debt: TechDebtReport | None,
) -> str:
    """Build the context string from analysis data and retrieved chunks."""
    parts: list[str] = []

    # Repo overview
    if manifest:
        lang_list = ", ".join(f"{l.name} ({l.file_count} files)" for l in manifest.languages)
        parts.append(
            f"## Repository Overview\n"
            f"- Name: {manifest.repo_name}\n"
            f"- Total files: {manifest.total_files}\n"
            f"- Total lines: {manifest.total_lines}\n"
            f"- Languages: {lang_list}\n"
            f"- Patterns: {', '.join(manifest.detected_patterns) or 'monolith'}\n"
        )

    # Architecture
    if architecture:
        parts.append(
            f"## Architecture\n"
            f"- Pattern: {architecture.detected_pattern}\n"
            f"- Entry points: {', '.join(architecture.entry_points) or 'none detected'}\n"
            f"- Core modules: {', '.join(architecture.core_modules) or 'none'}\n"
            f"- Orphan modules: {', '.join(architecture.orphan_modules) or 'none'}\n"
            f"- Dependency cycles: {len(architecture.dependency_cycles)} detected\n"
        )
        if architecture.module_descriptions:
            parts.append("### Module Descriptions\n")
            for mod, desc in architecture.module_descriptions.items():
                parts.append(f"- `{mod}`: {desc}\n")

    # Tech debt
    if tech_debt:
        parts.append(
            f"## Technical Debt\n"
            f"- Overall score: {tech_debt.overall_score}/100\n"
        )
        for cat in tech_debt.categories:
            parts.append(f"- {cat.name}: {cat.score}/100 ({cat.severity})\n")

    # Retrieved chunks
    if retrieved_chunks:
        parts.append("## Relevant Code\n")
        for i, chunk in enumerate(retrieved_chunks, 1):
            meta = chunk.get("metadata", {})
            content = chunk.get("content", "")
            parts.append(
                f"### Chunk {i}\n"
                f"- File: `{meta.get('file_path', 'unknown')}`\n"
                f"- Type: {meta.get('node_type', 'unknown')}\n"
                f"- Name: {meta.get('name', 'unknown')}\n"
                f"- Lines: {meta.get('start_line', '?')}-{meta.get('end_line', '?')}\n\n"
                f"```\n{content}\n```\n"
            )

    return "\n".join(parts)


def ask_question(
    state: GrimoireState,
    question: str,
    n_chunks: int = 5,
) -> dict[str, Any]:
    """Answer a question about the analyzed codebase using RAG.

    Args:
        state: The current pipeline state (must have completed analysis).
        question: The user's question.
        n_chunks: Number of code chunks to retrieve.

    Returns:
        Dict with ``answer``, ``sources``, and ``chunks_used``.
    """
    job_id = state["job_id"]

    # Retrieve relevant chunks
    retrieved = query_chunks(job_id, question, n_results=n_chunks)

    # Build context
    context = _build_context(
        retrieved_chunks=retrieved,
        manifest=state.get("repo_manifest"),
        architecture=state.get("architecture_report"),
        tech_debt=state.get("tech_debt_report"),
    )

    # Call OpenAI
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        return {
            "answer": (
                "Error: No OPENAI_API_KEY configured. "
                "Please set the environment variable and restart the server."
            ),
            "sources": [],
            "chunks_used": 0,
        }

    client = OpenAI(api_key=api_key)

    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            max_tokens=1024,
            messages=[
                {
                    "role": "system",
                    "content": SYSTEM_PROMPT,
                },
                {
                    "role": "user",
                    "content": f"# Codebase Context\n\n{context}\n\n# Question\n\n{question}",
                },
            ],
        )

        answer = response.choices[0].message.content if response.choices else "No answer generated."

    except Exception as e:
        logger.error("[%s] OpenAI API call failed: %s", job_id, e)
        answer = f"Error calling OpenAI API: {e}"

    # Build sources
    sources = [
        {
            "file_path": c.get("metadata", {}).get("file_path", "unknown"),
            "node_type": c.get("metadata", {}).get("node_type", "unknown"),
            "name": c.get("metadata", {}).get("name", "unknown"),
            "start_line": c.get("metadata", {}).get("start_line", 0),
            "end_line": c.get("metadata", {}).get("end_line", 0),
            "relevance": c.get("distance", 1.0),
        }
        for c in retrieved
    ]

    return {
        "answer": answer,
        "sources": sources,
        "chunks_used": len(retrieved),
    }

"""Shared catalog and helpers for MCP-accessible documentation files."""

from __future__ import annotations

import os

DOC_FILENAME_MAP = {
    "score-yaml-format": "score-yaml-format.md",
    "score-concepts": "score-concepts.md",
    "score-yaml-langgraph": "score-yaml-langgraph.md",
    "score-yaml-tactusscore": "score-yaml-tactusscore.md",
    "feedback-alignment": "feedback-alignment.md",
    "dataset-yaml-format": "dataset-yaml-format.md",
    "optimizer-cookbook": "optimizer-cookbook.md",
    "optimizer-procedures": "optimizer-procedures.md",
}

DOC_DESCRIPTION_MAP = {
    "score-yaml-format": (
        "High-level score-authoring guide covering shared design patterns, "
        "cross-cutting YAML features, and optimization techniques"
    ),
    "score-concepts": (
        "Shared score and optimizer mental model: scorecards, versions, "
        "dependencies, inputs, outputs, and error-segment terminology"
    ),
    "score-yaml-langgraph": (
        "LangGraphScore implementation guide: Classifier-centered graph recipes, "
        "routing, extractors, logical nodes, and aggregation patterns"
    ),
    "score-yaml-tactusscore": (
        "TactusScore implementation guide: ClassifyProcedure, raw Procedure, "
        "Classify, loops, gating, and deterministic aggregation"
    ),
    "feedback-alignment": (
        "Feedback alignment workflow reference: baseline-first analysis, local "
        "evaluation, segment investigation, and iteration discipline"
    ),
    "dataset-yaml-format": (
        "Dataset YAML reference for data sources, transformations, and evaluation inputs"
    ),
    "optimizer-cookbook": (
        "Optimizer change-selection guide covering when to try prompt fixes, "
        "structural redesign, processors, and model swaps"
    ),
    "optimizer-procedures": (
        "Feedback Alignment Optimizer procedure reference: trigger, monitor, "
        "continue, branch, and interpret runs"
    ),
}


def available_document_names() -> tuple[str, ...]:
    """Return the stable ordered list of valid documentation keys."""

    return tuple(DOC_FILENAME_MAP.keys())


def available_document_names_text() -> str:
    """Return the valid keys as a comma-separated string."""

    return ", ".join(available_document_names())


def build_invalid_filename_error(filename: str) -> str:
    """Return the canonical invalid-filename error."""

    return (
        f"Error: Invalid filename '{filename}'. "
        f"Valid options are: {available_document_names_text()}"
    )


def build_tool_docstring() -> str:
    """Return the canonical get_plexus_documentation docstring."""

    lines = [
        "Get documentation content for specific Plexus topics.",
        "",
        "Valid filenames:",
    ]
    for key in available_document_names():
        lines.append(f"- {key}: {DOC_DESCRIPTION_MAP[key]}")
    return "\n".join(lines)


def get_project_root() -> str:
    """Return the repository root that contains plexus/docs/."""

    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def get_docs_dir() -> str:
    """Return the absolute path to plexus/docs/."""

    return os.path.join(get_project_root(), "plexus", "docs")


def get_doc_path(filename: str) -> str:
    """Return the absolute path for a valid documentation key."""

    return os.path.join(get_docs_dir(), DOC_FILENAME_MAP[filename])

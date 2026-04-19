#!/usr/bin/env python3
"""Tests for the MCP documentation catalog and loader paths."""

from __future__ import annotations

import asyncio
import re
from pathlib import Path

import pytest

from shared.documentation_catalog import (
    DOC_FILENAME_MAP,
    available_document_names,
    build_invalid_filename_error,
    get_doc_path,
)
from tools.documentation.docs import register_documentation_tools
from tools.util.docs import register_docs_tool

pytestmark = pytest.mark.unit

PROJECT_ROOT = Path(__file__).resolve().parents[3]
TARGET_DOC_KEYS = (
    "score-concepts",
    "score-yaml-langgraph",
    "score-yaml-tactusscore",
)
OPTIMIZER_FACING_FILES = (
    PROJECT_ROOT / "plexus/docs/feedback-alignment.md",
    PROJECT_ROOT / "plexus/docs/optimizer-cookbook.md",
    PROJECT_ROOT / "plexus/docs/optimizer-procedures.md",
    PROJECT_ROOT / "plexus/procedures/feedback_alignment_optimizer.yaml",
)
BANNED_ERROR_SHORTHAND = (
    r"false positive",
    r"false negative",
    r"\bFP\b",
    r"\bFN\b",
)


class FakeMCP:
    """Tiny stand-in for FastMCP used to capture registered tools."""

    def __init__(self) -> None:
        self.tools = {}

    def tool(self):
        def decorator(func):
            self.tools[func.__name__] = func
            return func

        return decorator


def load_documentation_tool(register_fn):
    fake = FakeMCP()
    register_fn(fake)
    return fake.tools["get_plexus_documentation"]


def test_catalog_contains_expected_keys():
    assert available_document_names() == (
        "score-yaml-format",
        "score-concepts",
        "score-yaml-langgraph",
        "score-yaml-tactusscore",
        "feedback-alignment",
        "dataset-yaml-format",
        "optimizer-cookbook",
        "optimizer-procedures",
    )


def test_invalid_filename_message_uses_shared_catalog():
    error = build_invalid_filename_error("invalid-doc")
    assert error.startswith("Error: Invalid filename 'invalid-doc'.")
    for key in DOC_FILENAME_MAP:
        assert key in error


def test_catalog_paths_exist():
    for key in DOC_FILENAME_MAP:
        path = Path(get_doc_path(key))
        assert path.is_file(), f"Missing documentation file for key {key}: {path}"


def test_both_loader_paths_return_identical_content():
    documentation_tool = load_documentation_tool(register_documentation_tools)
    util_tool = load_documentation_tool(register_docs_tool)

    for key in DOC_FILENAME_MAP:
        documentation_content = asyncio.run(documentation_tool(key))
        util_content = asyncio.run(util_tool(key))
        assert documentation_content == util_content
        assert documentation_content.startswith("#")


def test_target_docs_are_not_empty_or_placeholder():
    for key in TARGET_DOC_KEYS:
        text = Path(get_doc_path(key)).read_text(encoding="utf-8")
        assert "PLACEHOLDER" not in text
        assert len(text.split()) > 120


def test_optimizer_facing_files_reject_legacy_error_shorthand():
    for path in OPTIMIZER_FACING_FILES:
        text = path.read_text(encoding="utf-8")
        for pattern in BANNED_ERROR_SHORTHAND:
            assert not re.search(
                pattern, text, flags=re.IGNORECASE
            ), f"Found banned error shorthand {pattern!r} in {path}"


def test_optimizer_docs_define_segment_shorthand():
    feedback_alignment = (
        PROJECT_ROOT / "plexus/docs/feedback-alignment.md"
    ).read_text(encoding="utf-8")
    assert 'P"No"->A"Yes"' in feedback_alignment
    assert 'P"Yes"->A"No"' in feedback_alignment

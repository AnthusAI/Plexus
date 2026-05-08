"""Unit tests for the documentation repository module."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from plexus.documentation.repository import (
    DocumentationRepository,
    InvalidDocumentationKeyError,
)


def _write(path, frontmatter: str, body: str = "# body\n") -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write("---\n" + frontmatter.strip() + "\n---\n" + body)


def _doc_frontmatter(doc_id: str, namespace: str, title: str | None = None) -> str:
    return (
        f"id: {doc_id}\n"
        f"title: {title or doc_id}\n"
        f"summary: summary for {doc_id}\n"
        f"namespace: {namespace}\n"
        "status: canonical\n"
        "disclosure: reference\n"
        "audience: agent\n"
        "tags: [test]\n"
    )


def test_list_returns_metadata_entries_sorted_by_id(tmp_path) -> None:
    _write(
        tmp_path / "mcp" / "discovery.md",
        _doc_frontmatter("mcp.discovery", "mcp", "Discovery"),
        "# Discovery\n",
    )
    _write(
        tmp_path / "mcp" / "execute-tactus.md",
        _doc_frontmatter("mcp.execute-tactus", "mcp", "Execute Tactus"),
        "# Execute Tactus\n",
    )

    repo = DocumentationRepository(str(tmp_path))
    result = repo.list_docs()

    ids = [entry["id"] for entry in result.entries]
    assert ids == ["mcp.discovery", "mcp.execute-tactus"]
    for entry in result.entries:
        for field in ("id", "title", "summary", "namespace", "tags"):
            assert field in entry
        assert "body" not in entry and "content" not in entry


def test_list_filters_by_namespace(tmp_path) -> None:
    _write(
        tmp_path / "mcp" / "discovery.md",
        _doc_frontmatter("mcp.discovery", "mcp"),
    )
    _write(
        tmp_path / "score-authoring" / "score-yaml.md",
        _doc_frontmatter("score-authoring.score-yaml", "score-authoring"),
    )

    repo = DocumentationRepository(str(tmp_path))
    result = repo.list_docs(namespace="mcp")

    assert [entry["id"] for entry in result.entries] == ["mcp.discovery"]


def test_list_excludes_readme_and_index_files(tmp_path) -> None:
    _write(
        tmp_path / "mcp" / "discovery.md",
        _doc_frontmatter("mcp.discovery", "mcp"),
    )
    _write(
        tmp_path / "mcp" / "_index.md",
        _doc_frontmatter("mcp._index", "mcp"),
    )
    (tmp_path / "mcp" / "README.md").write_text("# Human readme\n")

    repo = DocumentationRepository(str(tmp_path))
    result = repo.list_docs()

    ids = [entry["id"] for entry in result.entries]
    assert ids == ["mcp.discovery"]


def test_list_reports_files_without_frontmatter_as_invalid(tmp_path) -> None:
    _write(
        tmp_path / "mcp" / "discovery.md",
        _doc_frontmatter("mcp.discovery", "mcp"),
    )
    (tmp_path / "mcp" / "no-frontmatter.md").write_text("# No frontmatter\n")

    repo = DocumentationRepository(str(tmp_path))
    result = repo.list_docs()

    assert [entry["id"] for entry in result.entries] == ["mcp.discovery"]
    assert any("no-frontmatter" in invalid.path for invalid in result.invalid)


def test_get_doc_returns_metadata_and_body(tmp_path) -> None:
    _write(
        tmp_path / "mcp" / "discovery.md",
        _doc_frontmatter("mcp.discovery", "mcp", "Discovery"),
        "# Discovery\nUse api.list.\n",
    )

    repo = DocumentationRepository(str(tmp_path))
    doc = repo.get_doc("mcp.discovery")

    assert doc.metadata["id"] == "mcp.discovery"
    assert doc.metadata["title"] == "Discovery"
    assert doc.body.startswith("# Discovery")


def test_get_doc_rejects_unsafe_keys(tmp_path) -> None:
    repo = DocumentationRepository(str(tmp_path))

    for key in ("../etc/passwd", "/etc/passwd", ".hidden", "evaluation/../escape", ""):
        with pytest.raises(InvalidDocumentationKeyError):
            repo.get_doc(key)


def test_get_doc_unknown_id_raises(tmp_path) -> None:
    _write(
        tmp_path / "mcp" / "discovery.md",
        _doc_frontmatter("mcp.discovery", "mcp"),
    )

    repo = DocumentationRepository(str(tmp_path))
    with pytest.raises(InvalidDocumentationKeyError):
        repo.get_doc("mcp.does-not-exist")


def test_get_doc_resolves_index_files_when_id_matches(tmp_path) -> None:
    _write(
        tmp_path / "mcp" / "_index.md",
        _doc_frontmatter("mcp._index", "mcp", "MCP Namespace"),
        "# MCP\n",
    )

    repo = DocumentationRepository(str(tmp_path))
    doc = repo.get_doc("mcp._index")

    assert doc.metadata["title"] == "MCP Namespace"


def test_list_returns_empty_when_root_missing(tmp_path) -> None:
    repo = DocumentationRepository(str(tmp_path / "does-not-exist"))

    result = repo.list_docs()

    assert result.entries == []
    assert result.invalid == []


def test_real_reports_namespace_exposes_user_facing_report_docs() -> None:
    docs_root = Path(__file__).resolve().parents[2] / "documentation" / "agent"
    repo = DocumentationRepository(str(docs_root))

    result = repo.list_docs(namespace="reports")
    ids = {entry["id"] for entry in result.entries}
    expected_ids = {
        "reports.reports-catalog",
        "reports.feedback-overview",
        "reports.feedback-alignment",
        "reports.feedback-alignment-timeline",
        "reports.feedback-volume-timeline",
        "reports.feedback-contradictions",
        "reports.acceptance-rate",
        "reports.acceptance-rate-timeline",
        "reports.correction-rate",
        "reports.recent-feedback",
        "reports.score-champion-version-timeline",
        "reports.scorecard-history",
        "reports.score-results-report",
    }

    assert expected_ids.issubset(ids)
    for doc_id in expected_ids:
        doc = repo.get_doc(doc_id)
        assert doc.metadata["namespace"] == "reports"
        assert "plexus.report.run" in doc.body or doc_id == "reports.reports-catalog"

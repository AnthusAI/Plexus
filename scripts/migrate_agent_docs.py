#!/usr/bin/env python3
"""One-shot migration helper for the agent documentation knowledge base.

This script copies markdown content from the legacy ``plexus/docs/`` tree
(plus a couple of files in ``documentation/`` and ``docs/``) into the new
``documentation/agent/`` layout and prepends a YAML frontmatter block
based on a static mapping table.

Run from the repo root:

    python scripts/migrate_agent_docs.py

The script is idempotent: it overwrites destination files. It does NOT
delete the source files, so the migration can be reviewed and the old
locations cleaned up by a follow-up step.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class Migration:
    source: str
    dest: str
    doc_id: str
    title: str
    summary: str
    namespace: str
    disclosure: str = "reference"
    status: str = "canonical"
    tags: tuple[str, ...] = ()
    related: tuple[str, ...] = ()


MIGRATIONS: tuple[Migration, ...] = (
    # MCP / runtime
    Migration(
        source="plexus/docs/overview.md",
        dest="documentation/agent/mcp/execute-tactus-overview.md",
        doc_id="mcp.execute-tactus-overview",
        title="execute_tactus Overview",
        summary="The single MCP tool, how the runtime captures results, helper aliases, and the response envelope.",
        namespace="mcp",
        disclosure="overview",
        tags=("mcp", "tactus", "runtime"),
        related=("mcp.discovery", "mcp.read-apis", "mcp.long-running-apis"),
    ),
    Migration(
        source="plexus/docs/discovery.md",
        dest="documentation/agent/mcp/discovery.md",
        doc_id="mcp.discovery",
        title="Discovery",
        summary="Enumerate available APIs and docs from inside execute_tactus using api.list and docs.list.",
        namespace="mcp",
        disclosure="reference",
        tags=("mcp", "discovery"),
        related=("mcp.execute-tactus-overview",),
    ),
    Migration(
        source="plexus/docs/read-apis.md",
        dest="documentation/agent/mcp/read-apis.md",
        doc_id="mcp.read-apis",
        title="Read-only APIs",
        summary="Read patterns for scorecards, scores, items, evaluations, and feedback.",
        namespace="mcp",
        disclosure="reference",
        tags=("mcp", "read"),
        related=("mcp.execute-tactus-overview", "mcp.long-running-apis"),
    ),
    Migration(
        source="plexus/docs/long-running-apis.md",
        dest="documentation/agent/mcp/long-running-apis.md",
        doc_id="mcp.long-running-apis",
        title="Long-running APIs",
        summary="The async=true contract, child budget requirements, and handle protocol for evaluation.run, report.run, and procedure.run.",
        namespace="mcp",
        disclosure="reference",
        tags=("mcp", "async", "handles"),
        related=("mcp.handles-and-budgets", "mcp.handle-protocol"),
    ),
    Migration(
        source="plexus/docs/handles-and-budgets.md",
        dest="documentation/agent/mcp/handles-and-budgets.md",
        doc_id="mcp.handles-and-budgets",
        title="Handles and Budgets",
        summary="handle.peek, handle.await, handle.cancel, and how parent budgets are carved into child budgets.",
        namespace="mcp",
        disclosure="reference",
        tags=("mcp", "budget", "handles"),
        related=("mcp.long-running-apis", "mcp.handle-protocol"),
    ),
    Migration(
        source="MCP/tools/tactus_runtime/HANDLE_PROTOCOL.md",
        dest="documentation/agent/mcp/handle-protocol.md",
        doc_id="mcp.handle-protocol",
        title="execute_tactus Handle Protocol",
        summary="The long-running handle protocol implemented by execute_tactus.",
        namespace="mcp",
        disclosure="deep-dive",
        tags=("mcp", "handles", "protocol"),
        related=("mcp.handles-and-budgets", "mcp.long-running-apis"),
    ),
    # Score authoring
    Migration(
        source="plexus/docs/score-and-dataset-authoring/score-yaml-format.md",
        dest="documentation/agent/score-authoring/score-yaml-format.md",
        doc_id="score-authoring.score-yaml-format",
        title="Score YAML Format",
        summary="Authoring reference for Plexus score YAML configurations.",
        namespace="score-authoring",
        disclosure="reference",
        tags=("score", "yaml", "authoring"),
        related=("score-authoring.dataset-yaml-format", "score-authoring.rubric-memory"),
    ),
    Migration(
        source="plexus/docs/score-and-dataset-authoring/dataset-yaml-format.md",
        dest="documentation/agent/score-authoring/dataset-yaml-format.md",
        doc_id="score-authoring.dataset-yaml-format",
        title="Dataset YAML Format",
        summary="Authoring reference for Plexus dataset YAML configurations.",
        namespace="score-authoring",
        disclosure="reference",
        tags=("dataset", "yaml", "authoring"),
        related=("score-authoring.score-yaml-format",),
    ),
    Migration(
        source="plexus/docs/score-and-dataset-authoring/rubric-memory.md",
        dest="documentation/agent/score-authoring/rubric-memory.md",
        doc_id="score-authoring.rubric-memory",
        title="Rubric Memory",
        summary="Rubric memory retrieval and how it surfaces in optimizer and feedback workflows.",
        namespace="score-authoring",
        disclosure="reference",
        tags=("rubric", "memory"),
        related=("score-authoring.rubric-consistency", "evaluation-feedback.optimizer-cookbook"),
    ),
    Migration(
        source="plexus/docs/score-and-dataset-authoring/score-rubric-consistency.md",
        dest="documentation/agent/score-authoring/rubric-consistency.md",
        doc_id="score-authoring.rubric-consistency",
        title="Score and Rubric Consistency",
        summary="Keeping score logic and rubric guidelines aligned across versions.",
        namespace="score-authoring",
        disclosure="reference",
        tags=("rubric", "consistency"),
        related=("score-authoring.rubric-memory",),
    ),
    Migration(
        source="documentation/classifier-interface-standard.md",
        dest="documentation/agent/score-authoring/classifier-interface.md",
        doc_id="score-authoring.classifier-interface",
        title="Classifier Interface Standard",
        summary="Interface contract for Plexus classifiers.",
        namespace="score-authoring",
        disclosure="reference",
        tags=("classifier", "interface"),
        related=("score-authoring.score-yaml-format",),
    ),
    Migration(
        source="documentation/scorecard-processors.md",
        dest="documentation/agent/score-authoring/scorecard-processors.md",
        doc_id="score-authoring.scorecard-processors",
        title="Scorecard Processors",
        summary="Authoring scorecard processors for input transformation and filtering.",
        namespace="score-authoring",
        disclosure="reference",
        tags=("processors", "scorecard"),
    ),
    # Evaluation and feedback
    Migration(
        source="plexus/docs/evaluation-and-feedback/feedback-alignment.md",
        dest="documentation/agent/evaluation-feedback/feedback-alignment.md",
        doc_id="evaluation-feedback.feedback-alignment",
        title="Feedback Alignment",
        summary="Measuring agreement between AI and human feedback (AC1, accuracy, confusion matrices).",
        namespace="evaluation-feedback",
        disclosure="reference",
        tags=("feedback", "alignment", "ac1"),
        related=("evaluation-feedback.evaluation-alignment", "evaluation-feedback.acceptance-rate"),
    ),
    Migration(
        source="plexus/docs/evaluation-and-feedback/evaluation-alignment.md",
        dest="documentation/agent/evaluation-feedback/evaluation-alignment.md",
        doc_id="evaluation-feedback.evaluation-alignment",
        title="Evaluation Alignment",
        summary="Running and interpreting evaluation alignment workflows.",
        namespace="evaluation-feedback",
        disclosure="reference",
        tags=("evaluation", "alignment"),
        related=("evaluation-feedback.feedback-alignment",),
    ),
    Migration(
        source="plexus/docs/evaluation-and-feedback/acceptance-rate.md",
        dest="documentation/agent/evaluation-feedback/acceptance-rate.md",
        doc_id="evaluation-feedback.acceptance-rate",
        title="Acceptance Rate",
        summary="Acceptance rate report and how it relates to alignment.",
        namespace="evaluation-feedback",
        disclosure="reference",
        tags=("acceptance-rate", "feedback"),
    ),
    Migration(
        source="plexus/docs/evaluation-and-feedback/optimizer-cookbook.md",
        dest="documentation/agent/evaluation-feedback/optimizer-cookbook.md",
        doc_id="evaluation-feedback.optimizer-cookbook",
        title="Optimizer Cookbook",
        summary="Index of optimizer cookbook variants and when to apply each.",
        namespace="evaluation-feedback",
        disclosure="overview",
        tags=("optimizer", "cookbook"),
        related=(
            "evaluation-feedback.optimizer-cookbook-normal",
            "evaluation-feedback.optimizer-cookbook-creative",
            "evaluation-feedback.optimizer-cookbook-structural",
        ),
    ),
    Migration(
        source="plexus/docs/evaluation-and-feedback/optimizer-cookbook-normal.md",
        dest="documentation/agent/evaluation-feedback/optimizer-cookbook-normal.md",
        doc_id="evaluation-feedback.optimizer-cookbook-normal",
        title="Optimizer Cookbook (Normal)",
        summary="Default optimizer playbook.",
        namespace="evaluation-feedback",
        disclosure="cookbook",
        tags=("optimizer", "cookbook"),
        related=("evaluation-feedback.optimizer-cookbook",),
    ),
    Migration(
        source="plexus/docs/evaluation-and-feedback/optimizer-cookbook-creative.md",
        dest="documentation/agent/evaluation-feedback/optimizer-cookbook-creative.md",
        doc_id="evaluation-feedback.optimizer-cookbook-creative",
        title="Optimizer Cookbook (Creative)",
        summary="Creative optimizer playbook for exploratory rubric work.",
        namespace="evaluation-feedback",
        disclosure="cookbook",
        tags=("optimizer", "cookbook"),
        related=("evaluation-feedback.optimizer-cookbook",),
    ),
    Migration(
        source="plexus/docs/evaluation-and-feedback/optimizer-cookbook-structural.md",
        dest="documentation/agent/evaluation-feedback/optimizer-cookbook-structural.md",
        doc_id="evaluation-feedback.optimizer-cookbook-structural",
        title="Optimizer Cookbook (Structural)",
        summary="Structural optimizer playbook for refactoring score logic.",
        namespace="evaluation-feedback",
        disclosure="cookbook",
        tags=("optimizer", "cookbook"),
        related=("evaluation-feedback.optimizer-cookbook",),
    ),
    Migration(
        source="plexus/docs/evaluation-and-feedback/optimizer-procedures.md",
        dest="documentation/agent/evaluation-feedback/optimizer-procedures.md",
        doc_id="evaluation-feedback.optimizer-procedures",
        title="Optimizer Procedures",
        summary="Procedure interfaces used by the feedback alignment optimizer.",
        namespace="evaluation-feedback",
        disclosure="reference",
        tags=("optimizer", "procedures"),
        related=(
            "evaluation-feedback.optimizer-cookbook",
            "optimizer.run-direct",
        ),
    ),
    Migration(
        source="plexus/docs/evaluation-and-feedback/optimizer-objective-alignment.md",
        dest="documentation/agent/evaluation-feedback/optimizer-objective-alignment.md",
        doc_id="evaluation-feedback.optimizer-objective-alignment",
        title="Optimizer Objective: Alignment",
        summary="Default optimizer objective: maximize alignment.",
        namespace="evaluation-feedback",
        disclosure="reference",
        tags=("optimizer", "objective", "alignment"),
    ),
    Migration(
        source="plexus/docs/evaluation-and-feedback/optimizer-objective-precision.md",
        dest="documentation/agent/evaluation-feedback/optimizer-objective-precision.md",
        doc_id="evaluation-feedback.optimizer-objective-precision",
        title="Optimizer Objective: Precision",
        summary="Optimizer objective tuned for precision.",
        namespace="evaluation-feedback",
        disclosure="reference",
        tags=("optimizer", "objective", "precision"),
    ),
    Migration(
        source="plexus/docs/evaluation-and-feedback/optimizer-objective-recall.md",
        dest="documentation/agent/evaluation-feedback/optimizer-objective-recall.md",
        doc_id="evaluation-feedback.optimizer-objective-recall",
        title="Optimizer Objective: Recall",
        summary="Optimizer objective tuned for recall.",
        namespace="evaluation-feedback",
        disclosure="reference",
        tags=("optimizer", "objective", "recall"),
    ),
    Migration(
        source="plexus/docs/evaluation-and-feedback/optimizer-objective-cost.md",
        dest="documentation/agent/evaluation-feedback/optimizer-objective-cost.md",
        doc_id="evaluation-feedback.optimizer-objective-cost",
        title="Optimizer Objective: Cost",
        summary="Optimizer objective tuned to minimize cost.",
        namespace="evaluation-feedback",
        disclosure="reference",
        tags=("optimizer", "objective", "cost"),
    ),
    # Reports
    Migration(
        source="documentation/report_block_details_s3_storage.md",
        dest="documentation/agent/reports/report-block-s3-storage.md",
        doc_id="reports.report-block-s3-storage",
        title="Report Block S3 Storage",
        summary="How ReportBlock output and attachments persist to S3 with DynamoDB metadata pointers.",
        namespace="reports",
        disclosure="reference",
        tags=("reports", "s3", "storage"),
    ),
    Migration(
        source="docs/topic_analysis_configuration.md",
        dest="documentation/agent/reports/topic-analysis-configuration.md",
        doc_id="reports.topic-analysis-configuration",
        title="Topic Analysis Configuration",
        summary="Configuring the TopicAnalysis report block (BERTopic, exemplars, lifecycle).",
        namespace="reports",
        disclosure="reference",
        tags=("reports", "topic-analysis", "bertopic"),
    ),
)


INDEX_FILES = {
    "mcp": (
        "MCP and execute_tactus",
        "Single-tool MCP runtime: discovery, reads, long-running calls, handles, and budgets.",
    ),
    "score-authoring": (
        "Score and Dataset Authoring",
        "How to author Plexus scores, datasets, classifiers, and processors.",
    ),
    "evaluation-feedback": (
        "Evaluation and Feedback",
        "Alignment, evaluation, acceptance, optimizer cookbook, and optimizer objectives.",
    ),
    "procedures": (
        "Procedures",
        "Authoring and running Plexus procedures.",
    ),
    "reports": (
        "Reports",
        "Report block authoring, persistence, and analysis configuration.",
    ),
    "optimizer": (
        "Optimizer Operations",
        "Direct CLI optimizer workflows and operating discipline.",
    ),
    "repo-workflows": (
        "Repository Workflows",
        "Kanbus, Git Flow, and local environment workflows used by humans and agents.",
    ),
}


def _yaml_list(values: tuple[str, ...]) -> str:
    if not values:
        return "[]"
    parts = ", ".join(values)
    return f"[{parts}]"


def _yaml_str(value: str) -> str:
    """Render a YAML scalar that is safe even with colons or quotes."""

    needs_quoting = any(token in value for token in (":", "#", "'", "\"", "{", "}", "[", "]", ",", "&", "*", "!", "|", ">", "%", "@", "`"))
    needs_quoting = needs_quoting or value != value.strip()
    if not needs_quoting:
        return value
    escaped = value.replace("\\", "\\\\").replace("\"", "\\\"")
    return f"\"{escaped}\""


def _frontmatter(migration: Migration) -> str:
    lines = [
        "---",
        f"id: {migration.doc_id}",
        f"title: {_yaml_str(migration.title)}",
        f"summary: {_yaml_str(migration.summary)}",
        f"namespace: {migration.namespace}",
        f"status: {migration.status}",
        f"disclosure: {migration.disclosure}",
        "audience: agent",
        f"tags: {_yaml_list(migration.tags)}",
    ]
    if migration.related:
        lines.append("related:")
        for rid in migration.related:
            lines.append(f"  - {rid}")
    lines.append("---")
    return "\n".join(lines) + "\n"


def _index_frontmatter(namespace: str, title: str, summary: str) -> str:
    return (
        "---\n"
        f"id: {namespace}._index\n"
        f"title: {_yaml_str(title)}\n"
        f"summary: {_yaml_str(summary)}\n"
        f"namespace: {namespace}\n"
        "status: canonical\n"
        "disclosure: overview\n"
        "audience: agent\n"
        "tags: [index]\n"
        "---\n"
    )


def migrate(repo_root: Path) -> None:
    missing: list[str] = []
    for migration in MIGRATIONS:
        src = repo_root / migration.source
        dst = repo_root / migration.dest
        if not src.is_file():
            missing.append(migration.source)
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        body = src.read_text(encoding="utf-8")
        dst.write_text(_frontmatter(migration) + body, encoding="utf-8")
        print(f"migrated  {migration.source} -> {migration.dest}")

    for namespace, (title, summary) in INDEX_FILES.items():
        path = repo_root / "documentation" / "agent" / namespace / "_index.md"
        body = (
            f"# {title}\n\n"
            f"{summary}\n\n"
            "## Topics in this namespace\n\n"
            "Use `plexus.docs.list({ namespace = \"" + namespace + "\" })` to list every topic, "
            "then `plexus.docs.get({ key = \"<id>\" })` for the full doc.\n"
        )
        path.write_text(_index_frontmatter(namespace, title, summary) + body, encoding="utf-8")
        print(f"wrote     {path.relative_to(repo_root)}")

    if missing:
        print()
        print("MISSING SOURCES (skipped):")
        for path in missing:
            print(f"  - {path}")
        sys.exit(1)


if __name__ == "__main__":
    migrate(REPO_ROOT)

"""Durable, append-only reporting for one periodic optimization run.

The service deliberately owns no optimization orchestration.  Callers execute
the decision stages with ``persist=False`` and publish their returned packets at
well-defined milestones.  A single Task is the lifecycle authority; one Report
is its stable stakeholder location; ReportBlocks contain only compact pointers
to immutable JSON/XLSX revisions.
"""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from io import BytesIO, StringIO
from typing import Any, Callable, Mapping, Optional
from urllib.parse import quote, urlencode, urlparse
from uuid import uuid4
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Font
from openpyxl.writer.excel import ExcelWriter

from plexus.optimization.operator_identity import (
    OptimizationOperatorIdentity,
    optimization_operator_identity,
)
from openpyxl.worksheet.table import Table, TableStyleInfo

from plexus.dashboard.api.models.report import Report
from plexus.dashboard.api.models.report_block import ReportBlock
from plexus.dashboard.api.models.task import Task
from plexus.dashboard.api.models.task_stage import TaskStage
from plexus.reports.service import _compact_output_json_for_storage, _get_programmatic_config_id
from plexus.storage.graphql_artifact_store import ArtifactTransferRequest, GraphQLArtifactStore


LIFECYCLE_VERSION = "optimization-run-report-v1"
_BLOCK_SPECS = (
    (0, "Run Status", "OptimizationRunStatus"),
    (1, "Decision Evidence", "OptimizationDecisionEvidence"),
    (2, "Stakeholder Workbook", "OptimizationStakeholderWorkbook"),
)
SHEET_NAMES = (
    "Overview",
    "Portfolio",
    "Priorities",
    "Feedback Investment",
    "Questions and Issues",
    "Optimization Outcomes",
    "Run Log",
    "Definitions",
)
_STAGES = ("preflight", "ranking", "assessment", "diagnosis", "approval", "optimization", "review", "finalization")
_MILESTONE_STAGE = {
    # Milestones describe the evidence that was just made durable.  Point the
    # dashboard at the work that follows so the Report never appears stuck on
    # a phase whose result is already published.
    "started": "ranking",
    "ranking": "assessment",
    "assessment": "diagnosis",
    "diagnosis": "approval",
    "approval": "approval",
    "optimization": "optimization",
    "optimization_review": "review",
    "finalization": "finalization",
}
_FINAL_STATES = {
    "complete",
    "completed",
    "complete_with_unresolved_actions",
    "completed_with_unresolved_actions",
    "incomplete",
    "blocked",
    "failed",
}

_ROW_COLUMNS: dict[str, tuple[tuple[str, str], ...]] = {
    "portfolio": (
        ("Evidence Rank", "evidence_rank"), ("Eligible Candidate Rank", "candidate_rank"),
        ("Scorecard", "scorecard_name"), ("Score", "score_name"),
        ("Valid Feedback", "valid_feedback_count"),
        ("Reviewed Disagreements", "reviewed_disagreements"),
        ("Disagreement Rate", "disagreement_rate"),
        ("Reviewed Error Opportunity", "reviewed_error_opportunity"),
        ("Policy Disposition", "policy_disposition"), ("Policy Reason", "policy_reason"),
        ("Review Disposition", "review_disposition"), ("Eligible After", "eligibility_timestamp"),
        ("Coverage", "coverage_status"), ("Recent Trend", "trend"),
        ("Collection State", "collection_state"), ("Guideline State", "guideline_state"),
        ("Feedback/Rubric State", "feedback_rubric_state"), ("Readiness", "readiness"),
        ("Promotion Readiness", "promotion_readiness"), ("Rationale", "rationale"),
        ("Next Action", "next_action"), ("Dashboard Link", "dashboard_url"),
    ),
    "priorities": (
        ("Evidence Rank", "evidence_rank"), ("Eligible Candidate Rank", "candidate_rank"),
        ("Scorecard", "scorecard_name"), ("Score", "score_name"),
        ("Evidence Count", "evidence_count"), ("Opportunity", "opportunity"),
        ("Disagreement Rate", "disagreement_rate"),
        ("Policy Disposition", "policy_disposition"), ("Policy Reason", "policy_reason"),
        ("Review Disposition", "review_disposition"), ("Eligible After", "eligibility_timestamp"),
        ("State", "state"), ("Coverage", "coverage_status"), ("Recent Trend", "trend"),
        ("Collection State", "collection_state"), ("Readiness", "readiness"),
        ("Promotion Readiness", "promotion_readiness"), ("Rationale", "rationale"),
        ("Next Action", "next_action"), ("Dashboard Link", "dashboard_url"),
    ),
    "feedback_investment": (
        ("Rank", "rank"), ("Scorecard", "scorecard_name"), ("Score", "score_name"),
        ("Evidence Count", "evidence_count"), ("State", "state"),
        ("Coverage", "coverage_status"), ("Recent Trend", "trend"),
        ("Recommendation", "recommendation"), ("Readiness", "readiness"),
        ("Rationale", "rationale"), ("Next Action", "next_action"),
        ("Dashboard Link", "dashboard_url"),
    ),
    "questions_and_issues": (
        ("Rank", "rank"), ("Type", "kind"), ("Scorecard", "scorecard_name"), ("Score", "score_name"),
        ("Evidence Count", "evidence_count"), ("State", "state"),
        ("Coverage", "coverage_status"), ("Guideline State", "guideline_state"),
        ("Feedback/Rubric State", "feedback_rubric_state"),
        ("Question or Issue", "finding"), ("Rationale", "rationale"),
        ("Next Action", "next_action"), ("Dashboard Link", "dashboard_url"),
    ),
    "optimization_outcomes": (
        ("Rank", "rank"), ("Scorecard", "scorecard_name"), ("Score", "score_name"),
        ("Evidence Count", "evidence_count"), ("Outcome", "outcome"),
        ("Evidence Status", "evidence_status"), ("Coverage", "coverage_status"),
        ("Recent Trend", "trend"), ("Collection State", "collection_state"),
        ("Readiness", "readiness"), ("Promotion Readiness", "promotion_readiness"),
        ("Rationale", "rationale"), ("Next Action", "next_action"),
        ("Dashboard Link", "dashboard_url"),
    ),
}
_OVERVIEW_KEYS = {
    "headline", "lifecycle_status", "current_activity", "next_checkpoint",
    "coverage_status", "inventory_coverage_status", "analysis_coverage_status",
    "ranking_window", "scorecards_inspected",
    "scorecards_in_scope", "evidence_ranked_score_count",
    "ranked_score_count", "unranked_score_count", "cooldown_excluded_count",
    "assessment_progress", "diagnosis_coverage", "pending_approval_count", "notes",
    "ranking_cutoff", "ranking_policy", "priority_display_limit",
    "priority_displayed_count", "priority_cutoff_rank", "priority_cutoff_opportunity",
    "ranked_below_priority_cutoff", "diagnosis_selection_policy",
    "diagnosis_top_priority_count", "diagnosis_monitoring_candidate_count",
    "diagnosis_selected_count", "diagnosis_scheduled_count", "diagnosis_deferred_count",
    "diagnosis_skipped_count", "diagnosis_incomplete_count", "diagnosis_max_count",
    "approved_target_count", "dispatched_optimizer_count", "optimizer_review_count",
}
_ROW_METADATA_KEYS = {
    "scorecard_ref", "rank", "evidence_rank", "candidate_rank", "policy_disposition",
    "policy_reason", "review_disposition", "eligibility_timestamp",
}


class OptimizationRunPublicationError(RuntimeError):
    """A milestone could not be made durable, so the run must stop."""


@dataclass
class OptimizationRunReportState:
    task: Any
    report: Any
    blocks: dict[str, Any]
    stages: dict[str, Any]
    run_spec: Mapping[str, Any]
    attempt_id: str
    operator_identity: OptimizationOperatorIdentity


@dataclass(frozen=True)
class WorkbookArtifact:
    content: bytes
    checksum: str
    row_counts: Mapping[str, int]


@dataclass(frozen=True)
class PublishedRevision:
    number: int
    milestone: str
    published_at: str
    raw_evidence_path: str
    workbook_path: str
    manifest_path: str
    manifest_checksum: str
    manifest_size_bytes: int
    evidence_checksum: str
    workbook_checksum: str
    row_counts: Mapping[str, int]
    overview: Mapping[str, Any]
    artifacts: tuple[Mapping[str, Any], ...] = ()


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _json(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str).encode("utf-8")


def _normalize_dashboard_base_url(value: Optional[str]) -> Optional[str]:
    if value is None or not str(value).strip():
        return None
    parsed = urlparse(str(value).strip())
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.path not in {"", "/"}
        or parsed.params
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError("dashboard_base_url must be an HTTPS origin")
    return f"https://{parsed.netloc}"


def dashboard_base_url_from_account_settings(settings: Any) -> Optional[str]:
    parsed_settings = _metadata(settings)
    reporting = parsed_settings.get("reporting")
    if not isinstance(reporting, Mapping):
        return None
    value = reporting.get("dashboardBaseUrl")
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError("reporting.dashboardBaseUrl must be a string")
    return _normalize_dashboard_base_url(value)


def _report_artifact_url(
    base_url: str,
    *,
    report_id: str,
    revision_number: int,
    logical_id: str,
) -> str:
    query = urlencode({"revision": revision_number, "artifact": logical_id})
    return f"{base_url}/lab/reports/{quote(report_id, safe='')}?{query}"


def optimization_run_key(account_id: str, run_spec: Mapping[str, Any]) -> str:
    """Stable identity for a frozen account/scope/policy run."""
    if not account_id or not isinstance(run_spec, Mapping):
        raise ValueError("account_id and run_spec are required")
    return "optimization-run-" + sha256(_json({"account_id": account_id, "run_spec": dict(run_spec)})).hexdigest()[:24]


def _same_run_spec(left: Mapping[str, Any], right: Mapping[str, Any]) -> bool:
    return _json(left) == _json(right)


def _metadata(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return {}
        return dict(parsed) if isinstance(parsed, dict) else {}
    return {}


def _safe_cell(value: Any) -> Any:
    if value is None or isinstance(value, (int, float, bool)):
        return value
    text = str(value)
    if text[:1] in ("=", "+", "-", "@"):
        return "'" + text
    return text


def _validate_view(view: Mapping[str, Any]) -> None:
    allowed_top_level = {"overview", "portfolio", "priorities", "feedback_investment", "questions_and_issues", "optimization_outcomes", "definitions"}
    unknown = set(view) - allowed_top_level
    if unknown:
        raise ValueError(f"stakeholder view keys are not allowed: {sorted(unknown)}")
    overview = view.get("overview", {})
    if not isinstance(overview, Mapping) or set(overview) - _OVERVIEW_KEYS:
        raise ValueError("overview contains keys that are not allowed")
    definitions = view.get("definitions", {})
    if not isinstance(definitions, Mapping):
        raise ValueError("definitions must be a mapping")
    for group, columns in _ROW_COLUMNS.items():
        rows = view.get(group, [])
        if not isinstance(rows, list):
            raise ValueError(f"{group} must be a list")
        allowed = {key for _, key in columns} | _ROW_METADATA_KEYS
        for row in rows:
            if not isinstance(row, Mapping):
                raise ValueError(f"{group} rows must be mappings")
            disallowed = set(row) - allowed
            if disallowed:
                raise ValueError(f"{group} contains keys that are not allowed: {sorted(disallowed)}")


def _write_table(sheet: Any, columns: tuple[tuple[str, str], ...], rows: list[Mapping[str, Any]]) -> None:
    sheet.append([title for title, _ in columns])
    for cell in sheet[1]:
        cell.font = Font(bold=True)
    for row in rows:
        sheet.append([_safe_cell(row.get(key)) for _, key in columns])
        if "dashboard_url" in row and row.get("dashboard_url"):
            cell = sheet.cell(sheet.max_row, len(columns))
            link = str(row["dashboard_url"])
            if link.startswith("https://"):
                cell.hyperlink = link
                cell.style = "Hyperlink"
    sheet.freeze_panes = "A2"
    sheet.auto_filter.ref = sheet.dimensions
    safe_name = "".join(part.title() for part in sheet.title.replace("-", " ").split()) + "Table"
    table = Table(displayName=safe_name, ref=sheet.dimensions)
    table.tableStyleInfo = TableStyleInfo(name="TableStyleMedium2", showRowStripes=True)
    sheet.add_table(table)
    for column in sheet.columns:
        width = max(len(str(cell.value or "")) for cell in column) + 2
        sheet.column_dimensions[column[0].column_letter].width = min(max(width, 12), 60)


def _canonical_xlsx(workbook: Workbook) -> bytes:
    """Save an xlsx with stable Zip metadata so checksums are reproducible."""
    interim = BytesIO()
    # Workbook.save() replaces the caller-supplied modified timestamp with the
    # wall clock immediately before serialization. Write through ExcelWriter
    # so both core timestamps remain part of the frozen report evidence.
    ExcelWriter(
        workbook,
        ZipFile(interim, "w", compression=ZIP_DEFLATED, allowZip64=True),
    ).save()
    output = BytesIO()
    with ZipFile(interim, "r") as source, ZipFile(output, "w", compression=ZIP_DEFLATED, compresslevel=9) as target:
        for name in sorted(source.namelist()):
            info = ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = ZIP_DEFLATED
            info.external_attr = 0o600 << 16
            target.writestr(info, source.read(name), compress_type=ZIP_DEFLATED, compresslevel=9)
    return output.getvalue()


def _validate_workbook_bytes(content: bytes, expected_row_counts: Mapping[str, int]) -> None:
    """Reopen the final artifact and reject unsafe or divergent workbooks."""
    workbook = load_workbook(BytesIO(content), data_only=False, keep_links=True)
    if workbook.sheetnames != list(SHEET_NAMES):
        raise ValueError("workbook sheet contract changed")
    if getattr(workbook, "_external_links", None):
        raise ValueError("workbook contains external links")
    if any(sheet.sheet_state != "visible" for sheet in workbook.worksheets):
        raise ValueError("workbook contains hidden sheets")
    if any(
        cell.data_type == "f"
        for sheet in workbook.worksheets
        for row in sheet.iter_rows()
        for cell in row
    ):
        raise ValueError("workbook contains formulas")
    sheet_by_projection = {
        "portfolio": "Portfolio",
        "priorities": "Priorities",
        "feedback_investment": "Feedback Investment",
        "questions_and_issues": "Questions and Issues",
        "optimization_outcomes": "Optimization Outcomes",
        "run_log": "Run Log",
        "definitions": "Definitions",
    }
    for key, expected in expected_row_counts.items():
        actual = max(workbook[sheet_by_projection[key]].max_row - 1, 0)
        if actual != expected:
            raise ValueError(f"workbook row count mismatch for {key}: {actual} != {expected}")


def build_stakeholder_workbook(
    stakeholder_view: Mapping[str, Any], *, revision_number: int, generated_at: datetime
) -> WorkbookArtifact:
    """Create the fixed, macro-free stakeholder workbook from a safe projection only."""
    _validate_view(stakeholder_view)
    generated_at = generated_at.astimezone(timezone.utc)
    workbook = Workbook()
    workbook.remove(workbook.active)
    workbook.properties.creator = "Plexus"
    workbook.properties.created = generated_at
    workbook.properties.modified = generated_at
    workbook.calculation.fullCalcOnLoad = False
    workbook.calculation.forceFullCalc = False

    overview = workbook.create_sheet("Overview")
    overview.append(["Optimization Run Overview", "Value"])
    for cell in overview[1]:
        cell.font = Font(bold=True)
    overview.append(["Revision", revision_number])
    overview.append(["Published At", _iso(generated_at)])
    for key in sorted(stakeholder_view.get("overview", {})):
        overview.append([key.replace("_", " ").title(), _safe_cell(stakeholder_view["overview"][key])])
    overview.column_dimensions["A"].width = min(
        max(len(str(cell.value or "")) for cell in overview["A"]) + 2,
        40,
    )
    overview.column_dimensions["B"].width = min(
        max(max(len(str(cell.value or "")) for cell in overview["B"]) + 2, 40),
        100,
    )
    for cell in overview["B"]:
        cell.alignment = Alignment(wrap_text=True, vertical="top")

    row_counts: dict[str, int] = {}
    table_sheets = (
        ("Portfolio", "portfolio"), ("Priorities", "priorities"),
        ("Feedback Investment", "feedback_investment"), ("Questions and Issues", "questions_and_issues"),
        ("Optimization Outcomes", "optimization_outcomes"),
    )
    for sheet_name, key in table_sheets:
        rows = list(stakeholder_view.get(key, []))
        _write_table(workbook.create_sheet(sheet_name), _ROW_COLUMNS[key], rows)
        row_counts[key] = len(rows)

    run_log = workbook.create_sheet("Run Log")
    _write_table(
        run_log,
        (("Revision", "revision"), ("Published At", "published_at"), ("Coverage", "coverage"), ("Status", "status")),
        [{"revision": revision_number, "published_at": _iso(generated_at), "coverage": stakeholder_view.get("overview", {}).get("coverage_status", "not provided"), "status": "published"}],
    )
    row_counts["run_log"] = 1

    definitions = workbook.create_sheet("Definitions")
    _write_table(
        definitions,
        (("Term", "term"), ("Definition", "definition")),
        [{"term": term, "definition": definition} for term, definition in sorted(stakeholder_view.get("definitions", {}).items())],
    )
    row_counts["definitions"] = len(stakeholder_view.get("definitions", {}))

    content = _canonical_xlsx(workbook)
    _validate_workbook_bytes(content, row_counts)
    return WorkbookArtifact(content=content, checksum=sha256(content).hexdigest(), row_counts=row_counts)


def _markdown_text(value: Any) -> str:
    return str(value or "").replace("\r", " ").replace("\n", " ").replace("|", "\\|").strip()


def _artifact_descriptor(
    *,
    logical_id: str,
    kind: str,
    display_name: str,
    scope: str,
    content_type: str,
    content: bytes,
    object_key: str,
    task_id: str,
    source_revision: int,
    scorecard_name: Optional[str] = None,
    score_name: Optional[str] = None,
) -> dict[str, Any]:
    descriptor: dict[str, Any] = {
        "logical_id": logical_id,
        "kind": kind,
        "display_name": display_name,
        "scope": scope,
        "content_type": content_type,
        "size_bytes": len(content),
        "sha256": sha256(content).hexdigest(),
        "task_id": task_id,
        "object_key": object_key,
        "source_revision": source_revision,
    }
    if scorecard_name:
        descriptor["scorecard_name"] = scorecard_name
    if score_name:
        descriptor["score_name"] = score_name
    return descriptor


def _score_issues(
    stakeholder_view: Mapping[str, Any],
    *,
    scorecard_name: str,
    scorecard_ref: str,
    score_name: str,
) -> list[Mapping[str, Any]]:
    return [
        issue for issue in stakeholder_view.get("questions_and_issues", [])
        if issue.get("score_name") == score_name
        and (
            issue.get("scorecard_ref") == scorecard_ref
            or (
                not issue.get("scorecard_ref")
                and issue.get("scorecard_name") == scorecard_name
            )
        )
    ]


def _score_brief_markdown(
    scorecard_name: str,
    scorecard_ref: str,
    row: Mapping[str, Any],
    stakeholder_view: Mapping[str, Any],
) -> bytes:
    score_name = str(row.get("score_name") or "Unlabeled score")
    lines = [
        f"# {_markdown_text(score_name)}",
        "",
        f"Scorecard: {_markdown_text(scorecard_name)}",
        "",
        "## Current finding",
        "",
        f"- Readiness: {_markdown_text(row.get('readiness') or 'inconclusive')}",
        f"- Feedback collection: {_markdown_text(row.get('collection_state') or 'inconclusive')}",
        f"- Valid feedback: {_markdown_text(row.get('valid_feedback_count') or 0)}",
        f"- Reviewed disagreements: {_markdown_text(row.get('reviewed_disagreements') or 0)}",
        f"- Next action: {_markdown_text(row.get('next_action') or 'review')}",
        "",
        _markdown_text(row.get("rationale") or "No stakeholder-safe rationale is available yet."),
    ]
    issues = _score_issues(
        stakeholder_view,
        scorecard_name=scorecard_name,
        scorecard_ref=scorecard_ref,
        score_name=score_name,
    )
    if issues:
        lines.extend(["", "## Questions and issues", ""])
        for issue in issues:
            finding = _markdown_text(
                issue.get("finding") or issue.get("rationale") or "Review required"
            )
            next_action = _markdown_text(issue.get("next_action") or "review")
            lines.append(f"- {finding} Next action: {next_action}.")
    lines.extend([
        "",
        "This brief contains stakeholder-safe findings only. The living Plexus Report is the cover page and lifecycle authority.",
        "",
    ])
    return "\n".join(lines).encode("utf-8")


def _scorecard_summary_markdown(
    scorecard_name: str,
    scorecard_ref: str,
    rows: list[Mapping[str, Any]],
    stakeholder_view: Mapping[str, Any],
) -> bytes:
    readiness_counts: dict[str, int] = {}
    collection_counts: dict[str, int] = {}
    for row in rows:
        readiness = _markdown_text(row.get("readiness") or "inconclusive")
        collection = _markdown_text(row.get("collection_state") or "inconclusive")
        readiness_counts[readiness] = readiness_counts.get(readiness, 0) + 1
        collection_counts[collection] = collection_counts.get(collection, 0) + 1

    def _counts(values: Mapping[str, int]) -> str:
        return ", ".join(f"{key}: {value}" for key, value in sorted(values.items())) or "None"

    def _opportunity(row: Mapping[str, Any]) -> float:
        try:
            return float(row.get("reviewed_error_opportunity") or 0)
        except (TypeError, ValueError):
            return 0.0

    priority_rows = sorted(rows, key=_opportunity, reverse=True)
    lines = [
        f"# {_markdown_text(scorecard_name)}",
        "",
        f"This scorecard has {len(rows)} scored criteria in this optimization report.",
        "",
        f"Readiness: {_counts(readiness_counts)}.",
        f"Feedback investment: {_counts(collection_counts)}.",
        "",
        "## Score details",
        "",
        "| Score | Valid feedback | Reviewed disagreements | Readiness | Next action |",
        "|---|---:|---:|---|---|",
    ]
    for row in priority_rows:
        lines.append(
            "| " + " | ".join([
                _markdown_text(row.get("score_name") or "Unlabeled score"),
                _markdown_text(row.get("valid_feedback_count")),
                _markdown_text(row.get("reviewed_disagreements")),
                _markdown_text(row.get("readiness") or "inconclusive"),
                _markdown_text(row.get("next_action") or "review"),
            ]) + " |"
        )

    issues = [
        row for row in stakeholder_view.get("questions_and_issues", [])
        if (
            row.get("scorecard_ref") == scorecard_ref
            or (
                not row.get("scorecard_ref")
                and row.get("scorecard_name") == scorecard_name
            )
        )
    ]
    if issues:
        lines.extend(["", "## Questions and issues", ""])
        for issue in issues:
            finding = _markdown_text(issue.get("finding") or issue.get("rationale") or "Review required")
            score_name = _markdown_text(issue.get("score_name") or "Score")
            lines.append(f"- {score_name}: {finding}")

    lines.extend([
        "",
        "This summary contains stakeholder-safe findings only. The living Plexus Report is the cover page and lifecycle authority.",
        "",
    ])
    return "\n".join(lines).encode("utf-8")


def _scorecard_csv(rows: list[Mapping[str, Any]]) -> bytes:
    output = StringIO(newline="")
    writer = csv.writer(output, lineterminator="\r\n")
    writer.writerow([title for title, _ in _ROW_COLUMNS["portfolio"]])
    for row in rows:
        writer.writerow([_safe_cell(row.get(key)) for _, key in _ROW_COLUMNS["portfolio"]])
    return ("\ufeff" + output.getvalue()).encode("utf-8")


def _scorecard_presentation(
    scorecard_name: str,
    scorecard_ref: str,
    rows: list[Mapping[str, Any]],
    stakeholder_view: Mapping[str, Any],
    score_artifacts: list[list[Mapping[str, Any]]],
) -> bytes:
    issues = [
        dict(row) for row in stakeholder_view.get("questions_and_issues", [])
        if (
            row.get("scorecard_ref") == scorecard_ref
            or (
                not row.get("scorecard_ref")
                and row.get("scorecard_name") == scorecard_name
            )
        )
    ]
    return _json({
        "scorecard_name": scorecard_name,
        "scorecard_ref": scorecard_ref,
        "scores": [
            {**dict(row), "artifacts": [dict(artifact) for artifact in artifacts]}
            for row, artifacts in zip(rows, score_artifacts)
        ],
        "questions_and_issues": issues,
    })


def build_scorecard_artifacts(
    stakeholder_view: Mapping[str, Any],
    *,
    revision_number: int,
    task_id: str,
    uploader: Callable[[str, str, bytes], str],
) -> list[dict[str, Any]]:
    """Publish one safe Markdown summary and quantitative CSV per scorecard."""
    _validate_view(stakeholder_view)
    grouped: dict[tuple[str, str], list[Mapping[str, Any]]] = {}
    for row in stakeholder_view.get("portfolio", []):
        scorecard_name = str(row.get("scorecard_name") or "Unlabeled scorecard")
        stable_key = str(row.get("scorecard_ref") or scorecard_name)
        grouped.setdefault((stable_key, scorecard_name), []).append(row)

    descriptors: list[dict[str, Any]] = []
    for (stable_key, scorecard_name), rows in sorted(grouped.items(), key=lambda item: item[0][1].casefold()):
        scope_hash = sha256(stable_key.encode("utf-8")).hexdigest()[:16]
        score_artifacts: list[list[Mapping[str, Any]]] = []
        for row_index, row in enumerate(rows):
            score_name = str(row.get("score_name") or "Unlabeled score")
            score_hash = sha256(
                f"{stable_key}\0{score_name}\0{row_index}".encode("utf-8")
            ).hexdigest()[:16]
            content = _score_brief_markdown(
                scorecard_name,
                stable_key,
                row,
                stakeholder_view,
            )
            filename = f"score-{score_hash}-brief-r{revision_number:04d}.md"
            object_key = uploader(task_id, filename, content)
            descriptor = _artifact_descriptor(
                logical_id=f"score_brief:{score_hash}",
                kind="score_brief",
                display_name="Score brief",
                scope="score",
                content_type="text/markdown",
                content=content,
                object_key=object_key,
                task_id=task_id,
                source_revision=revision_number,
                scorecard_name=scorecard_name,
                score_name=score_name,
            )
            descriptors.append(descriptor)
            score_artifacts.append([descriptor])
        artifacts = (
            (
                "scorecard_summary",
                "Summary",
                "text/markdown",
                f"scorecard-{scope_hash}-summary-r{revision_number:04d}.md",
                _scorecard_summary_markdown(
                    scorecard_name,
                    stable_key,
                    rows,
                    stakeholder_view,
                ),
            ),
            (
                "scorecard_portfolio_csv",
                "Quantitative results",
                "text/csv",
                f"scorecard-{scope_hash}-portfolio-r{revision_number:04d}.csv",
                _scorecard_csv(rows),
            ),
            (
                "scorecard_presentation",
                "Interactive score details",
                "application/json",
                f"scorecard-{scope_hash}-presentation-r{revision_number:04d}.json",
                _scorecard_presentation(
                    scorecard_name,
                    stable_key,
                    rows,
                    stakeholder_view,
                    score_artifacts,
                ),
            ),
        )
        for kind, display_name, content_type, filename, content in artifacts:
            object_key = uploader(task_id, filename, content)
            descriptors.append(_artifact_descriptor(
                logical_id=f"{kind}:{scope_hash}",
                kind=kind,
                display_name=display_name,
                scope="scorecard",
                content_type=content_type,
                content=content,
                object_key=object_key,
                task_id=task_id,
                source_revision=revision_number,
                scorecard_name=scorecard_name,
            ))
    return descriptors


def _primary_decision_category(row: Mapping[str, Any]) -> str:
    action = str(row.get("next_action") or "").strip().lower()
    if "optimiz" in action:
        return "optimize"
    if "promot" in action:
        return "promotion_review"
    if "question" in action or "clarif" in action or "stakeholder" in action:
        return "stakeholder_clarification"
    if "repair" in action or "guideline" in action or "rubric" in action:
        return "repair"
    if "collect" in action or "feedback" in action:
        return "targeted_feedback"
    if "cooldown" in action or action.startswith("wait"):
        return "cooldown"
    if "monitor" in action:
        return "monitoring"
    return "review_or_insufficient_evidence"


def build_stakeholder_presentation(
    stakeholder_view: Mapping[str, Any],
    *,
    scorecard_artifacts: list[Mapping[str, Any]],
) -> dict[str, Any]:
    """Build the safe, deterministic aggregate/card projection for the dashboard."""
    _validate_view(stakeholder_view)
    rows = list(stakeholder_view.get("portfolio", []))
    primary_decision_mix: dict[str, int] = {}
    grouped: dict[tuple[str, str], list[Mapping[str, Any]]] = {}
    for row in rows:
        category = _primary_decision_category(row)
        primary_decision_mix[category] = primary_decision_mix.get(category, 0) + 1
        scorecard_name = str(row.get("scorecard_name") or "Unlabeled scorecard")
        scorecard_ref = str(row.get("scorecard_ref") or scorecard_name)
        grouped.setdefault((scorecard_ref, scorecard_name), []).append(row)

    secondary_issue_counts: dict[str, int] = {}
    for issue in stakeholder_view.get("questions_and_issues", []):
        kind = str(issue.get("kind") or "other issue")
        secondary_issue_counts[kind] = secondary_issue_counts.get(kind, 0) + 1

    artifacts_by_ref: dict[str, list[Mapping[str, Any]]] = {}
    for artifact in scorecard_artifacts:
        logical_id = str(artifact.get("logical_id") or "")
        scope_hash = logical_id.rsplit(":", 1)[-1]
        artifacts_by_ref.setdefault(scope_hash, []).append(dict(artifact))

    scorecards: list[dict[str, Any]] = []
    for (scorecard_ref, scorecard_name), score_rows in sorted(
        grouped.items(), key=lambda item: item[0][1].casefold()
    ):
        scope_hash = sha256(scorecard_ref.encode("utf-8")).hexdigest()[:16]
        decision_mix: dict[str, int] = {}
        for row in score_rows:
            category = _primary_decision_category(row)
            decision_mix[category] = decision_mix.get(category, 0) + 1
        scorecards.append({
            "scorecard_ref": scorecard_ref,
            "scorecard_name": scorecard_name,
            "score_count": len(score_rows),
            "primary_decision_mix": decision_mix,
            "reviewed_error_opportunity": sum(
                float(row.get("reviewed_error_opportunity") or 0)
                for row in score_rows
                if isinstance(row.get("reviewed_error_opportunity"), (int, float))
            ),
            "artifacts": artifacts_by_ref.get(scope_hash, []),
        })

    overview = dict(stakeholder_view.get("overview") or {})
    try:
        priority_display_limit = max(0, int(overview.get("priority_display_limit") or 10))
    except (TypeError, ValueError):
        priority_display_limit = 10
    priorities = sorted(
        stakeholder_view.get("priorities", []),
        key=lambda row: float(row.get("opportunity") or 0)
        if isinstance(row.get("opportunity"), (int, float)) else 0.0,
        reverse=True,
    )[:priority_display_limit]
    opportunity_distribution = sorted(
        ({
            "evidence_rank": row.get("evidence_rank", row.get("rank")),
            "candidate_rank": row.get("candidate_rank"),
            "scorecard_name": row.get("scorecard_name"),
            "score_name": row.get("score_name"),
            "opportunity": row.get("reviewed_error_opportunity"),
            "valid_feedback_count": row.get("valid_feedback_count"),
            "disagreement_rate": row.get("disagreement_rate"),
            "review_disposition": row.get("review_disposition", "eligible_below_selection"),
            "policy_disposition": row.get("policy_disposition", "eligible"),
            "policy_reason": row.get("policy_reason", "meets_rank_policy"),
            "eligibility_timestamp": row.get("eligibility_timestamp"),
            "next_action": row.get("next_action"),
            "dashboard_url": row.get("dashboard_url"),
        } for row in rows),
        key=lambda row: int(row.get("evidence_rank") or 10**9),
    )
    return {
        "overview": overview,
        "score_count": len(rows),
        "scorecard_count": len(scorecards),
        "primary_decision_mix": primary_decision_mix,
        "secondary_issue_counts": secondary_issue_counts,
        "opportunity_distribution": opportunity_distribution,
        "top_priorities": [dict(row) for row in priorities],
        "scorecards": scorecards,
    }


class OptimizationRunReportService:
    """Publish a periodic run to one stable Report and append-only revisions."""

    def __init__(
        self,
        *,
        client: Any,
        account_id: str,
        run_key: str,
        report_configuration_id: Optional[str] = None,
        dashboard_base_url: Optional[str] = None,
        existing_task: Any = None,
        now: Callable[[], datetime] = _utc_now,
        task_lookup: Optional[Callable[[str], Any]] = None,
        report_lookup: Optional[Callable[[Any], Any]] = None,
        block_lookup: Optional[Callable[[Any], list[Any]]] = None,
        stage_lookup: Optional[Callable[[Any], list[Any]]] = None,
        artifact_uploader: Optional[Callable[[str, str, bytes], str]] = None,
        artifact_store: Optional[Any] = None,
        verify_uploaded_artifacts: bool = True,
        attempt_id_factory: Callable[[], str] = lambda: str(uuid4()),
    ) -> None:
        if not account_id or not run_key:
            raise ValueError("account_id and run_key are required")
        self.client = client
        self.account_id = account_id
        self.run_key = run_key
        self.report_configuration_id = report_configuration_id
        self.dashboard_base_url = _normalize_dashboard_base_url(dashboard_base_url)
        self._existing_task = existing_task
        self._uses_existing_task = existing_task is not None
        self.now = now
        self._task_lookup = task_lookup or self._find_task
        self._report_lookup = report_lookup or self._find_report
        self._block_lookup = block_lookup or self._find_blocks
        self._stage_lookup = stage_lookup or self._find_stages
        self._artifact_store = artifact_store
        if self._artifact_store is None and artifact_uploader is None:
            self._artifact_store = GraphQLArtifactStore(client)
        self._verify_uploaded_artifacts = bool(verify_uploaded_artifacts)
        self._attempt_id_factory = attempt_id_factory
        self._artifact_uploader = artifact_uploader or self._upload_task_attachment
        self._state: Optional[OptimizationRunReportState] = None

    def start_or_resume(self, run_spec: Mapping[str, Any]) -> OptimizationRunReportState:
        if self._state is not None:
            if not _same_run_spec(self._state.run_spec, run_spec):
                raise ValueError("a run key cannot be reused with a different frozen run specification")
            return self._state
        operator_identity = optimization_operator_identity(
            scope=run_spec.get("scope") if isinstance(run_spec, Mapping) else None,
        )
        task = self._existing_task if self._uses_existing_task else self._task_lookup(self.run_key)
        created_new_attempt = False
        predecessor: dict[str, Any] = {}
        if task is not None:
            existing_metadata = _metadata(getattr(task, "metadata", {}))
            existing_run_key = str(existing_metadata.get("optimization_run_key") or "")
            if self._uses_existing_task and existing_run_key and existing_run_key != self.run_key:
                raise ValueError("existing Procedure Task is already claimed by another optimization run")
            if self._uses_existing_task and not existing_metadata.get("optimization_run_key"):
                if str(getattr(task, "accountId", self.account_id)) != self.account_id:
                    raise ValueError("existing Procedure Task belongs to a different account")
                attempt_id = self._attempt_id_factory()
                if not isinstance(attempt_id, str) or not attempt_id:
                    raise ValueError("attempt_id_factory must return a nonempty string")
                existing_metadata.update({
                    "optimization_run_key": self.run_key,
                    "attempt_id": attempt_id,
                    "lifecycle_version": LIFECYCLE_VERSION,
                    "run_spec": dict(run_spec),
                    "operator_identity": operator_identity.as_dict(),
                })
                task.update(
                    metadata=json.dumps(existing_metadata),
                    description=(
                        f"{operator_identity.display_title} — "
                        f"{operator_identity.display_scope}"
                    ),
                )
                created_new_attempt = True
            existing_spec = existing_metadata.get("run_spec")
            if isinstance(existing_spec, Mapping) and not _same_run_spec(existing_spec, run_spec):
                raise ValueError("a run key cannot be reused with a different frozen run specification")
            final_status = str(existing_metadata.get("optimization_run_final_status") or "").lower()
            if str(getattr(task, "status", "")).upper() == "FAILED" or final_status in {"failed", "blocked"}:
                if self._uses_existing_task:
                    raise ValueError("a terminal Procedure Task cannot be reused for another optimization attempt")
                previous_report = self._report_lookup(task)
                predecessor = {
                    "previous_attempt_id": existing_metadata.get("attempt_id"),
                    "previous_task_id": task.id,
                    "previous_report_id": getattr(previous_report, "id", None),
                }
                task = None
        if task is None:
            attempt_id = self._attempt_id_factory()
            if not isinstance(attempt_id, str) or not attempt_id:
                raise ValueError("attempt_id_factory must return a nonempty string")
            task_metadata = {
                "optimization_run_key": self.run_key,
                "attempt_id": attempt_id,
                "lifecycle_version": LIFECYCLE_VERSION,
                "run_spec": dict(run_spec),
                "operator_identity": operator_identity.as_dict(),
                **{key: value for key, value in predecessor.items() if value},
            }
            task = Task.create(
                client=self.client, accountId=self.account_id, type="OptimizationRunReport",
                target=f"optimization/run/{self.run_key}", command="optimization portfolio run",
                description=(
                    f"{operator_identity.display_title} — {operator_identity.display_scope}"
                ),
                status="RUNNING", dispatchStatus="LOCAL",
                startedAt=_iso(self.now()), metadata=json.dumps(task_metadata),
            )
            created_new_attempt = True
        else:
            task_metadata = _metadata(getattr(task, "metadata", {}))
            attempt_id = str(task_metadata.get("attempt_id") or "")
            if not attempt_id:
                raise ValueError("existing optimization run attempt is missing attempt_id")
        report = None
        try:
            # Publish the operator-facing cover before the fixed TaskStages and
            # ReportBlocks incur their sequential remote setup cost.
            report = None if created_new_attempt else self._report_lookup(task)
            if report is None:
                config_id = self.report_configuration_id or _get_programmatic_config_id(self.account_id, self.client)
                parameters = {
                    "_display_title": operator_identity.display_title,
                    "_display_subtitle": self._display_subtitle(operator_identity),
                    "optimization_run": {
                    "run_key": self.run_key,
                    "attempt_id": attempt_id,
                    "lifecycle_version": LIFECYCLE_VERSION,
                    "run_spec": dict(run_spec),
                    "operator_identity": operator_identity.as_dict(),
                    "latest_revision": None,
                    "revisions": [],
                    **{key: value for key, value in predecessor.items() if value},
                }}
                report = Report.create(
                    client=self.client, accountId=self.account_id, taskId=task.id,
                    name=operator_identity.display_title,
                    reportConfigurationId=config_id,
                    parameters=parameters,
                    output=self._render_report_manifest(
                        "running", None, identity=operator_identity,
                    ),
                )
            stages = (
                list(self._stage_lookup(task))
                if self._uses_existing_task
                else self._ensure_fixed_stages(task)
            )
            blocks = self._ensure_fixed_blocks(report)
            self._state = OptimizationRunReportState(
                task=task, report=report, blocks=blocks,
                stages={
                    str(getattr(stage, "name", "")).strip().lower(): stage
                    for stage in stages
                },
                run_spec=dict(run_spec), attempt_id=attempt_id,
                operator_identity=operator_identity,
            )
            running_stage = next(
                (stage for stage in stages if str(getattr(stage, "status", "")).upper() == "RUNNING"),
                stages[0] if stages else None,
            )
            if (
                not self._uses_existing_task
                and running_stage is not None
                and getattr(task, "currentStageId", None) != running_stage.id
            ):
                task.update(currentStageId=running_stage.id)
            self._ensure_initial_envelopes(self._state)
        except Exception as exc:
            message = f"Failed to durably initialize report: {exc}"
            if self._state is not None:
                self.fail(message)
            else:
                failed_metadata = _metadata(getattr(task, "metadata", {}))
                failed_metadata["optimization_run_final_status"] = "failed"
                failed_metadata["failure"] = message
                try:
                    task.update(
                        status="FAILED",
                        completedAt=_iso(self.now()),
                        metadata=json.dumps(failed_metadata),
                    )
                except Exception:
                    pass
                if report is not None:
                    try:
                        report.update(output=self._render_report_manifest(
                            "failed", None, message, identity=operator_identity,
                        ))
                    except Exception:
                        pass
            raise OptimizationRunPublicationError("Could not initialize optimization run report") from exc
        return self._state

    def publish_milestone(
        self, milestone: str, decision_evidence: Mapping[str, Any], *, stakeholder_view: Mapping[str, Any]
    ) -> PublishedRevision:
        state = self._require_state()
        if not milestone or not isinstance(decision_evidence, Mapping):
            raise ValueError("milestone and decision_evidence mapping are required")
        revision_number = self._latest_revision_number(state.report) + 1
        try:
            generated_at = self.now()
            _validate_view(stakeholder_view)
            safe_overview = dict(stakeholder_view.get("overview") or {})
            raw_evidence = _json(decision_evidence)
            evidence_checksum = sha256(raw_evidence).hexdigest()
            workbook = build_stakeholder_workbook(stakeholder_view, revision_number=revision_number, generated_at=generated_at)
            raw_path = self._artifact_uploader(state.task.id, f"optimization-evidence-r{revision_number:04d}.json", raw_evidence)
            self._attach_task_file(state.task, raw_path)
            workbook_path = self._artifact_uploader(state.task.id, f"optimization-workbook-r{revision_number:04d}.xlsx", workbook.content)
            self._attach_task_file(state.task, workbook_path)
            artifacts = [
                _artifact_descriptor(
                    logical_id="run_evidence",
                    kind="run_evidence",
                    display_name="Decision evidence",
                    scope="run",
                    content_type="application/json",
                    content=raw_evidence,
                    object_key=raw_path,
                    task_id=state.task.id,
                    source_revision=revision_number,
                ),
                _artifact_descriptor(
                    logical_id="stakeholder_workbook",
                    kind="stakeholder_workbook",
                    display_name="Stakeholder workbook",
                    scope="run",
                    content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    content=workbook.content,
                    object_key=workbook_path,
                    task_id=state.task.id,
                    source_revision=revision_number,
                ),
            ]
            scorecard_artifacts = build_scorecard_artifacts(
                stakeholder_view,
                revision_number=revision_number,
                task_id=state.task.id,
                uploader=self._artifact_uploader,
            )
            artifacts.extend(scorecard_artifacts)
            presentation = build_stakeholder_presentation(
                stakeholder_view,
                scorecard_artifacts=scorecard_artifacts,
            )
            presentation_bytes = _json(presentation)
            presentation_path = self._artifact_uploader(
                state.task.id,
                f"optimization-presentation-r{revision_number:04d}.json",
                presentation_bytes,
            )
            self._attach_task_file(state.task, presentation_path)
            presentation_artifact = _artifact_descriptor(
                logical_id="stakeholder_presentation",
                kind="stakeholder_presentation",
                display_name="Stakeholder presentation data",
                scope="run",
                content_type="application/json",
                content=presentation_bytes,
                object_key=presentation_path,
                task_id=state.task.id,
                source_revision=revision_number,
            )
            artifacts.append(presentation_artifact)
            if self.dashboard_base_url:
                for artifact in artifacts:
                    artifact["dashboard_url"] = _report_artifact_url(
                        self.dashboard_base_url,
                        report_id=state.report.id,
                        revision_number=revision_number,
                        logical_id=str(artifact["logical_id"]),
                    )
            manifest = {
                "revision": revision_number, "milestone": milestone, "published_at": _iso(generated_at),
                "coverage_complete": bool((decision_evidence.get("coverage") or {}).get("complete", decision_evidence.get("coverage_complete", False))),
                "evidence_checksum": evidence_checksum, "workbook_checksum": workbook.checksum,
                "workbook_path": workbook_path, "row_counts": dict(workbook.row_counts),
                "scorecard_count": sum(
                    1 for item in artifacts if item["kind"] == "scorecard_summary"
                ),
                "score_count": len(stakeholder_view.get("portfolio", [])),
                "artifacts": artifacts,
                "overview": safe_overview,
            }
            manifest_bytes = _json(manifest)
            manifest_checksum = sha256(manifest_bytes).hexdigest()
            manifest_path = self._artifact_uploader(state.task.id, f"optimization-revision-r{revision_number:04d}.json", manifest_bytes)
            self._attach_task_file(state.task, manifest_path)
            self._update_block(state.blocks["evidence"], raw_path, {"revision": revision_number, "milestone": milestone, "checksum": evidence_checksum})
            self._update_block(state.blocks["workbook"], workbook_path, {"revision": revision_number, "milestone": milestone, "checksum": workbook.checksum, "row_counts": dict(workbook.row_counts)})
            self._update_block(state.blocks["status"], manifest_path, {
                "type": "optimization_run_status",
                "status": "published",
                "summary": {
                    "revision": revision_number,
                    "milestone": milestone,
                    "overview": safe_overview,
                    "presentation": presentation_artifact,
                },
            })
            revision = PublishedRevision(
                number=revision_number,
                milestone=milestone,
                published_at=_iso(generated_at),
                raw_evidence_path=raw_path,
                workbook_path=workbook_path,
                manifest_path=manifest_path,
                manifest_checksum=manifest_checksum,
                manifest_size_bytes=len(manifest_bytes),
                evidence_checksum=evidence_checksum,
                workbook_checksum=workbook.checksum,
                row_counts=workbook.row_counts,
                overview=safe_overview,
                artifacts=tuple(artifacts),
            )
            self._record_latest_revision(state, revision)
            # TaskStage is the dashboard's lifecycle projection. Advance it
            # only after the immutable evidence, workbook, block pointers, and
            # Report cover page have all been made durable.
            self._advance_stage_for_milestone(milestone)
            return revision
        except Exception as exc:
            self.fail(f"Failed to durably publish {milestone}: {exc}")
            raise OptimizationRunPublicationError(f"Could not publish optimization milestone {milestone}") from exc

    def publish_progress(
        self, *, phase: str, current: int, total: int, message: str
    ) -> None:
        """Publish lightweight live progress without creating an evidence revision.

        Milestones remain the immutable audit trail.  This method updates only
        the existing analysis stage, compact status block, and Report cover so
        operators can see movement during long assessment and diagnosis loops.
        """
        state = self._require_state()
        normalized_phase = str(phase or "").strip().lower()
        normalized_message = " ".join(str(message or "").split()).strip()
        if normalized_phase not in {"assessment", "diagnosis"}:
            raise ValueError("progress phase must be assessment or diagnosis")
        if isinstance(current, bool) or isinstance(total, bool):
            raise ValueError("progress counts must be integers")
        current = int(current)
        total = int(total)
        if current < 0 or total < 0 or current > total:
            raise ValueError("progress counts must satisfy 0 <= current <= total")
        if not normalized_message:
            raise ValueError("progress message is required")

        progress = {
            "phase": normalized_phase,
            "current": current,
            "total": total,
            "message": normalized_message,
            "updated_at": _iso(self.now()),
        }
        try:
            stage = (
                state.stages.get(normalized_phase)
                or state.stages.get("analysis")
            )
            if stage is None:
                raise RuntimeError("missing analysis TaskStage for live progress")
            stage.update(
                processedItems=current,
                totalItems=total,
                statusMessage=normalized_message[:1000],
            )

            status_block = state.blocks["status"]
            compact = _metadata(getattr(status_block, "output", {}))
            preview = dict(compact.get("preview") or {})
            summary = dict(preview.get("summary") or {})
            summary["live_progress"] = progress
            preview["summary"] = summary
            compact["preview"] = preview
            status_block.update(
                output=json.dumps(compact),
                log="Live progress; see immutable revisions in attachedFiles.",
            )

            state.report.update(output=self._render_report_manifest(
                "RUNNING",
                self._latest_revision(state.report),
                identity=state.operator_identity,
                live_progress=progress,
            ))
        except Exception as exc:
            self.fail(f"Failed to publish live {normalized_phase} progress: {exc}")
            raise OptimizationRunPublicationError(
                f"Could not publish live {normalized_phase} progress"
            ) from exc

    def finalize(self, *, status: str = "completed") -> OptimizationRunReportState:
        """Finish a run while preserving its stakeholder-visible terminal state.

        ``Task.status`` has no distinct incomplete/blocked terminal values, so
        it remains ``COMPLETED`` for a safely concluded non-failure run.  The
        precise lifecycle outcome is retained in immutable task metadata and
        the Report cover page rather than being mislabeled as a failure.
        """
        state = self._require_state()
        terminal_status = str(status or "completed").lower()
        if terminal_status not in _FINAL_STATES:
            raise ValueError(f"unsupported optimization run terminal status: {status}")
        if terminal_status == "failed":
            return self.fail("Optimization run finalized as failed")
        try:
            task_metadata = _metadata(getattr(state.task, "metadata", {}))
            task_metadata["optimization_run_final_status"] = terminal_status
            state.report.update(output=self._render_report_manifest(
                terminal_status,
                self._latest_revision(state.report),
                identity=state.operator_identity,
            ))
            if self._uses_existing_task:
                # The outer Tactus procedure remains the lifecycle authority
                # for its Task and coarse stages.
                state.task.update(metadata=json.dumps(task_metadata))
            else:
                self._complete_all_stages()
                state.task.update(
                    status="COMPLETED",
                    completedAt=_iso(self.now()),
                    metadata=json.dumps(task_metadata),
                )
            return state
        except Exception as exc:
            self.fail(f"Failed to finalize report: {exc}")
            raise OptimizationRunPublicationError("Could not finalize optimization run report") from exc

    def fail(self, message: str) -> OptimizationRunReportState:
        state = self._require_state()
        task_metadata = _metadata(getattr(state.task, "metadata", {}))
        task_metadata["optimization_run_final_status"] = "failed"
        self._fail_active_stage(str(message))
        state.task.update(
            status="FAILED", errorMessage=str(message), completedAt=_iso(self.now()),
            metadata=json.dumps(task_metadata),
        )
        try:
            state.report.update(output=self._render_report_manifest(
                "failed",
                self._latest_revision(state.report),
                message,
                identity=state.operator_identity,
            ))
        except Exception:
            # The Task failure is the canonical safety signal if the report view is unavailable.
            pass
        return state

    def _advance_stage_for_milestone(self, milestone: str) -> None:
        if self._uses_existing_task:
            return
        target_name = _MILESTONE_STAGE.get(str(milestone))
        if target_name is None:
            return
        state = self._require_state()
        target = state.stages.get(target_name)
        if target is None:
            raise RuntimeError(f"missing TaskStage for milestone {milestone}: {target_name}")
        target_order = int(getattr(target, "order", _STAGES.index(target_name)))
        changed_at = self.now()
        for stage in sorted(state.stages.values(), key=lambda item: int(getattr(item, "order", 0))):
            order = int(getattr(stage, "order", 0))
            status = str(getattr(stage, "status", "")).upper()
            if order < target_order and status not in {"COMPLETED", "FAILED"}:
                stage.update(
                    status="COMPLETED",
                    statusMessage="Complete",
                    startedAt=getattr(stage, "startedAt", None) or changed_at,
                    completedAt=changed_at,
                )
            elif order == target_order and status == "PENDING":
                stage.update(
                    status="RUNNING",
                    statusMessage=f"Publishing {milestone}",
                    startedAt=getattr(stage, "startedAt", None) or changed_at,
                )
        if getattr(state.task, "currentStageId", None) != target.id:
            state.task.update(currentStageId=target.id)

    def _complete_all_stages(self) -> None:
        if self._uses_existing_task:
            return
        state = self._require_state()
        completed_at = self.now()
        for stage in sorted(state.stages.values(), key=lambda item: int(getattr(item, "order", 0))):
            if str(getattr(stage, "status", "")).upper() in {"COMPLETED", "FAILED"}:
                continue
            stage.update(
                status="COMPLETED",
                statusMessage="Complete",
                startedAt=getattr(stage, "startedAt", None) or completed_at,
                completedAt=completed_at,
            )

    def _fail_active_stage(self, message: str) -> None:
        """Best-effort stage failure; the Task remains the canonical signal."""
        if self._uses_existing_task:
            return
        state = self._require_state()
        ordered = sorted(state.stages.values(), key=lambda item: int(getattr(item, "order", 0)))
        active = next(
            (stage for stage in ordered if str(getattr(stage, "status", "")).upper() == "RUNNING"),
            None,
        )
        if active is None:
            active = next(
                (stage for stage in ordered if str(getattr(stage, "status", "")).upper() != "COMPLETED"),
                None,
            )
        if active is None or str(getattr(active, "status", "")).upper() == "FAILED":
            return
        try:
            active.update(
                status="FAILED",
                statusMessage=message[:1000],
                completedAt=self.now(),
            )
        except Exception:
            pass

    def _require_state(self) -> OptimizationRunReportState:
        if self._state is None:
            raise RuntimeError("start_or_resume must be called before publishing")
        return self._state

    def _ensure_fixed_stages(self, task: Any) -> list[Any]:
        existing = {str(getattr(stage, "name", "")): stage for stage in self._stage_lookup(task)}
        stages: list[Any] = []
        for order, name in enumerate(_STAGES):
            stage = existing.get(name)
            if stage is None:
                stage = TaskStage.create(
                    client=self.client,
                    taskId=task.id,
                    name=name,
                    order=order,
                    status="RUNNING" if order == 0 else "PENDING",
                    statusMessage="Current stage" if order == 0 else "Waiting",
                )
            stages.append(stage)
        return stages

    def _ensure_fixed_blocks(self, report: Any) -> dict[str, Any]:
        existing = {str(getattr(block, "type", "")): block for block in self._block_lookup(report)}
        blocks: dict[str, Any] = {}
        for position, name, block_type in _BLOCK_SPECS:
            block = existing.get(block_type)
            if block is None:
                block = ReportBlock.create(
                    client=self.client, reportId=report.id, position=position, type=block_type,
                    name=name, output=json.dumps({"status": "pending", "output_compacted": True}),
                    log="Waiting for the next durable revision.",
                )
            blocks[{"OptimizationRunStatus": "status", "OptimizationDecisionEvidence": "evidence", "OptimizationStakeholderWorkbook": "workbook"}[block_type]] = block
        return blocks

    def _update_block(self, block: Any, attachment_path: str, summary: Mapping[str, Any]) -> None:
        attached = list(getattr(block, "attachedFiles", None) or [])
        if attachment_path not in attached:
            attached.append(attachment_path)
        compact = _compact_output_json_for_storage(summary, attachment_path)
        block.update(output=compact, log="See immutable revision in attachedFiles.", attachedFiles=attached)

    @staticmethod
    def _attach_task_file(task: Any, attachment_path: str) -> None:
        attached = list(getattr(task, "attachedFiles", None) or [])
        if attachment_path not in attached:
            attached.append(attachment_path)
            task.update(attachedFiles=attached)

    def _ensure_initial_envelopes(self, state: OptimizationRunReportState) -> None:
        """Give every fixed block a real compact pointer before a run advances."""
        for key, block in state.blocks.items():
            if list(getattr(block, "attachedFiles", None) or []):
                continue
            payload = {
                "kind": "optimization_run_initialization",
                "run_key": self.run_key,
                "block": key,
                "published_at": _iso(self.now()),
                "status": "running",
            }
            if key == "evidence":
                name = "optimization-run-initial-evidence.json"
                path = self._artifact_uploader(state.task.id, name, _json(payload))
                self._attach_task_file(state.task, path)
            elif key == "workbook":
                name = "optimization-workbook-r0000.xlsx"
                initial_view = {
                    "overview": {
                        "headline": state.operator_identity.display_title,
                        "lifecycle_status": "running",
                        "current_activity": "Preparing exhaustive portfolio discovery.",
                        "next_checkpoint": "Ranking begins after the run and report are durably initialized.",
                        "coverage_status": "pending",
                        "ranking_window": "pending",
                        "scorecards_inspected": 0,
                        "ranked_score_count": 0,
                        "unranked_score_count": 0,
                        "cooldown_excluded_count": 0,
                        "assessment_progress": "Not started",
                        "diagnosis_coverage": "Not started",
                        "pending_approval_count": 0,
                        "notes": "No score, guideline, champion, or feedback setting is changed automatically.",
                    },
                    "portfolio": [],
                    "priorities": [],
                    "feedback_investment": [],
                    "questions_and_issues": [],
                    "optimization_outcomes": [],
                    "definitions": {},
                }
                workbook = build_stakeholder_workbook(
                    initial_view, revision_number=0, generated_at=self.now(),
                )
                path = self._artifact_uploader(state.task.id, name, workbook.content)
                self._attach_task_file(state.task, path)
                payload = {
                    **payload,
                    "checksum": workbook.checksum,
                    "row_counts": dict(workbook.row_counts),
                }
            else:
                name = "optimization-run-initial-status.json"
                path = self._artifact_uploader(state.task.id, name, _json(payload))
                self._attach_task_file(state.task, path)
            self._update_block(block, path, payload)

    def _record_latest_revision(self, state: OptimizationRunReportState, revision: PublishedRevision) -> None:
        parameters = _metadata(getattr(state.report, "parameters", {}))
        run = dict(parameters.get("optimization_run") or {})
        latest = {
            "number": revision.number, "milestone": revision.milestone,
            "published_at": revision.published_at,
            "manifest_path": revision.manifest_path, "workbook_path": revision.workbook_path,
            "manifest": {
                "task_id": state.task.id,
                "object_key": revision.manifest_path,
                "content_type": "application/json",
                "size_bytes": revision.manifest_size_bytes,
                "sha256": revision.manifest_checksum,
            },
            "evidence_path": revision.raw_evidence_path,
            "evidence_checksum": revision.evidence_checksum, "workbook_checksum": revision.workbook_checksum,
            "row_counts": dict(revision.row_counts),
            "overview": dict(revision.overview),
        }
        revisions = list(run.get("revisions") or [])
        if any(int(item.get("number") or -1) == revision.number for item in revisions if isinstance(item, Mapping)):
            raise ValueError(f"revision {revision.number} already exists")
        revisions.append(latest)
        run["latest_revision"] = latest
        run["revisions"] = revisions
        run["run_key"] = self.run_key
        run["lifecycle_version"] = LIFECYCLE_VERSION
        run["operator_identity"] = state.operator_identity.as_dict()
        parameters["_display_title"] = state.operator_identity.display_title
        parameters["_display_subtitle"] = self._display_subtitle(state.operator_identity)
        parameters["optimization_run"] = run
        state.report.update(
            parameters=parameters,
            output=self._render_report_manifest(
                "RUNNING", latest, identity=state.operator_identity,
            ),
        )
        task_metadata = _metadata(getattr(state.task, "metadata", {}))
        task_metadata["optimization_run_key"] = self.run_key
        task_metadata["latest_revision"] = latest
        state.task.update(metadata=json.dumps(task_metadata))

    @staticmethod
    def _latest_revision_number(report: Any) -> int:
        return int(((_metadata(getattr(report, "parameters", {})).get("optimization_run") or {}).get("latest_revision") or {}).get("number") or 0)

    @staticmethod
    def _latest_revision(report: Any) -> Any:
        return ((_metadata(getattr(report, "parameters", {})).get("optimization_run") or {}).get("latest_revision"))

    @staticmethod
    def _render_report_manifest(
        status: str,
        revision: Optional[Mapping[str, Any]],
        error: Optional[str] = None,
        *,
        identity: OptimizationOperatorIdentity,
        live_progress: Optional[Mapping[str, Any]] = None,
    ) -> str:
        def safe(value: Any) -> str:
            return " ".join(str(value or "").split()).strip()

        overview = revision.get("overview") if isinstance(revision, Mapping) else {}
        overview = overview if isinstance(overview, Mapping) else {}
        milestone = safe(revision.get("milestone")) if isinstance(revision, Mapping) else ""
        normalized_status = safe(status) or "running"
        coverage = safe(overview.get("coverage_status")) or "pending"
        inventory_coverage = safe(overview.get("inventory_coverage_status")) or coverage
        analysis_coverage = safe(overview.get("analysis_coverage_status")) or coverage
        inspected = overview.get("scorecards_inspected", 0)
        in_scope = overview.get("scorecards_in_scope", 0)
        ranked = overview.get("ranked_score_count", 0)
        unranked = overview.get("unranked_score_count", 0)
        evidence_ranked = overview.get("evidence_ranked_score_count", ranked + unranked)
        cooldown = overview.get("cooldown_excluded_count", 0)
        lines = [
            f"# {identity.display_title}",
            "",
            (
                "This living report follows the linked procedure from portfolio "
                "analysis through human decisions and final outcomes."
            ),
        ]
        if revision:
            lines.extend([
                f"Latest durable revision: {revision.get('number')}",
                f"Milestone: {milestone}",
            ])
        lines.extend([
            "",
            "```block",
            "class: OptimizationRunStatus",
            "```",
            "",
            f"Status: {normalized_status}",
        ])
        current_activity = safe(overview.get("current_activity"))
        next_checkpoint = safe(overview.get("next_checkpoint"))
        if current_activity:
            lines.extend(["", "## What is happening now", "", current_activity])
        if next_checkpoint:
            lines.extend(["", "Next checkpoint: " + next_checkpoint])
        lines.extend([
            "",
            "## Coverage and progress",
            "",
            f"Portfolio inventory coverage: {inventory_coverage.title()}",
            f"Semantic analysis: {analysis_coverage.title()}",
            (
                f"Portfolio: {in_scope} scorecards in scope; {inspected} account "
                f"scorecards inspected to resolve scope; {evidence_ranked} evidence-ranked "
                f"scores; {ranked} eligible candidates; {unranked} policy-deferred or "
                f"structurally blocked scores, including {cooldown} cooldown deferrals."
            ),
        ])
        if isinstance(live_progress, Mapping):
            phase = safe(live_progress.get("phase")).title()
            current = live_progress.get("current", 0)
            total = live_progress.get("total", 0)
            unit = "scores assessed" if phase.lower() == "assessment" else "analysis steps complete"
            lines.extend([
                f"{phase}: {current} of {total} {unit}",
                safe(live_progress.get("message")),
            ])
        for label, key in (
            ("Assessment", "assessment_progress"),
            ("Diagnosis", "diagnosis_coverage"),
            ("Pending approvals", "pending_approval_count"),
        ):
            value = safe(overview.get(key))
            if value:
                lines.append(f"{label}: {value}")
        notes = safe(overview.get("notes"))
        if (
            notes
            or inventory_coverage.lower() == "incomplete"
            or analysis_coverage.lower() == "incomplete"
        ):
            lines.extend(["", "## Limitations", ""])
            if inventory_coverage.lower() == "incomplete":
                lines.append("Portfolio inventory coverage is incomplete, so rankings are partial rather than exact.")
            if analysis_coverage.lower() == "incomplete":
                lines.append("Semantic analysis is incomplete, so some findings still require review or another run.")
            if notes:
                lines.append(notes)
        lines.extend([
            "",
            "The latest stakeholder workbook and immutable evidence are available in this Report's artifact blocks.",
        ])
        if error:
            lines.extend(["", f"Publication error: {safe(error)}"])
        return "\n".join(lines)

    @staticmethod
    def _display_subtitle(identity: OptimizationOperatorIdentity) -> str:
        if identity.kind == "account_wide_portfolio":
            return "Periodic analysis across all scorecards"
        if identity.kind == "scorecard_scoped_portfolio":
            return "Focused scorecard portfolio analysis"
        if identity.kind == "single_score":
            return "Focused analysis and optimization of one score"
        return "Living optimization analysis"

    def _find_task(self, run_key: str) -> Any:
        # This is intentionally bounded client-side discovery until a dedicated
        # run-key index/claim exists. The deterministic run key still makes a
        # resumed process reuse the same durable state.
        query = """
        query ListOptimizationRunTasks($accountId: String!, $nextToken: String) {
          listTaskByAccountIdAndUpdatedAt(accountId: $accountId, limit: 100, sortDirection: DESC, nextToken: $nextToken) {
            items { id accountId type status target command metadata createdAt updatedAt startedAt completedAt }
            nextToken
          }
        }
        """
        token = None
        while True:
            result = self.client.execute(query, {"accountId": self.account_id, "nextToken": token})
            page = (result or {}).get("listTaskByAccountIdAndUpdatedAt") or {}
            for item in page.get("items") or []:
                if _metadata(item.get("metadata")).get("optimization_run_key") == run_key:
                    return Task.from_dict(item, self.client)
            token = page.get("nextToken")
            if not token:
                return None

    def _find_report(self, task: Any) -> Any:
        for report in Report.list_by_account_id(self.account_id, self.client, limit=100, max_items=500):
            if getattr(report, "taskId", None) == task.id:
                return report
        return None

    def _find_blocks(self, report: Any) -> list[Any]:
        return ReportBlock.list_by_report_id(report.id, self.client, limit=100, max_items=100)

    @staticmethod
    def _find_stages(task: Any) -> list[Any]:
        return list(task.get_stages())

    def _upload_task_attachment(self, task_id: str, name: str, content: bytes) -> str:
        if self._artifact_store is None:
            raise OptimizationRunPublicationError("GraphQL artifact store is unavailable")
        digest = sha256(content).hexdigest()
        content_type = (
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            if name.endswith(".xlsx")
            else "text/markdown"
            if name.endswith(".md")
            else "text/csv"
            if name.endswith(".csv")
            else "application/json"
        )
        write_request = ArtifactTransferRequest(
            operation="WRITE",
            resource_type="TASK",
            resource_id=task_id,
            artifact_type="TASK_ATTACHMENT",
            filename=name,
            content_type=content_type,
            size_bytes=len(content),
            sha256=digest,
        )
        metadata = self._artifact_store.upload_bytes(write_request, content)
        if not isinstance(metadata, Mapping) or metadata.get("sha256") != digest:
            raise OptimizationRunPublicationError("artifact upload did not preserve its checksum")
        object_key = metadata.get("_s3_key")
        if not isinstance(object_key, str) or not object_key:
            raise OptimizationRunPublicationError("artifact upload omitted its object key")
        reader = getattr(self._artifact_store, "download_bytes", None)
        if self._verify_uploaded_artifacts and callable(reader):
            read_request = ArtifactTransferRequest(
                operation="READ",
                resource_type="TASK",
                resource_id=task_id,
                artifact_type="TASK_ATTACHMENT",
                filename=name,
                content_type=content_type,
                size_bytes=len(content),
                sha256=digest,
            )
            downloaded = reader(read_request)
            if downloaded != content or sha256(downloaded).hexdigest() != digest:
                raise OptimizationRunPublicationError("artifact read-back checksum did not match")
        return object_key

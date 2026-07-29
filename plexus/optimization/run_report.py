"""Durable, append-only reporting for one periodic optimization run.

The service deliberately owns no optimization orchestration.  Callers execute
the decision stages with ``persist=False`` and publish their returned packets at
well-defined milestones.  A single Task is the lifecycle authority; one Report
is its stable stakeholder location; ReportBlocks contain only compact pointers
to immutable JSON/XLSX revisions.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from io import BytesIO
import json
from typing import Any, Callable, Mapping, Optional
from uuid import uuid4
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Font
from openpyxl.writer.excel import ExcelWriter
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
_FINAL_STATES = {
    "completed", "complete_with_unresolved_actions", "incomplete", "blocked", "failed",
}

_ROW_COLUMNS: dict[str, tuple[tuple[str, str], ...]] = {
    "portfolio": (
        ("Scorecard", "scorecard_name"), ("Score", "score_name"),
        ("Valid Feedback", "valid_feedback_count"),
        ("Reviewed Disagreements", "reviewed_disagreements"),
        ("Disagreement Rate", "disagreement_rate"),
        ("Reviewed Error Opportunity", "reviewed_error_opportunity"),
        ("Coverage", "coverage_status"), ("Recent Trend", "trend"),
        ("Collection State", "collection_state"), ("Guideline State", "guideline_state"),
        ("Feedback/Rubric State", "feedback_rubric_state"), ("Readiness", "readiness"),
        ("Promotion Readiness", "promotion_readiness"), ("Rationale", "rationale"),
        ("Next Action", "next_action"), ("Dashboard Link", "dashboard_url"),
    ),
    "priorities": (
        ("Scorecard", "scorecard_name"), ("Score", "score_name"),
        ("Evidence Count", "evidence_count"), ("Opportunity", "opportunity"),
        ("State", "state"), ("Coverage", "coverage_status"), ("Recent Trend", "trend"),
        ("Collection State", "collection_state"), ("Readiness", "readiness"),
        ("Promotion Readiness", "promotion_readiness"), ("Rationale", "rationale"),
        ("Next Action", "next_action"), ("Dashboard Link", "dashboard_url"),
    ),
    "feedback_investment": (
        ("Scorecard", "scorecard_name"), ("Score", "score_name"),
        ("Evidence Count", "evidence_count"), ("State", "state"),
        ("Coverage", "coverage_status"), ("Recent Trend", "trend"),
        ("Recommendation", "recommendation"), ("Readiness", "readiness"),
        ("Rationale", "rationale"), ("Next Action", "next_action"),
        ("Dashboard Link", "dashboard_url"),
    ),
    "questions_and_issues": (
        ("Type", "kind"), ("Scorecard", "scorecard_name"), ("Score", "score_name"),
        ("Evidence Count", "evidence_count"), ("State", "state"),
        ("Coverage", "coverage_status"), ("Guideline State", "guideline_state"),
        ("Feedback/Rubric State", "feedback_rubric_state"),
        ("Question or Issue", "finding"), ("Rationale", "rationale"),
        ("Next Action", "next_action"), ("Dashboard Link", "dashboard_url"),
    ),
    "optimization_outcomes": (
        ("Scorecard", "scorecard_name"), ("Score", "score_name"),
        ("Evidence Count", "evidence_count"), ("Outcome", "outcome"),
        ("Evidence Status", "evidence_status"), ("Coverage", "coverage_status"),
        ("Recent Trend", "trend"), ("Collection State", "collection_state"),
        ("Readiness", "readiness"), ("Promotion Readiness", "promotion_readiness"),
        ("Rationale", "rationale"), ("Next Action", "next_action"),
        ("Dashboard Link", "dashboard_url"),
    ),
}
_OVERVIEW_KEYS = {"headline", "coverage_status", "ranking_window", "ranked_score_count", "notes"}


class OptimizationRunPublicationError(RuntimeError):
    """A milestone could not be made durable, so the run must stop."""


@dataclass
class OptimizationRunReportState:
    task: Any
    report: Any
    blocks: dict[str, Any]
    run_spec: Mapping[str, Any]
    attempt_id: str


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
    evidence_checksum: str
    workbook_checksum: str
    row_counts: Mapping[str, int]


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _json(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str).encode("utf-8")


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
        allowed = {key for _, key in columns}
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


class OptimizationRunReportService:
    """Publish a periodic run to one stable Report and append-only revisions."""

    def __init__(
        self,
        *,
        client: Any,
        account_id: str,
        run_key: str,
        report_configuration_id: Optional[str] = None,
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
        task = self._task_lookup(self.run_key)
        predecessor: dict[str, Any] = {}
        if task is not None:
            existing_metadata = _metadata(getattr(task, "metadata", {}))
            existing_spec = existing_metadata.get("run_spec")
            if isinstance(existing_spec, Mapping) and not _same_run_spec(existing_spec, run_spec):
                raise ValueError("a run key cannot be reused with a different frozen run specification")
            final_status = str(existing_metadata.get("optimization_run_final_status") or "").lower()
            if str(getattr(task, "status", "")).upper() == "FAILED" or final_status in {"failed", "blocked"}:
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
                **{key: value for key, value in predecessor.items() if value},
            }
            task = Task.create(
                client=self.client, accountId=self.account_id, type="OptimizationRunReport",
                target=f"optimization/run/{self.run_key}", command="optimization portfolio run",
                description="Durable periodic optimization report", status="RUNNING", dispatchStatus="LOCAL",
                startedAt=_iso(self.now()), metadata=json.dumps(task_metadata),
            )
        else:
            task_metadata = _metadata(getattr(task, "metadata", {}))
            attempt_id = str(task_metadata.get("attempt_id") or "")
            if not attempt_id:
                raise ValueError("existing optimization run attempt is missing attempt_id")
        self._ensure_fixed_stages(task)
        report = self._report_lookup(task)
        if report is None:
            config_id = self.report_configuration_id or _get_programmatic_config_id(self.account_id, self.client)
            parameters = {"optimization_run": {
                "run_key": self.run_key,
                "attempt_id": attempt_id,
                "lifecycle_version": LIFECYCLE_VERSION,
                "run_spec": dict(run_spec),
                "latest_revision": None,
                "revisions": [],
                **{key: value for key, value in predecessor.items() if value},
            }}
            report = Report.create(
                client=self.client, accountId=self.account_id, taskId=task.id,
                name="Optimization Run", reportConfigurationId=config_id, parameters=parameters,
                output=self._render_report_manifest("running", None),
            )
        blocks = self._ensure_fixed_blocks(report)
        self._state = OptimizationRunReportState(
            task=task, report=report, blocks=blocks, run_spec=dict(run_spec), attempt_id=attempt_id,
        )
        try:
            self._ensure_initial_envelopes(self._state)
        except Exception as exc:
            self.fail(f"Failed to durably initialize report: {exc}")
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
            raw_evidence = _json(decision_evidence)
            evidence_checksum = sha256(raw_evidence).hexdigest()
            workbook = build_stakeholder_workbook(stakeholder_view, revision_number=revision_number, generated_at=generated_at)
            raw_path = self._artifact_uploader(state.task.id, f"optimization-evidence-r{revision_number:04d}.json", raw_evidence)
            self._attach_task_file(state.task, raw_path)
            workbook_path = self._artifact_uploader(state.task.id, f"optimization-workbook-r{revision_number:04d}.xlsx", workbook.content)
            self._attach_task_file(state.task, workbook_path)
            manifest = {
                "revision": revision_number, "milestone": milestone, "published_at": _iso(generated_at),
                "coverage_complete": bool((decision_evidence.get("coverage") or {}).get("complete", decision_evidence.get("coverage_complete", False))),
                "evidence_checksum": evidence_checksum, "workbook_checksum": workbook.checksum,
                "workbook_path": workbook_path, "row_counts": dict(workbook.row_counts),
            }
            manifest_bytes = _json(manifest)
            manifest_path = self._artifact_uploader(state.task.id, f"optimization-revision-r{revision_number:04d}.json", manifest_bytes)
            self._attach_task_file(state.task, manifest_path)
            self._update_block(state.blocks["evidence"], raw_path, {"revision": revision_number, "milestone": milestone, "checksum": evidence_checksum})
            self._update_block(state.blocks["workbook"], workbook_path, {"revision": revision_number, "milestone": milestone, "checksum": workbook.checksum, "row_counts": dict(workbook.row_counts)})
            self._update_block(state.blocks["status"], manifest_path, manifest)
            revision = PublishedRevision(
                number=revision_number,
                milestone=milestone,
                published_at=_iso(generated_at),
                raw_evidence_path=raw_path,
                workbook_path=workbook_path,
                manifest_path=manifest_path,
                evidence_checksum=evidence_checksum,
                workbook_checksum=workbook.checksum,
                row_counts=workbook.row_counts,
            )
            self._record_latest_revision(state, revision)
            return revision
        except Exception as exc:
            self.fail(f"Failed to durably publish {milestone}: {exc}")
            raise OptimizationRunPublicationError(f"Could not publish optimization milestone {milestone}") from exc

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
            state.report.update(output=self._render_report_manifest(terminal_status, self._latest_revision(state.report)))
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
        state.task.update(
            status="FAILED", errorMessage=str(message), completedAt=_iso(self.now()),
            metadata=json.dumps(task_metadata),
        )
        try:
            state.report.update(output=self._render_report_manifest("failed", self._latest_revision(state.report), message))
        except Exception:
            # The Task failure is the canonical safety signal if the report view is unavailable.
            pass
        return state

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
                        "headline": "Optimization run started",
                        "coverage_status": "pending",
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
            "evidence_path": revision.raw_evidence_path,
            "evidence_checksum": revision.evidence_checksum, "workbook_checksum": revision.workbook_checksum,
            "row_counts": dict(revision.row_counts),
        }
        revisions = list(run.get("revisions") or [])
        if any(int(item.get("number") or -1) == revision.number for item in revisions if isinstance(item, Mapping)):
            raise ValueError(f"revision {revision.number} already exists")
        revisions.append(latest)
        run["latest_revision"] = latest
        run["revisions"] = revisions
        run["run_key"] = self.run_key
        run["lifecycle_version"] = LIFECYCLE_VERSION
        parameters["optimization_run"] = run
        state.report.update(parameters=parameters, output=self._render_report_manifest("RUNNING", latest))
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
    def _render_report_manifest(status: str, revision: Optional[Mapping[str, Any]], error: Optional[str] = None) -> str:
        lines = ["# Optimization Run", "", f"Status: {status}"]
        if revision:
            lines.append(f"Latest durable revision: {revision.get('number')}")
            lines.append(f"Milestone: {revision.get('milestone')}")
        if error:
            lines.extend(["", f"Publication error: {error}"])
        return "\n".join(lines)

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
            if name.endswith(".xlsx") else "application/json"
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

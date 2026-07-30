"""Outside-in tests for the durable optimization run report lifecycle."""

from __future__ import annotations

from datetime import datetime, timezone
from io import BytesIO
import csv
from copy import deepcopy
import inspect
import json
from types import SimpleNamespace
from zipfile import ZipFile

import pytest
from openpyxl import load_workbook


class _Task:
    created: list["_Task"] = []

    def __init__(self, identifier: str = "task-1", **values):
        self.id = identifier
        self.accountId = values.get("accountId", "account-1")
        self.type = values.get("type")
        self.description = values.get("description")
        self.status = values.get("status", "RUNNING")
        self.metadata = values.get("metadata", {})
        self.attachedFiles = list(values.get("attachedFiles") or [])
        self.currentStageId = values.get("currentStageId")
        self.updates: list[dict] = []

    @classmethod
    def create(cls, **values):
        task = cls(identifier=f"task-{len(cls.created) + 1}", **values)
        cls.created.append(task)
        return task

    def update(self, **values):
        self.updates.append(values)
        self.status = values.get("status", self.status)
        self.metadata = values.get("metadata", self.metadata)
        self.attachedFiles = list(values.get("attachedFiles", self.attachedFiles))
        self.currentStageId = values.get("currentStageId", self.currentStageId)
        return self


class _Report:
    created: list["_Report"] = []

    def __init__(self, identifier: str = "report-1", **values):
        self.id = identifier
        self.taskId = values["taskId"]
        self.accountId = values["accountId"]
        self.name = values.get("name")
        self.parameters = values.get("parameters", {})
        self.output = values.get("output")
        self.updates: list[dict] = []

    @classmethod
    def create(cls, **values):
        report = cls(identifier=f"report-{len(cls.created) + 1}", **values)
        cls.created.append(report)
        return report

    def update(self, **values):
        self.updates.append(values)
        self.parameters = values.get("parameters", self.parameters)
        self.output = values.get("output", self.output)
        return self


class _Block:
    created: list["_Block"] = []

    def __init__(self, identifier: str, **values):
        self.id = identifier
        self.reportId = values["reportId"]
        self.position = values["position"]
        self.name = values["name"]
        self.type = values["type"]
        self.output = values.get("output")
        self.attachedFiles = list(values.get("attachedFiles") or [])
        self.updates: list[dict] = []

    @classmethod
    def create(cls, **values):
        block = cls(f"block-{len(cls.created) + 1}", **values)
        cls.created.append(block)
        return block

    def update(self, **values):
        self.updates.append(values)
        self.output = values.get("output", self.output)
        self.attachedFiles = list(values.get("attachedFiles", self.attachedFiles))
        return self


class _TaskStage:
    created: list["_TaskStage"] = []

    def __init__(self, identifier: str, **values):
        self.id = identifier
        self.taskId = values["taskId"]
        self.name = values["name"]
        self.order = values["order"]
        self.status = values["status"]
        self.statusMessage = values.get("statusMessage")
        self.startedAt = values.get("startedAt")
        self.completedAt = values.get("completedAt")
        self.updates: list[dict] = []

    @classmethod
    def create(cls, **values):
        stage = cls(f"stage-{len(cls.created) + 1}", **values)
        cls.created.append(stage)
        return stage

    def update(self, **values):
        self.updates.append(values)
        for key, value in values.items():
            setattr(self, key, value)
        return self


class _ArtifactStore:
    def __init__(self):
        self.uploads = []
        self.downloads = []
        self.content_by_key: dict[str, bytes] = {}

    def upload_bytes(self, request, content, **_kwargs):
        self.uploads.append((request, content))
        object_key = f"{request.resource_type.lower()}s/{request.resource_id}/{request.filename}"
        self.content_by_key[object_key] = bytes(content)
        return {
            "_s3_key": object_key,
            "sha256": request.sha256,
            "size_bytes": request.size_bytes,
            "content_type": request.content_type,
        }

    def download_bytes(self, request):
        self.downloads.append(request)
        object_key = f"{request.resource_type.lower()}s/{request.resource_id}/{request.filename}"
        return self.content_by_key[object_key]


@pytest.fixture(autouse=True)
def _reset_fakes():
    _Task.created = []
    _Report.created = []
    _Block.created = []
    _TaskStage.created = []


def _safe_view():
    return {
        "overview": {"headline": "Daily optimization findings"},
        "portfolio": [
            {
                "scorecard_name": "Example Portfolio",
                "score_name": "Priority Score",
                "valid_feedback_count": 250,
                "reviewed_disagreements": 70,
                "disagreement_rate": 0.28,
                "reviewed_error_opportunity": 70,
                "readiness": "repair_required",
                "next_action": "repair_guidelines",
            }
        ],
        "priorities": [
            {
                "scorecard_name": "Example Portfolio",
                "score_name": "Priority Score",
                "opportunity": 70,
                "rationale": "=must remain literal text",
                "next_action": "repair_guidelines",
                "dashboard_url": "https://dashboard.example/reports/summary",
            }
        ],
        "feedback_investment": [
            {
                "scorecard_name": "Example Portfolio",
                "score_name": "Priority Score",
                "recommendation": "continue_broad_collection",
                "rationale": "More reviewed examples are needed.",
            }
        ],
        "questions_and_issues": [
            {
                "kind": "guideline",
                "scorecard_name": "Example Portfolio",
                "score_name": "Priority Score",
                "finding": "Guidelines need repair.",
                "next_action": "repair_guidelines",
            }
        ],
        "optimization_outcomes": [],
        "definitions": {"Reviewed error opportunity": "Reviewed disagreements in the window."},
    }


def _service(monkeypatch, *, block_class=_Block, dashboard_base_url=None):
    from plexus.optimization import run_report

    monkeypatch.setattr(run_report, "Task", _Task)
    monkeypatch.setattr(run_report, "Report", _Report)
    monkeypatch.setattr(run_report, "ReportBlock", block_class)
    monkeypatch.setattr(run_report, "TaskStage", _TaskStage)
    return run_report.OptimizationRunReportService(
        client=SimpleNamespace(),
        account_id="account-1",
        run_key="daily-v1-2026-07-29",
        report_configuration_id="config-1",
        dashboard_base_url=dashboard_base_url,
        now=lambda: datetime(2026, 7, 29, 12, 0, tzinfo=timezone.utc),
        task_lookup=lambda _: None,
        report_lookup=lambda _: None,
        block_lookup=lambda _: [],
        stage_lookup=lambda task: [stage for stage in _TaskStage.created if stage.taskId == task.id],
        artifact_uploader=lambda task_id, name, _: f"tasks/{task_id}/{name}",
    )


def test_run_key_is_a_deterministic_fingerprint_of_account_and_frozen_spec():
    from plexus.optimization.run_report import optimization_run_key

    left = optimization_run_key("account-1", {"window": {"start": "2026-04-30T00:00:00Z"}, "scope": ["b", "a"]})
    right = optimization_run_key("account-1", {"scope": ["b", "a"], "window": {"start": "2026-04-30T00:00:00Z"}})
    changed = optimization_run_key("account-1", {"scope": ["a"], "window": {"start": "2026-04-30T00:00:00Z"}})

    assert left == right
    assert left.startswith("optimization-run-")
    assert changed != left


def test_start_or_resume_uses_one_running_task_report_and_fixed_blocks(monkeypatch):
    service = _service(monkeypatch)

    first = service.start_or_resume({"window": {"start": "2026-04-30T00:00:00Z"}})
    second = service.start_or_resume({"window": {"start": "2026-04-30T00:00:00Z"}})

    assert first.task.id == second.task.id == "task-1"
    assert first.report.id == second.report.id == "report-1"
    assert len(_Task.created) == 1
    assert len(_Report.created) == 1
    assert [(block.position, block.name, block.type) for block in _Block.created] == [
        (0, "Run Status", "OptimizationRunStatus"),
        (1, "Decision Evidence", "OptimizationDecisionEvidence"),
        (2, "Stakeholder Workbook", "OptimizationStakeholderWorkbook"),
    ]
    assert first.task.status == "RUNNING"
    metadata = json.loads(first.task.metadata)
    assert metadata["optimization_run_key"] == "daily-v1-2026-07-29"
    assert metadata["attempt_id"]


def test_start_is_self_identifying_in_the_task_report_list_and_cover(monkeypatch):
    service = _service(monkeypatch)

    state = service.start_or_resume({"scope": {}})

    assert state.task.type == "OptimizationRunReport"
    assert state.task.description == "Account-wide optimization portfolio — All scorecards"
    assert state.report.name == "Account-wide optimization portfolio"
    assert state.report.parameters["_display_title"] == "Account-wide optimization portfolio"
    assert state.report.parameters["_display_subtitle"] == "All scorecards"
    assert state.report.parameters["optimization_run"]["operator_identity"] == {
        "kind": "account_wide_portfolio",
        "display_title": "Account-wide optimization portfolio",
        "display_scope": "All scorecards",
    }
    assert state.report.output.startswith("# Account-wide optimization portfolio")
    assert "Scope: All scorecards" in state.report.output
    assert "Current phase: Preflight" in state.report.output
    assert "```block\nclass: OptimizationRunStatus\n```" in state.report.output


def test_milestone_cover_projects_safe_progress_and_preserves_identity_on_finalize(monkeypatch):
    service = _service(monkeypatch)
    state = service.start_or_resume({"scope": {}})
    view = _safe_view()
    view["overview"] = {
        "headline": "Daily optimization findings",
        "lifecycle_status": "running",
        "current_activity": "Checking deterministic readiness across the ranked portfolio.",
        "next_checkpoint": "Semantic diagnosis begins after assessment is durable.",
        "coverage_status": "incomplete",
        "ranking_window": "2026-05-01 through 2026-07-29 UTC",
        "scorecards_inspected": 56,
        "scorecards_in_scope": 4,
        "ranked_score_count": 18,
        "unranked_score_count": 92,
        "cooldown_excluded_count": 7,
        "assessment_progress": "12 of 18 ranked scores complete",
        "diagnosis_coverage": "0 of 10 selected diagnoses complete; 0 failed",
        "pending_approval_count": 0,
        "notes": "Coverage is incomplete, so priorities are partial rather than exact.",
    }

    service.publish_milestone(
        "assessment",
        {"coverage": {"complete": False}, "restricted": {"score_id": "opaque-score"}},
        stakeholder_view=view,
    )

    cover = state.report.output
    assert cover.startswith("# Account-wide optimization portfolio")
    assert "Current phase: Diagnosis" in cover
    assert "Checking deterministic readiness" in cover
    assert "Semantic diagnosis begins" in cover
    assert "Coverage: Incomplete" in cover
    assert "4 scorecards in scope" in cover
    assert "56 account scorecards inspected to resolve scope" in cover
    assert "18 ranked scores" in cover
    assert "7 cooldown exclusions" in cover
    assert "12 of 18 ranked scores complete" in cover
    assert "Coverage is incomplete" in cover
    assert "opaque-score" not in cover

    service.finalize(status="incomplete")

    assert state.report.output.startswith("# Account-wide optimization portfolio")
    assert "Status: incomplete" in state.report.output
    assert "Checking deterministic readiness" in state.report.output


def test_start_creates_the_fixed_task_stages(monkeypatch):
    service = _service(monkeypatch)

    state = service.start_or_resume({"window": {"start": "2026-04-30T00:00:00Z"}})

    assert [(stage.order, stage.name, stage.status) for stage in _TaskStage.created] == [
        (0, "preflight", "RUNNING"),
        (1, "ranking", "PENDING"),
        (2, "assessment", "PENDING"),
        (3, "diagnosis", "PENDING"),
        (4, "approval", "PENDING"),
        (5, "optimization", "PENDING"),
        (6, "review", "PENDING"),
        (7, "finalization", "PENDING"),
    ]
    assert all(stage.taskId == state.task.id for stage in _TaskStage.created)


def test_durable_milestones_advance_visible_task_stages_in_lifecycle_order(monkeypatch):
    service = _service(monkeypatch)
    service.start_or_resume({"window": {"start": "2026-04-30T00:00:00Z"}})

    service.publish_milestone(
        "started", {"coverage": {"complete": False}}, stakeholder_view=_safe_view(),
    )
    assert [stage.status for stage in _TaskStage.created] == [
        "COMPLETED", "RUNNING", "PENDING", "PENDING", "PENDING", "PENDING", "PENDING", "PENDING",
    ]
    assert _Task.created[0].currentStageId == next(
        stage.id for stage in _TaskStage.created if stage.name == "ranking"
    )

    for milestone, running_stage in (
        ("ranking", "assessment"),
        ("assessment", "diagnosis"),
        ("diagnosis", "approval"),
        ("approval", "approval"),
        ("optimization", "optimization"),
        ("optimization_review", "review"),
        ("finalization", "finalization"),
    ):
        service.publish_milestone(
            milestone, {"coverage": {"complete": True}}, stakeholder_view=_safe_view(),
        )
        target = next(stage for stage in _TaskStage.created if stage.name == running_stage)
        assert target.status == "RUNNING"
        assert _Task.created[0].currentStageId == target.id
        assert all(
            stage.status == "COMPLETED"
            for stage in _TaskStage.created
            if stage.order < target.order
        )
        assert all(
            stage.status == "PENDING"
            for stage in _TaskStage.created
            if stage.order > target.order
        )


def test_finalize_completes_every_visible_task_stage(monkeypatch):
    service = _service(monkeypatch)
    service.start_or_resume({"window": {"start": "2026-04-30T00:00:00Z"}})
    service.publish_milestone(
        "ranking", {"coverage": {"complete": True}}, stakeholder_view=_safe_view(),
    )

    service.finalize(status="incomplete")

    assert all(stage.status == "COMPLETED" for stage in _TaskStage.created)
    assert all(stage.completedAt is not None for stage in _TaskStage.created)


def test_fixed_blocks_are_immediately_backed_by_compact_artifact_envelopes(monkeypatch):
    service = _service(monkeypatch)

    service.start_or_resume({"window": {"start": "2026-04-30T00:00:00Z"}})

    for block in _Block.created:
        envelope = __import__("json").loads(block.output)
        assert envelope["output_compacted"] is True
        assert envelope["output_attachment"] in block.attachedFiles

    workbook_block = next(block for block in _Block.created if block.name == "Stakeholder Workbook")
    assert workbook_block.attachedFiles == ["tasks/task-1/optimization-workbook-r0000.xlsx"]


def test_resume_rejects_a_different_frozen_scope_for_the_same_run_key(monkeypatch):
    service = _service(monkeypatch)
    service.start_or_resume({"window": {"start": "2026-04-30T00:00:00Z"}})

    with pytest.raises(ValueError, match="frozen run specification"):
        service.start_or_resume({"window": {"start": "2026-05-01T00:00:00Z"}})


def test_recovery_reuses_existing_task_report_and_fixed_blocks(monkeypatch):
    first_service = _service(monkeypatch)
    first = first_service.start_or_resume({"window": {"start": "2026-04-30T00:00:00Z"}})
    recovered = _service(monkeypatch)
    recovered._task_lookup = lambda _: first.task
    recovered._report_lookup = lambda _: first.report
    recovered._block_lookup = lambda _: list(_Block.created)

    resumed = recovered.start_or_resume({"window": {"start": "2026-04-30T00:00:00Z"}})

    assert resumed.task is first.task
    assert resumed.report is first.report
    assert len(_Task.created) == 1
    assert len(_Report.created) == 1
    assert len(_Block.created) == 3


def test_retry_after_failed_attempt_creates_a_linked_new_task_and_report(monkeypatch):
    first_service = _service(monkeypatch)
    first = first_service.start_or_resume({"window": {"start": "2026-04-30T00:00:00Z"}})
    first_service.fail("publication failed")

    retry = _service(monkeypatch)
    retry._task_lookup = lambda _: first.task
    retry._report_lookup = lambda task: first.report if task.id == first.task.id else None
    retried = retry.start_or_resume({"window": {"start": "2026-04-30T00:00:00Z"}})

    assert retried.task.id == "task-2"
    assert retried.report.id == "report-2"
    assert first.task.status == "FAILED"
    metadata = json.loads(retried.task.metadata)
    assert metadata["previous_attempt_id"] == json.loads(first.task.metadata)["attempt_id"]
    assert metadata["previous_task_id"] == first.task.id
    assert metadata["previous_report_id"] == first.report.id


def test_retry_after_blocked_attempt_preserves_the_terminal_attempt_and_links_a_successor(monkeypatch):
    first_service = _service(monkeypatch)
    first = first_service.start_or_resume({"window": {"start": "2026-04-30T00:00:00Z"}})
    first_service.finalize(status="blocked")
    frozen_updates = list(first.task.updates)

    retry = _service(monkeypatch)
    retry._task_lookup = lambda _: first.task
    retry._report_lookup = lambda task: first.report if task.id == first.task.id else None
    retried = retry.start_or_resume({"window": {"start": "2026-04-30T00:00:00Z"}})

    assert retried.task.id == "task-2"
    assert first.task.updates == frozen_updates
    assert json.loads(retried.task.metadata)["previous_task_id"] == first.task.id


def test_publish_milestone_keeps_raw_evidence_restricted_and_points_to_latest_immutable_revision(monkeypatch):
    uploaded: list[tuple[str, str]] = []
    service = _service(monkeypatch)
    service._artifact_uploader = lambda task_id, name, _: uploaded.append(("task", name)) or f"tasks/{task_id}/{name}"
    state = service.start_or_resume({"window": {"start": "2026-04-30T00:00:00Z"}})

    revision = service.publish_milestone(
        "assessment",
        {"raw_transcript": "do not expose", "score_id": "opaque-id", "coverage": {"complete": True}},
        stakeholder_view=_safe_view(),
    )

    assert revision.number == 1
    assert revision.raw_evidence_path.startswith("tasks/task-1/")
    assert revision.workbook_path.startswith("tasks/task-1/")
    assert revision.manifest_path.startswith("tasks/task-1/")
    assert ("task", "optimization-evidence-r0001.json") in uploaded
    assert ("task", "optimization-workbook-r0001.xlsx") in uploaded
    assert ("task", "optimization-revision-r0001.json") in uploaded
    assert revision.raw_evidence_path in state.task.attachedFiles
    assert state.report.parameters["optimization_run"]["latest_revision"]["number"] == 1
    latest = state.report.parameters["optimization_run"]["latest_revision"]
    assert latest["manifest"] == {
        "task_id": state.task.id,
        "object_key": revision.manifest_path,
        "content_type": "application/json",
        "size_bytes": revision.manifest_size_bytes,
        "sha256": revision.manifest_checksum,
    }
    assert latest["manifest"]["size_bytes"] > 0
    assert len(latest["manifest"]["sha256"]) == 64
    assert [item["number"] for item in state.report.parameters["optimization_run"]["revisions"]] == [1]
    assert "raw_transcript" not in str(_Block.created[0].updates[-1])
    assert "opaque-id" not in str(_Block.created[2].updates[-1])


def test_publish_milestone_indexes_revisioned_scorecard_markdown_and_csv_without_attaching_each_child(monkeypatch):
    uploaded: dict[str, bytes] = {}
    service = _service(monkeypatch, dashboard_base_url="https://dashboard.example.com")
    service._artifact_uploader = lambda task_id, name, content: (
        uploaded.__setitem__(name, content) or f"tasks/{task_id}/{name}"
    )
    state = service.start_or_resume({"scope": {}})
    view = deepcopy(_safe_view())
    view["portfolio"][0]["scorecard_ref"] = "safe-ref-one"
    view["portfolio"][0]["score_name"] = "=Formula-like score"
    second_row = dict(view["portfolio"][0])
    second_row.update({
        "scorecard_ref": "safe-ref-two",
        "score_name": "Second Score",
        "valid_feedback_count": 75,
    })
    view["portfolio"].append(second_row)

    revision = service.publish_milestone(
        "assessment",
        {"coverage": {"complete": True}},
        stakeholder_view=view,
    )

    manifest = json.loads(uploaded["optimization-revision-r0001.json"])
    presentation_artifact = next(
        artifact for artifact in manifest["artifacts"]
        if artifact["kind"] == "stakeholder_presentation"
    )
    presentation_name = presentation_artifact["object_key"].rsplit("/", 1)[-1]
    presentation = json.loads(uploaded[presentation_name])
    assert sum(presentation["primary_decision_mix"].values()) == 2
    assert presentation["score_count"] == 2
    assert len(presentation["scorecards"]) == 2
    assert presentation["scorecards"][0]["score_count"] == 1
    assert presentation["top_priorities"][0]["opportunity"] == 70
    assert presentation_artifact["object_key"] in state.task.attachedFiles
    status_envelope = json.loads(state.blocks["status"].output)
    assert status_envelope["preview"]["type"] == "optimization_run_status"
    assert status_envelope["preview"]["summary"]["presentation"] == presentation_artifact
    scorecard_artifacts = [
        artifact for artifact in manifest["artifacts"]
        if artifact["scope"] == "scorecard"
    ]
    assert {artifact["kind"] for artifact in scorecard_artifacts} == {
        "scorecard_summary",
        "scorecard_portfolio_csv",
        "scorecard_presentation",
    }
    assert len(scorecard_artifacts) == 6
    assert manifest["scorecard_count"] == 2
    assert manifest["score_count"] == 2
    assert all(artifact["source_revision"] == 1 for artifact in scorecard_artifacts)
    assert {artifact["scorecard_name"] for artifact in scorecard_artifacts} == {"Example Portfolio"}
    assert len({artifact["logical_id"] for artifact in scorecard_artifacts}) == 6
    assert all(artifact["sha256"] and artifact["size_bytes"] > 0 for artifact in scorecard_artifacts)
    assert all(artifact["task_id"] == state.task.id for artifact in scorecard_artifacts)
    assert all(
        artifact["dashboard_url"] == (
            f"https://dashboard.example.com/lab/reports/{state.report.id}"
            f"?revision=1&artifact={artifact['logical_id'].replace(':', '%3A')}"
        )
        for artifact in scorecard_artifacts
    )
    assert all(artifact["object_key"].startswith(f"tasks/{state.task.id}/") for artifact in scorecard_artifacts)
    assert all(artifact["object_key"] not in state.task.attachedFiles for artifact in scorecard_artifacts)
    assert len(revision.artifacts) == len(manifest["artifacts"])

    csv_artifact = next(
        artifact for artifact in scorecard_artifacts
        if artifact["kind"] == "scorecard_portfolio_csv"
        and artifact["scorecard_name"] == "Example Portfolio"
    )
    csv_name = csv_artifact["object_key"].rsplit("/", 1)[-1]
    csv_rows = list(csv.DictReader(uploaded[csv_name].decode("utf-8-sig").splitlines()))
    assert len(csv_rows) == 1
    assert csv_rows[0]["Score"] == "'=Formula-like score"

    summary_artifact = next(
        artifact for artifact in scorecard_artifacts
        if artifact["kind"] == "scorecard_summary"
        and artifact["scorecard_name"] == "Example Portfolio"
    )
    summary_name = summary_artifact["object_key"].rsplit("/", 1)[-1]
    summary = uploaded[summary_name].decode("utf-8")
    assert summary.startswith("# Example Portfolio")
    assert "repair_guidelines" in summary

    detail_artifact = next(
        artifact for artifact in scorecard_artifacts
        if artifact["kind"] == "scorecard_presentation"
    )
    detail_name = detail_artifact["object_key"].rsplit("/", 1)[-1]
    detail = json.loads(uploaded[detail_name])
    assert detail["scorecard_name"] == "Example Portfolio"
    assert len(detail["scores"]) == 1
    assert detail["scores"][0]["score_name"] == "=Formula-like score"


def test_report_artifact_base_url_rejects_non_https_or_non_origin_values(monkeypatch):
    for value in (
        "http://dashboard.example.com",
        "https://dashboard.example.com/path",
        "https://user:secret@dashboard.example.com",
    ):
        with pytest.raises(ValueError, match="HTTPS origin"):
            _service(monkeypatch, dashboard_base_url=value)


def test_report_artifact_base_url_comes_from_existing_account_settings():
    from plexus.optimization.run_report import dashboard_base_url_from_account_settings

    assert dashboard_base_url_from_account_settings({
        "hiddenMenuItems": [],
        "reporting": {"dashboardBaseUrl": "https://dashboard.example.com/"},
    }) == "https://dashboard.example.com"
    assert dashboard_base_url_from_account_settings({"hiddenMenuItems": []}) is None
    assert dashboard_base_url_from_account_settings(None) is None


def test_multiple_milestones_preserve_full_revision_history(monkeypatch):
    service = _service(monkeypatch)
    state = service.start_or_resume({"window": {"start": "2026-04-30T00:00:00Z"}})

    service.publish_milestone("ranking", {"coverage": {"complete": True}}, stakeholder_view=_safe_view())
    service.publish_milestone("assessment", {"coverage": {"complete": True}}, stakeholder_view=_safe_view())

    history = state.report.parameters["optimization_run"]["revisions"]
    assert [revision["number"] for revision in history] == [1, 2]
    assert [revision["milestone"] for revision in history] == ["ranking", "assessment"]
    assert all(revision["evidence_path"].startswith("tasks/task-1/") for revision in history)
    assert len(state.blocks["workbook"].attachedFiles) == 3


def test_default_artifact_path_uses_only_task_graphql_tickets_without_direct_s3(monkeypatch):
    from plexus.optimization import run_report

    monkeypatch.setattr(run_report, "Task", _Task)
    monkeypatch.setattr(run_report, "TaskStage", _TaskStage)
    monkeypatch.setattr(run_report, "Report", _Report)
    monkeypatch.setattr(run_report, "ReportBlock", _Block)
    store = _ArtifactStore()
    service = run_report.OptimizationRunReportService(
        client=SimpleNamespace(),
        account_id="account-1",
        run_key="daily-v1-2026-07-29",
        report_configuration_id="config-1",
        now=lambda: datetime(2026, 7, 29, 12, 0, tzinfo=timezone.utc),
        task_lookup=lambda _: None,
        report_lookup=lambda _: None,
        block_lookup=lambda _: [],
        stage_lookup=lambda _: [],
        artifact_store=store,
        verify_uploaded_artifacts=True,
    )

    state = service.start_or_resume({"window": {"start": "2026-04-30T00:00:00Z"}})
    service.publish_milestone("assessment", {"coverage": {"complete": True}}, stakeholder_view=_safe_view())

    requests = [request for request, _content in store.uploads]
    assert all(request.resource_type == "TASK" for request in requests)
    assert all(request.resource_id == state.task.id for request in requests)
    assert all(request.artifact_type == "TASK_ATTACHMENT" for request in requests)
    assert {request.filename for request in requests} >= {
        "optimization-run-initial-status.json",
        "optimization-run-initial-evidence.json",
        "optimization-workbook-r0000.xlsx",
        "optimization-evidence-r0001.json",
        "optimization-workbook-r0001.xlsx",
        "optimization-revision-r0001.json",
    }
    assert {
        request.content_type for request in requests
        if request.filename.endswith((".md", ".csv"))
    } == {
        "text/markdown",
        "text/csv",
    }
    assert all(path.startswith(f"tasks/{state.task.id}/") for path in state.task.attachedFiles)
    child_paths = {
        f"tasks/{state.task.id}/{request.filename}"
        for request in requests
        if request.filename.startswith("scorecard-")
    }
    assert child_paths
    assert child_paths.isdisjoint(state.task.attachedFiles)
    assert len(state.task.attachedFiles) == len(store.uploads) - len(child_paths)
    assert all(
        json.loads(block.output)["output_attachment"].startswith(f"tasks/{state.task.id}/")
        for block in state.blocks.values()
    )
    assert len(store.downloads) == len(store.uploads)
    initial_workbook_upload = next(
        content for request, content in store.uploads
        if request.filename == "optimization-workbook-r0000.xlsx"
    )
    assert initial_workbook_upload.startswith(b"PK")
    source = inspect.getsource(run_report)
    assert "plexus.reports.s3_utils" not in source
    assert "upload_report_block_file" not in source
    assert "upload_procedure_file" not in source
    assert "REPORT_BLOCK_ATTACHMENT" not in source


def test_artifact_checksum_mismatch_is_fatal_and_marks_the_attempt_failed(monkeypatch):
    from plexus.optimization import run_report

    class _CorruptingStore(_ArtifactStore):
        def download_bytes(self, request):
            return super().download_bytes(request) + b"corrupt"

    monkeypatch.setattr(run_report, "Task", _Task)
    monkeypatch.setattr(run_report, "TaskStage", _TaskStage)
    monkeypatch.setattr(run_report, "Report", _Report)
    monkeypatch.setattr(run_report, "ReportBlock", _Block)
    service = run_report.OptimizationRunReportService(
        client=SimpleNamespace(), account_id="account-1", run_key="daily-v1-2026-07-29",
        report_configuration_id="config-1", task_lookup=lambda _: None,
        report_lookup=lambda _: None, block_lookup=lambda _: [], stage_lookup=lambda _: [],
        artifact_store=_CorruptingStore(), verify_uploaded_artifacts=True,
    )

    with pytest.raises(run_report.OptimizationRunPublicationError, match="initialize"):
        service.start_or_resume({"window": {"start": "2026-04-30T00:00:00Z"}})

    assert _Task.created[0].status == "FAILED"


def test_publish_failure_marks_task_failed_and_raises_without_silent_progress(monkeypatch):
    class _FailingBlock(_Block):
        def update(self, **values):
            if self.name == "Decision Evidence" and "r0001" in str(values.get("output", "")):
                raise RuntimeError("attachment envelope write failed")
            return super().update(**values)

    service = _service(monkeypatch, block_class=_FailingBlock)
    state = service.start_or_resume({"window": {"start": "2026-04-30T00:00:00Z"}})

    from plexus.optimization.run_report import OptimizationRunPublicationError

    with pytest.raises(OptimizationRunPublicationError, match="assessment"):
        service.publish_milestone("assessment", {"coverage": {"complete": True}}, stakeholder_view=_safe_view())

    assert state.task.status == "FAILED"
    assert any(update.get("status") == "FAILED" for update in state.task.updates)
    active = next(stage for stage in _TaskStage.created if stage.status == "FAILED")
    assert active.name == "preflight"
    assert "attachment envelope write failed" in active.statusMessage


def test_finalize_marks_the_single_task_complete_after_the_latest_revision(monkeypatch):
    service = _service(monkeypatch)
    state = service.start_or_resume({"window": {"start": "2026-04-30T00:00:00Z"}})
    service.publish_milestone("summary", {"coverage": {"complete": True}}, stakeholder_view=_safe_view())

    completed = service.finalize()

    assert completed is state
    assert state.task.status == "COMPLETED"
    assert "Status: completed" in state.report.output


def test_finalize_records_an_honest_incomplete_terminal_state_without_reclassifying_it_as_a_failure(monkeypatch):
    service = _service(monkeypatch)
    state = service.start_or_resume({"window": {"start": "2026-04-30T00:00:00Z"}})

    service.finalize(status="incomplete")

    assert state.task.status == "COMPLETED"
    assert __import__("json").loads(state.task.metadata)["optimization_run_final_status"] == "incomplete"
    assert "Status: incomplete" in state.report.output


@pytest.mark.parametrize(
    ("requested", "task_status"),
    [
        ("completed", "COMPLETED"),
        ("complete_with_unresolved_actions", "COMPLETED"),
        ("completed_with_unresolved_actions", "COMPLETED"),
        ("incomplete", "COMPLETED"),
        ("blocked", "COMPLETED"),
    ],
)
def test_finalize_supports_every_nonfailure_lifecycle_state(monkeypatch, requested, task_status):
    service = _service(monkeypatch)
    state = service.start_or_resume({"window": {"start": "2026-04-30T00:00:00Z"}})

    service.finalize(status=requested)

    assert state.task.status == task_status
    assert json.loads(state.task.metadata)["optimization_run_final_status"] == requested
    assert f"Status: {requested}" in state.report.output


def test_workbook_is_deterministic_macro_free_formula_safe_and_has_all_stakeholder_sheets():
    from plexus.optimization.run_report import build_stakeholder_workbook

    generated_at = datetime(2026, 7, 29, 12, 0, tzinfo=timezone.utc)
    first = build_stakeholder_workbook(_safe_view(), revision_number=1, generated_at=generated_at)
    second = build_stakeholder_workbook(_safe_view(), revision_number=1, generated_at=generated_at)

    assert first.checksum == second.checksum
    assert first.content == second.content
    workbook = load_workbook(BytesIO(first.content), data_only=False)
    assert workbook.sheetnames == [
        "Overview",
        "Portfolio",
        "Priorities",
        "Feedback Investment",
        "Questions and Issues",
        "Optimization Outcomes",
        "Run Log",
        "Definitions",
    ]
    assert first.row_counts["priorities"] == 1
    assert first.row_counts == {
        "portfolio": 1,
        "priorities": 1,
        "feedback_investment": 1,
        "questions_and_issues": 1,
        "optimization_outcomes": 0,
        "run_log": 1,
        "definitions": 1,
    }
    priority_headers = [cell.value for cell in workbook["Priorities"][1]]
    rationale_cell = workbook["Priorities"].cell(2, priority_headers.index("Rationale") + 1)
    assert rationale_cell.data_type != "f"
    assert rationale_cell.value.startswith("'")
    with ZipFile(BytesIO(first.content)) as archive:
        names = archive.namelist()
        assert not any(name.lower().endswith("vbaProject.bin".lower()) for name in names)
        core_properties = archive.read("docProps/core.xml")
        assert core_properties.count(b"2026-07-29T12:00:00Z") == 2
        content = b"".join(archive.read(name) for name in names)
        assert b"opaque-id" not in content
        assert b"do not expose" not in content
    assert all(sheet.sheet_state == "visible" for sheet in workbook.worksheets)
    assert not workbook._external_links
    assert all(cell.data_type != "f" for sheet in workbook.worksheets for row in sheet.iter_rows() for cell in row)
    assert {table.name for sheet in workbook.worksheets for table in sheet.tables.values()} >= {
        "PortfolioTable", "PrioritiesTable", "FeedbackInvestmentTable",
        "QuestionsAndIssuesTable", "OptimizationOutcomesTable", "RunLogTable", "DefinitionsTable",
    }
    assert workbook["Portfolio"].freeze_panes == "A2"
    assert workbook["Portfolio"].auto_filter.ref
    assert workbook["Portfolio"].column_dimensions["A"].width > 10


def test_workbook_overview_is_sized_and_wrapped_for_default_opening():
    from plexus.optimization.run_report import build_stakeholder_workbook

    artifact = build_stakeholder_workbook(
        _safe_view(),
        revision_number=1,
        generated_at=datetime(2026, 7, 29, 12, 0, tzinfo=timezone.utc),
    )
    overview = load_workbook(BytesIO(artifact.content))["Overview"]

    assert overview.column_dimensions["A"].width >= len("Optimization Run Overview") + 2
    assert overview.column_dimensions["B"].width >= 40
    assert all(cell.alignment.wrap_text for cell in overview["B"])


def test_workbook_rejects_unsafe_view_keys_instead_of_copying_raw_evidence():
    from plexus.optimization.run_report import build_stakeholder_workbook

    unsafe = _safe_view()
    unsafe["portfolio"][0]["score_id"] = "opaque-id"

    with pytest.raises(ValueError, match="not allowed"):
        build_stakeholder_workbook(unsafe, revision_number=1, generated_at=datetime(2026, 7, 29, tzinfo=timezone.utc))

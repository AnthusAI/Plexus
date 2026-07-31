"""Outside-in specifications for at-most-once optimizer Task dispatch."""

from __future__ import annotations

from copy import deepcopy

import pytest


def _request() -> dict:
    return {
        "account_id": "account-opaque",
        "run_key": "frozen-run-key",
        "scorecard_id": "scorecard-opaque",
        "score_id": "score-opaque",
        "assessment_fingerprint": "assessment-fingerprint",
        "limits": {
            "max_cost_usd": 5.0,
            "max_samples": 50,
            "max_iterations": 2,
            "max_concurrency": 1,
        },
        "optimizer_yaml": "name: optimizer\n" + ("# large\n" * 100),
        "stages": [
            {"name": "Setup", "order": 1, "status": "PENDING"},
            {"name": "Optimize", "order": 2, "status": "PENDING"},
        ],
    }


class _Backend:
    def __init__(self) -> None:
        self.procedures: list[dict] = []
        self.tasks: list[dict] = []
        self.create_procedure_calls = 0
        self.create_task_calls = 0
        self.upload_calls = 0
        self.release_calls = 0
        self.reconciled: list[str] = []
        self.read_artifact_calls = 0
        self.artifacts: dict[str, bytes] = {}
        self.task_stages: dict[str, list[dict]] = {}
        self.procedure_pages: list[dict] | None = None
        self.task_pages: list[dict] | None = None
        self.task_stage_pages: list[dict] | None = None
        self.raise_after_procedure_create = False
        self.raise_after_task_create = False
        self.raise_after_release = False

    def create_procedure(self, record):
        self.create_procedure_calls += 1
        row = {
            "id": f"procedure-generated-{len(self.procedures) + 1}",
            **deepcopy(record),
        }
        self.procedures.append(row)
        if self.raise_after_procedure_create:
            raise TimeoutError("procedure response lost")
        return deepcopy(row)

    def upload_and_verify_procedure_yaml(self, procedure, optimizer_yaml, metadata):
        self.upload_calls += 1
        self.uploaded_yaml = optimizer_yaml
        pointer = {
            "key": f"procedures/{procedure['id']}/code.tac",
            "sha256": metadata["optimizer_yaml_sha256"],
        }
        self.artifacts[pointer["key"]] = optimizer_yaml.encode("utf-8")
        procedure["metadata"] = {**metadata, "code_artifact": pointer}
        for row in self.procedures:
            if row["id"] == procedure["id"]:
                row["metadata"] = deepcopy(procedure["metadata"])
        return deepcopy(procedure)

    def procedure_pages_for_account(self, _account_id):
        pages = self.procedure_pages
        if pages is None:
            pages = [{"items": deepcopy(self.procedures), "next_token": None}]
        return iter(deepcopy(pages))

    def get_procedure(self, procedure_id):
        row = next((row for row in self.procedures if row["id"] == procedure_id), None)
        return deepcopy(row)

    def read_procedure_artifact(self, key):
        self.read_artifact_calls += 1
        return self.artifacts[key]

    def create_task(self, record):
        self.create_task_calls += 1
        assert record["dispatchStatus"] == "HELD"
        row = {
            "id": f"task-generated-{len(self.tasks) + 1}",
            "status": "PENDING",
            **deepcopy(record),
        }
        self.tasks.append(row)
        if self.raise_after_task_create:
            raise TimeoutError("task response lost")
        return deepcopy(row)

    def task_pages_for_account(self, _account_id):
        pages = self.task_pages
        if pages is None:
            pages = [{"items": deepcopy(self.tasks), "next_token": None}]
        return iter(deepcopy(pages))

    def reconcile_task_stages(self, task_id, stages):
        self.reconciled.append(task_id)
        assert stages == _request()["stages"]
        stored = self.task_stages.setdefault(task_id, [])
        for stage in stages:
            matches = [
                row for row in stored
                if row.get("name") == stage["name"] and row.get("order") == stage["order"]
            ]
            if len(matches) > 1:
                raise RuntimeError("ambiguous existing stage")
            if not matches:
                stored.append({
                    "id": f"stage-generated-{len(stored) + 1}",
                    "taskId": task_id,
                    **deepcopy(stage),
                })
        return deepcopy(stored)

    def task_stage_pages_for_task(self, task_id):
        pages = self.task_stage_pages
        if pages is None:
            pages = [{
                "items": deepcopy(self.task_stages.get(task_id, [])),
                "next_token": None,
            }]
        return iter(deepcopy(pages))

    def release_held_task(self, task_id):
        self.release_calls += 1
        task = next(row for row in self.tasks if row["id"] == task_id)
        assert task["dispatchStatus"] == "HELD"
        task["dispatchStatus"] = "PENDING"
        if self.raise_after_release:
            raise TimeoutError("release response lost")

    def get_task(self, task_id):
        row = next((row for row in self.tasks if row["id"] == task_id), None)
        return deepcopy(row)


class _Publisher:
    def __init__(self) -> None:
        self.states: list[dict] = []

    def __call__(self, state):
        self.states.append(deepcopy(state))


class _FailingPublisher(_Publisher):
    def __init__(self, phase: str) -> None:
        super().__init__()
        self.phase = phase
        self.last_successful: dict | None = None

    def __call__(self, state):
        if state["phase"] == self.phase:
            raise RuntimeError(f"publication failed at {self.phase}")
        super().__call__(state)
        self.last_successful = deepcopy(state)


def _launch(backend, request, published, resume_state=None):
    from plexus.optimization.optimizer_dispatch import OptimizerTaskDispatchService
    from plexus.optimization.portfolio_run import drive_optimizer_child_launch

    service = OptimizerTaskDispatchService(backend)
    return drive_optimizer_child_launch(
        request,
        initial_state=resume_state,
        step=service.step,
        publish=published,
    )


def test_happy_path_persists_each_phase_holds_then_releases_once() -> None:
    backend = _Backend()
    published = _Publisher()

    result = _launch(backend, _request(), published)

    assert [row["phase"] for row in published.states] == [
        "planned",
        "procedure_create_attempted",
        "procedure_record_observed",
        "procedure_provisioned",
        "task_create_attempted",
        "task_record_observed",
        "task_held",
        "release_attempted",
        "waiting",
    ]
    assert backend.create_procedure_calls == 1
    assert backend.create_task_calls == 1
    assert backend.reconciled == ["task-generated-1"]
    assert backend.release_calls == 1
    assert backend.tasks[0]["dispatchStatus"] == "PENDING"
    assert result["procedure_id"] == "procedure-generated-1"
    assert result["task_id"] == "task-generated-1"
    assert result["launch_spec"] == published.states[0]["launch_spec"]
    assert "optimizer_yaml" not in result["launch_spec"]
    assert published.states[3]["code_artifact"]["sha256"] == result["launch_spec"]["optimizer_yaml_sha256"]
    assert backend.tasks[0]["metadata"]["dispatch_policy"] == "held_once"


@pytest.mark.parametrize("max_cost_usd", [0, -0.01, float("inf"), float("nan")])
def test_invalid_cost_limit_rejects_before_creating_optimizer_children(max_cost_usd) -> None:
    backend = _Backend()

    request = _request()
    request["limits"]["max_cost_usd"] = max_cost_usd

    with pytest.raises(ValueError, match="max_cost_usd"):
        _launch(backend, request, _Publisher())

    assert backend.create_procedure_calls == 0
    assert backend.create_task_calls == 0
    assert backend.release_calls == 0


@pytest.mark.parametrize(
    ("failure", "expected_create_procedure", "expected_create_task", "expected_release"),
    [
        ("procedure", 1, 1, 1),
        ("task", 1, 1, 1),
        ("release", 1, 1, 1),
    ],
)
def test_ambiguous_mutation_adopts_one_exact_generated_child_without_retrying(
    failure,
    expected_create_procedure,
    expected_create_task,
    expected_release,
) -> None:
    backend = _Backend()
    setattr(backend, f"raise_after_{failure}_create" if failure != "release" else "raise_after_release", True)
    published = _Publisher()

    result = _launch(backend, _request(), published)

    assert result["phase"] == "waiting"
    assert backend.create_procedure_calls == expected_create_procedure
    assert backend.create_task_calls == expected_create_task
    assert backend.release_calls == expected_release
    assert len(backend.procedures) == 1
    assert len(backend.tasks) == 1


def test_resume_after_attempted_phase_scans_but_never_recreates() -> None:
    backend = _Backend()
    published = _Publisher()
    first = _launch(backend, _request(), published)
    attempted = next(row for row in published.states if row["phase"] == "procedure_create_attempted")
    backend.create_procedure_calls = 0
    backend.create_task_calls = 0
    backend.release_calls = 0

    replay = _launch(backend, _request(), _Publisher(), resume_state=attempted)

    assert replay["phase"] == "waiting"
    assert backend.create_procedure_calls == 0
    assert backend.create_task_calls == 0
    assert backend.release_calls == 0


@pytest.mark.parametrize("bad_pages", [
    [{"items": [], "next_token": None}],
    [{"items": "malformed", "next_token": None}],
    [{"items": [], "next_token": "cycle"}, {"items": [], "next_token": "cycle"}],
])
def test_ambiguous_procedure_scan_failure_is_unknown_and_never_recreates(bad_pages) -> None:
    backend = _Backend()
    # Capture the durable pre-mutation state without performing the mutation.
    class StopAfterAttempt:
        def __init__(self):
            self.last = None

        def __call__(self, state):
            self.last = deepcopy(state)
            if state["phase"] == "procedure_create_attempted":
                raise RuntimeError("simulated process stop")

    stop = StopAfterAttempt()
    with pytest.raises(RuntimeError, match="simulated process stop"):
        _launch(backend, _request(), stop)
    backend.procedure_pages = bad_pages
    published = _Publisher()

    result = _launch(backend, _request(), published, resume_state=stop.last)

    assert result["phase"] == "dispatch_outcome_unknown"
    assert result["complete"] is False
    assert backend.create_procedure_calls == 0
    assert backend.create_task_calls == 0
    assert backend.release_calls == 0


def test_multiple_exact_ambiguous_matches_are_unknown() -> None:
    backend = _Backend()
    published = _Publisher()
    first = _launch(backend, _request(), published)
    attempted = next(row for row in published.states if row["phase"] == "procedure_create_attempted")
    exact = deepcopy(backend.procedures[0])
    exact["id"] = "procedure-generated-duplicate"
    backend.procedures.append(exact)

    result = _launch(backend, _request(), _Publisher(), resume_state=attempted)

    assert result["phase"] == "dispatch_outcome_unknown"
    assert result["reason"] == "multiple_exact_procedure_matches"


def test_dispatching_without_celery_id_is_unknown_and_never_released_again() -> None:
    backend = _Backend()
    published = _Publisher()
    result = _launch(backend, _request(), published)
    backend.tasks[0]["dispatchStatus"] = "DISPATCHING"
    backend.tasks[0].pop("celeryTaskId", None)
    backend.release_calls = 0

    observed = _launch(backend, _request(), _Publisher(), resume_state=result)

    assert observed["phase"] == "dispatch_outcome_unknown"
    assert observed["reason"] == "dispatching_without_celery_id"
    assert backend.release_calls == 0


@pytest.mark.parametrize(
    ("phase", "procedure_creates", "uploads", "task_creates", "reconciles", "releases"),
    [
        ("procedure_create_attempted", 0, 0, 0, 0, 0),
        ("procedure_record_observed", 1, 0, 0, 0, 0),
        ("task_create_attempted", 1, 1, 0, 0, 0),
        ("task_record_observed", 1, 1, 1, 0, 0),
        ("release_attempted", 1, 1, 1, 1, 0),
    ],
)
def test_publication_failure_at_each_pre_mutation_boundary_prevents_the_mutation(
    phase, procedure_creates, uploads, task_creates, reconciles, releases,
) -> None:
    backend = _Backend()
    publisher = _FailingPublisher(phase)

    with pytest.raises(RuntimeError, match="publication failed"):
        _launch(backend, _request(), publisher)

    assert backend.create_procedure_calls == procedure_creates
    assert backend.upload_calls == uploads
    assert backend.create_task_calls == task_creates
    assert len(backend.reconciled) == reconciles
    assert backend.release_calls == releases


@pytest.mark.parametrize("lost_phase", [
    "procedure_record_observed", "task_record_observed", "waiting",
])
def test_post_mutation_publication_loss_replays_by_readback_without_repeating_mutation(
    lost_phase,
) -> None:
    backend = _Backend()
    publisher = _FailingPublisher(lost_phase)

    with pytest.raises(RuntimeError, match="publication failed"):
        _launch(backend, _request(), publisher)
    before = (
        backend.create_procedure_calls,
        backend.upload_calls,
        backend.create_task_calls,
        len(backend.reconciled),
        backend.release_calls,
    )

    result = _launch(
        backend,
        _request(),
        _Publisher(),
        resume_state=publisher.last_successful,
    )

    assert result["phase"] == "waiting"
    after = (
        backend.create_procedure_calls,
        backend.upload_calls,
        backend.create_task_calls,
        len(backend.reconciled),
        backend.release_calls,
    )
    if lost_phase == "procedure_record_observed":
        assert after[0] == before[0]
    if lost_phase == "task_record_observed":
        assert after[2] == before[2]
    if lost_phase == "waiting":
        assert after[4] == before[4]


def test_launch_spec_is_complete_immutable_and_request_mismatch_is_rejected() -> None:
    request = _request()
    published = _Publisher()
    result = _launch(_Backend(), request, published)
    spec = result["launch_spec"]

    assert spec["account_id"] == request["account_id"]
    assert spec["run_key"] == request["run_key"]
    assert spec["scorecard_id"] == request["scorecard_id"]
    assert spec["score_id"] == request["score_id"]
    assert spec["assessment_fingerprint"] == request["assessment_fingerprint"]
    assert spec["limits"] == request["limits"]
    assert len(spec["optimizer_yaml_sha256"]) == 64
    assert "optimizer_yaml" not in spec

    changed = _request()
    changed["limits"] = {**changed["limits"], "max_samples": 51}
    with pytest.raises(ValueError, match="does not match"):
        _launch(_Backend(), changed, _Publisher(), resume_state=result)


def test_ambiguous_procedure_is_adopted_from_a_later_complete_page() -> None:
    backend = _Backend()
    published = _Publisher()
    result = _launch(backend, _request(), published)
    attempted = next(row for row in published.states if row["phase"] == "procedure_create_attempted")
    exact = deepcopy(backend.procedures[0])
    unrelated = deepcopy(exact)
    unrelated["id"] = "unrelated"
    unrelated["metadata"]["optimizer_launch_spec"] = {
        **unrelated["metadata"]["optimizer_launch_spec"], "run_key": "other"
    }
    backend.procedure_pages = [
        {"items": [unrelated], "next_token": "page-2"},
        {"items": [exact], "next_token": None},
    ]
    backend.create_procedure_calls = 0

    replay = _launch(backend, _request(), _Publisher(), resume_state=attempted)

    assert replay["phase"] == "waiting"
    assert replay["procedure_id"] == result["procedure_id"]
    assert backend.create_procedure_calls == 0


@pytest.mark.parametrize("kind", ["procedure", "task"])
def test_legacy_null_metadata_before_later_exact_child_is_an_unrelated_nonmatch(kind) -> None:
    backend = _Backend()
    published = _Publisher()
    completed = _launch(backend, _request(), published)
    attempted_phase = (
        "procedure_create_attempted" if kind == "procedure" else "task_create_attempted"
    )
    attempted = next(row for row in published.states if row["phase"] == attempted_phase)

    if kind == "procedure":
        legacy = deepcopy(backend.procedures[0])
        exact = deepcopy(backend.procedures[0])
        legacy["id"] = "legacy-without-metadata"
        legacy["metadata"] = None
        backend.procedure_pages = [
            {"items": [legacy], "next_token": "procedure-exact"},
            {"items": [exact], "next_token": None},
        ]
        backend.create_procedure_calls = 0
    else:
        legacy = deepcopy(backend.tasks[0])
        exact = deepcopy(backend.tasks[0])
        legacy["id"] = "legacy-without-metadata"
        legacy["metadata"] = None
        backend.task_pages = [
            {"items": [legacy], "next_token": "task-exact"},
            {"items": [exact], "next_token": None},
        ]
        backend.create_task_calls = 0

    replay = _launch(backend, _request(), _Publisher(), resume_state=attempted)

    assert replay["phase"] == "waiting"
    assert replay["task_id"] == completed["task_id"]
    assert (
        backend.create_procedure_calls if kind == "procedure" else backend.create_task_calls
    ) == 0


@pytest.mark.parametrize("kind", ["procedure", "task"])
def test_optimizer_shaped_malformed_metadata_fails_closed_before_child_creation(kind) -> None:
    backend = _Backend()

    class StopAfterAttempt:
        def __init__(self) -> None:
            self.last = None

        def __call__(self, state) -> None:
            self.last = deepcopy(state)
            if state["phase"] == "procedure_create_attempted":
                raise RuntimeError("simulated process stop")

    if kind == "procedure":
        stop = StopAfterAttempt()
        with pytest.raises(RuntimeError, match="simulated process stop"):
            _launch(backend, _request(), stop)
        malformed = {
            **_Backend().create_procedure({
                "accountId": "account-opaque", "scorecardId": "scorecard-opaque",
                "scoreId": "score-opaque", "name": "Feedback alignment optimizer",
                "category": "optimizer", "version": "optimizer-task-dispatch-v1",
                "featured": False, "isTemplate": False, "status": "RUNNING",
                "metadata": {"optimizer_launch_spec": "corrupt"},
            }),
        }
        backend.procedure_pages = [{"items": [malformed], "next_token": None}]
        replay = _launch(backend, _request(), _Publisher(), resume_state=stop.last)
        assert backend.create_procedure_calls == 0
    else:
        published = _Publisher()
        _launch(backend, _request(), published)
        attempted = next(row for row in published.states if row["phase"] == "task_create_attempted")
        malformed = deepcopy(backend.tasks[0])
        malformed["metadata"] = {"optimizer_launch_spec": "corrupt"}
        backend.task_pages = [{"items": [malformed], "next_token": None}]
        backend.create_task_calls = 0
        replay = _launch(backend, _request(), _Publisher(), resume_state=attempted)
        assert backend.create_task_calls == 0

    assert replay["phase"] == "dispatch_outcome_unknown"
    assert replay["reason"] == f"malformed_{kind}_metadata"


def test_optimizer_shaped_malformed_metadata_on_unrelated_physical_target_is_skipped() -> None:
    backend = _Backend()
    published = _Publisher()
    completed = _launch(backend, _request(), published)
    attempted = next(row for row in published.states if row["phase"] == "procedure_create_attempted")
    unrelated = deepcopy(backend.procedures[0])
    unrelated["id"] = "other-score"
    unrelated["scoreId"] = "other-score"
    unrelated["metadata"] = {"optimizer_launch_spec": "corrupt"}
    backend.procedure_pages = [
        {"items": [unrelated], "next_token": "exact"},
        {"items": [deepcopy(backend.procedures[0])], "next_token": None},
    ]
    backend.create_procedure_calls = 0

    replay = _launch(backend, _request(), _Publisher(), resume_state=attempted)

    assert replay["phase"] == "waiting"
    assert replay["procedure_id"] == completed["procedure_id"]
    assert backend.create_procedure_calls == 0


def test_ambiguous_page_exception_is_unknown() -> None:
    class FailingPages:
        def __iter__(self):
            yield {"items": [], "next_token": "page-2"}
            raise RuntimeError("page failed")

    backend = _Backend()
    stop = _FailingPublisher("procedure_record_observed")
    with pytest.raises(RuntimeError):
        _launch(backend, _request(), stop)
    backend.procedure_pages = FailingPages()
    result = _launch(backend, _request(), _Publisher(), resume_state=stop.last_successful)

    assert result["phase"] == "dispatch_outcome_unknown"
    assert result["reason"] == "procedure_scan_page_failed"


def test_large_yaml_is_attachment_only_and_pointer_mismatch_blocks_task_creation() -> None:
    class BadPointerBackend(_Backend):
        def upload_and_verify_procedure_yaml(self, procedure, optimizer_yaml, metadata):
            result = super().upload_and_verify_procedure_yaml(
                procedure, optimizer_yaml, metadata,
            )
            result["metadata"]["code_artifact"]["sha256"] = "wrong"
            self.procedures[0]["metadata"]["code_artifact"]["sha256"] = "wrong"
            return result

    request = _request()
    request["optimizer_yaml"] = "name: optimizer\n" + ("x" * 360_000)
    backend = BadPointerBackend()

    result = _launch(backend, request, _Publisher())

    assert backend.uploaded_yaml.encode("utf-8") == request["optimizer_yaml"].encode("utf-8")
    assert "code" not in backend.procedures[0]
    assert result["phase"] == "dispatch_outcome_unknown"
    assert result["reason"] == "procedure_attachment_verification_failed"
    assert backend.create_task_calls == 0


@pytest.mark.parametrize(
    ("dispatch_status", "celery_id", "expected_phase", "expected_reason"),
    [
        ("PENDING", None, "waiting", None),
        ("DISPATCHING", None, "dispatch_outcome_unknown", "dispatching_without_celery_id"),
        ("DISPATCHING", "celery-1", "running", None),
        ("DISPATCHED", "celery-1", "running", None),
    ],
)
def test_replay_observes_dispatched_states_without_a_second_release(
    dispatch_status, celery_id, expected_phase, expected_reason,
) -> None:
    backend = _Backend()
    result = _launch(backend, _request(), _Publisher())
    backend.tasks[0]["dispatchStatus"] = dispatch_status
    if celery_id:
        backend.tasks[0]["celeryTaskId"] = celery_id
    else:
        backend.tasks[0].pop("celeryTaskId", None)
    backend.release_calls = 0

    replay = _launch(backend, _request(), _Publisher(), resume_state=result)

    assert replay["phase"] == expected_phase
    assert replay.get("reason") == expected_reason
    assert backend.release_calls == 0


def test_lost_provision_publication_reuses_verified_procedure_attachment() -> None:
    backend = _Backend()
    publisher = _FailingPublisher("procedure_provisioned")

    with pytest.raises(RuntimeError, match="publication failed"):
        _launch(backend, _request(), publisher)
    uploads_before_replay = backend.upload_calls
    backend.read_artifact_calls = 0

    result = _launch(
        backend,
        _request(),
        _Publisher(),
        resume_state=publisher.last_successful,
    )

    assert result["phase"] == "waiting"
    assert backend.upload_calls == uploads_before_replay
    assert backend.read_artifact_calls == 1
    assert backend.create_task_calls == 1


@pytest.mark.parametrize("corruption", ["key", "bytes"])
def test_lost_provision_publication_rejects_unbound_or_corrupt_attachment(corruption) -> None:
    backend = _Backend()
    publisher = _FailingPublisher("procedure_provisioned")

    with pytest.raises(RuntimeError, match="publication failed"):
        _launch(backend, _request(), publisher)
    pointer = backend.procedures[0]["metadata"]["code_artifact"]
    if corruption == "key":
        pointer["key"] = "procedures/other-procedure/code.tac"
    else:
        backend.artifacts[pointer["key"]] = b"not the immutable optimizer yaml"

    result = _launch(
        backend,
        _request(),
        _Publisher(),
        resume_state=publisher.last_successful,
    )

    assert result["phase"] == "dispatch_outcome_unknown"
    assert result["reason"] == "procedure_attachment_verification_failed"
    assert backend.create_task_calls == 0


@pytest.mark.parametrize("field", ["accountId", "scorecardId", "scoreId", "category", "version"])
def test_procedure_adoption_rejects_copied_launch_metadata_with_wrong_physical_identity(field) -> None:
    backend = _Backend()
    stop = _FailingPublisher("procedure_record_observed")
    with pytest.raises(RuntimeError, match="publication failed"):
        _launch(backend, _request(), stop)
    copied = deepcopy(backend.procedures[0])
    copied["id"] = "copied-procedure"
    copied[field] = "wrong-physical-value"
    backend.procedures = [copied]
    backend.create_procedure_calls = 0

    result = _launch(backend, _request(), _Publisher(), resume_state=stop.last_successful)

    assert result["phase"] == "dispatch_outcome_unknown"
    assert result["reason"] == "procedure_identity_mismatch"
    assert backend.create_procedure_calls == 0


@pytest.mark.parametrize("field", [
    "accountId", "scorecardId", "scoreId", "type", "status", "target", "command",
])
def test_task_adoption_rejects_copied_launch_metadata_with_wrong_physical_identity(field) -> None:
    backend = _Backend()
    published = _Publisher()
    _launch(backend, _request(), published)
    attempted = next(row for row in published.states if row["phase"] == "task_create_attempted")
    copied = deepcopy(backend.tasks[0])
    copied["id"] = "copied-task"
    copied[field] = "wrong-physical-value"
    backend.tasks = [copied]
    backend.create_task_calls = 0

    result = _launch(backend, _request(), _Publisher(), resume_state=attempted)

    assert result["phase"] == "dispatch_outcome_unknown"
    assert result["reason"] == "task_identity_mismatch"
    assert backend.create_task_calls == 0


def test_task_adoption_requires_metadata_procedure_id() -> None:
    backend = _Backend()
    published = _Publisher()
    _launch(backend, _request(), published)
    attempted = next(row for row in published.states if row["phase"] == "task_create_attempted")
    copied = deepcopy(backend.tasks[0])
    copied["metadata"]["procedure_id"] = "other-procedure"
    backend.tasks = [copied]
    backend.create_task_calls = 0

    result = _launch(backend, _request(), _Publisher(), resume_state=attempted)

    assert result["phase"] == "dispatch_outcome_unknown"
    assert result["reason"] == "task_launch_spec_mismatch"
    assert backend.create_task_calls == 0


@pytest.mark.parametrize("corrupt", ["scorecard", "status", "procedure_id"])
def test_release_rechecks_full_task_identity_immediately_before_mutation(corrupt) -> None:
    backend = _Backend()
    published = _Publisher()
    _launch(backend, _request(), published)
    release_attempt = next(row for row in published.states if row["phase"] == "release_attempted")
    backend.tasks[0]["dispatchStatus"] = "HELD"
    if corrupt == "scorecard":
        backend.tasks[0]["scorecardId"] = "other-scorecard"
    elif corrupt == "status":
        backend.tasks[0]["status"] = "FAILED"
    else:
        backend.tasks[0]["metadata"]["procedure_id"] = "other-procedure"
    backend.release_calls = 0

    result = _launch(backend, _request(), _Publisher(), resume_state=release_attempt)

    assert result["phase"] == "dispatch_outcome_unknown"
    assert backend.release_calls == 0


def test_lost_task_held_publication_reads_complete_stages_without_second_mutation() -> None:
    backend = _Backend()
    publisher = _FailingPublisher("task_held")
    with pytest.raises(RuntimeError, match="publication failed"):
        _launch(backend, _request(), publisher)
    reconciliations_before_replay = len(backend.reconciled)

    result = _launch(
        backend,
        _request(),
        _Publisher(),
        resume_state=publisher.last_successful,
    )

    assert result["phase"] == "waiting"
    assert len(backend.reconciled) == reconciliations_before_replay
    assert len(backend.task_stages[result["task_id"]]) == 2


def test_replay_reconciles_missing_stages_once_and_reads_back_complete_set() -> None:
    backend = _Backend()
    published = _Publisher()
    completed = _launch(backend, _request(), published)
    held_record = next(row for row in published.states if row["phase"] == "task_record_observed")
    backend.task_stages[completed["task_id"]].pop()
    backend.tasks[0]["dispatchStatus"] = "HELD"
    reconciliations_before_replay = len(backend.reconciled)

    result = _launch(backend, _request(), _Publisher(), resume_state=held_record)

    assert result["phase"] == "waiting"
    assert len(backend.reconciled) == reconciliations_before_replay + 1
    assert len(backend.task_stages[completed["task_id"]]) == 2
    assert len({(row["name"], row["order"]) for row in backend.task_stages[completed["task_id"]]}) == 2


def test_replay_rejects_ambiguous_existing_task_stages_without_reconciliation() -> None:
    backend = _Backend()
    published = _Publisher()
    completed = _launch(backend, _request(), published)
    held_record = next(row for row in published.states if row["phase"] == "task_record_observed")
    duplicate = deepcopy(backend.task_stages[completed["task_id"]][0])
    duplicate["id"] = "duplicate-stage"
    backend.task_stages[completed["task_id"]].append(duplicate)
    backend.tasks[0]["dispatchStatus"] = "HELD"
    reconciliations_before_replay = len(backend.reconciled)

    result = _launch(backend, _request(), _Publisher(), resume_state=held_record)

    assert result["phase"] == "dispatch_outcome_unknown"
    assert result["reason"] == "ambiguous_task_stages"
    assert len(backend.reconciled) == reconciliations_before_replay


@pytest.mark.parametrize("pages, reason", [
    ([
        {"items": [], "next_token": "page-2"},
        {"items": [], "next_token": "page-2"},
    ], "task_scan_token_cycle"),
    ([{"items": [], "next_token": "page-2"}], "task_scan_incomplete"),
])
def test_task_adoption_page_coverage_failure_is_unknown_and_never_recreates(pages, reason) -> None:
    backend = _Backend()
    publisher = _FailingPublisher("task_record_observed")
    with pytest.raises(RuntimeError, match="publication failed"):
        _launch(backend, _request(), publisher)
    backend.task_pages = pages
    backend.create_task_calls = 0

    result = _launch(
        backend,
        _request(),
        _Publisher(),
        resume_state=publisher.last_successful,
    )

    assert result["phase"] == "dispatch_outcome_unknown"
    assert result["reason"] == reason
    assert backend.create_task_calls == 0


def test_task_adoption_finds_exact_record_on_a_later_complete_page() -> None:
    backend = _Backend()
    published = _Publisher()
    completed = _launch(backend, _request(), published)
    attempted = next(row for row in published.states if row["phase"] == "task_create_attempted")
    unrelated = deepcopy(backend.tasks[0])
    unrelated["id"] = "unrelated-task"
    unrelated["metadata"]["optimizer_launch_spec"] = {
        **unrelated["metadata"]["optimizer_launch_spec"], "run_key": "other-run",
    }
    backend.task_pages = [
        {"items": [unrelated], "next_token": "page-2"},
        {"items": [deepcopy(backend.tasks[0])], "next_token": None},
    ]
    backend.create_task_calls = 0

    replay = _launch(backend, _request(), _Publisher(), resume_state=attempted)

    assert replay["phase"] == "waiting"
    assert replay["task_id"] == completed["task_id"]
    assert backend.create_task_calls == 0


def test_task_adoption_page_exception_is_unknown_and_never_recreates() -> None:
    class FailingPages:
        def __iter__(self):
            yield {"items": [], "next_token": "page-2"}
            raise RuntimeError("page failed")

    backend = _Backend()
    publisher = _FailingPublisher("task_record_observed")
    with pytest.raises(RuntimeError, match="publication failed"):
        _launch(backend, _request(), publisher)
    backend.task_pages = FailingPages()
    backend.create_task_calls = 0

    result = _launch(
        backend,
        _request(),
        _Publisher(),
        resume_state=publisher.last_successful,
    )

    assert result["phase"] == "dispatch_outcome_unknown"
    assert result["reason"] == "task_scan_page_failed"
    assert backend.create_task_calls == 0


def test_held_task_stage_page_failure_is_unknown_without_reconciliation() -> None:
    class FailingPages:
        def __iter__(self):
            yield {"items": [], "next_token": "page-2"}
            raise RuntimeError("page failed")

    backend = _Backend()
    published = _Publisher()
    completed = _launch(backend, _request(), published)
    held_record = next(row for row in published.states if row["phase"] == "task_record_observed")
    backend.tasks[0]["dispatchStatus"] = "HELD"
    backend.task_stage_pages = FailingPages()
    reconciliations_before_replay = len(backend.reconciled)

    result = _launch(backend, _request(), _Publisher(), resume_state=held_record)

    assert result["phase"] == "dispatch_outcome_unknown"
    assert result["reason"] == "task_stage_scan_page_failed"
    assert len(backend.reconciled) == reconciliations_before_replay

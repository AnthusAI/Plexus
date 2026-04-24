import json
from types import SimpleNamespace


def test_build_continuation_context_recovers_baseline_params_and_state_ids(monkeypatch):
    from plexus.cli.procedure import continuation_service as cs

    monkeypatch.setattr(
        cs,
        "_load_procedure",
        lambda _client, _procedure_id: {
            "id": "proc-123",
            "code": "name: test",
            "accountId": "acct-123",
            "scorecardId": "scorecard-id",
            "scoreId": "score-id",
        },
    )

    monkeypatch.setattr(
        "plexus.cli.shared.experiment_runner._extract_run_parameters_from_procedure_yaml",
        lambda _code: {"days": 90, "max_samples": 20, "dry_run": False},
    )
    monkeypatch.setattr(
        "plexus.cli.shared.experiment_runner._find_existing_task_for_procedure",
        lambda _procedure_id, _account_id, _client: "task-123",
    )

    class FakeTask:
        metadata = json.dumps(
            {
                "run_parameters": {
                    "optimization_objective": "alignment",
                    "context_window": 180000,
                }
            }
        )

    monkeypatch.setattr(
        "plexus.dashboard.api.models.task.Task.get_by_id",
        lambda _task_id, _client: FakeTask(),
    )

    class FakeStorage:
        values = {
            "recent_baseline_id": "eval-123",
            "scorecard_id": "scorecard-id",
            "score_id": "score-id",
            "scorecard_name": "Scorecard Name",
            "score_name": "Score Name",
        }

        def __init__(self, _client, _procedure_id):
            pass

        def state_get(self, _procedure_id, key):
            return self.values.get(key)

    monkeypatch.setattr(
        "plexus.cli.procedure.tactus_adapters.storage.PlexusStorageAdapter",
        FakeStorage,
    )

    class FakeClient:
        def execute(self, _query, variables):
            assert variables == {"id": "eval-123"}
            return {
                "getEvaluation": {
                    "id": "eval-123",
                    "parameters": json.dumps(
                        {
                            "days": 180,
                            "requested_max_items": 100,
                            "sampling_mode": "newest",
                        }
                    ),
                }
            }

    context = cs.build_continuation_context(
        FakeClient(),
        "proc-123",
        max_iterations=10,
        hint="focus on contradictions",
    )

    assert context["scorecard"] == "scorecard-id"
    assert context["score"] == "score-id"
    assert context["days"] == 180
    assert context["max_samples"] == 100
    assert context["sampling_mode"] == "newest"
    assert context["optimization_objective"] == "alignment"
    assert context["context_window"] == 180000
    assert context["max_iterations"] == 10
    assert context["hint"] == "focus on contradictions"


def test_build_continuation_context_uses_names_when_ids_missing(monkeypatch):
    from plexus.cli.procedure import continuation_service as cs

    monkeypatch.setattr(
        cs,
        "_load_procedure",
        lambda _client, _procedure_id: {
            "id": "proc-123",
            "code": "name: test",
            "accountId": "acct-123",
            "scorecardId": None,
            "scoreId": None,
        },
    )
    monkeypatch.setattr(
        "plexus.cli.shared.experiment_runner._extract_run_parameters_from_procedure_yaml",
        lambda _code: {},
    )
    monkeypatch.setattr(
        "plexus.cli.shared.experiment_runner._find_existing_task_for_procedure",
        lambda _procedure_id, _account_id, _client: None,
    )

    class FakeStorage:
        values = {
            "recent_baseline_id": None,
            "scorecard_name": "Scorecard Name",
            "score_name": "Score Name",
        }

        def __init__(self, _client, _procedure_id):
            pass

        def state_get(self, _procedure_id, key):
            return self.values.get(key)

    monkeypatch.setattr(
        "plexus.cli.procedure.tactus_adapters.storage.PlexusStorageAdapter",
        FakeStorage,
    )

    context = cs.build_continuation_context(SimpleNamespace(), "proc-123", max_iterations=7)

    assert context["scorecard"] == "Scorecard Name"
    assert context["score"] == "Score Name"
    assert context["max_iterations"] == 7

from types import SimpleNamespace

from click.testing import CliRunner

from docker.demo.harness import extract_last_json
from plexus.cli.procedure import procedures


class LuaTableLike:
    def __init__(self, values):
        self._values = values

    def items(self):
        return self._values.items()

    def keys(self):
        return self._values.keys()

    def values(self):
        return self._values.values()


def test_lua_to_python_converts_contiguous_one_based_tables_to_lists():
    result = procedures._lua_to_python({
        1: {"iteration": 1},
        2: {"iteration": 2},
    })

    assert result == [{"iteration": 1}, {"iteration": 2}]


def test_lua_to_python_converts_nested_iterations_to_list():
    result = procedures._lua_to_python({
        "result": {
            "iterations": LuaTableLike({
                1: {"iteration": 1},
                2: {"iteration": 2},
            })
        }
    })

    assert result["result"]["iterations"] == [{"iteration": 1}, {"iteration": 2}]


def test_lua_to_python_preserves_non_contiguous_numeric_key_dicts():
    result = procedures._lua_to_python({
        1: "first",
        3: "third",
    })

    assert result == {1: "first", 3: "third"}


def test_lua_to_python_preserves_string_key_dicts():
    result = procedures._lua_to_python({
        "1": "first",
        "2": "second",
    })

    assert result == {"1": "first", "2": "second"}


def test_optimize_table_summary_handles_lua_style_iteration_result(monkeypatch):
    class FakeProcedureService:
        def __init__(self, client):
            self.client = client

        def create_procedure(self, **kwargs):
            return SimpleNamespace(success=True, procedure=SimpleNamespace(id="proc-123"))

    async def fake_run_procedure_with_task_tracking(**kwargs):
        return {
            "success": True,
            "result": {
                "success": True,
                "status": "completed",
                "improvement": 0.25,
                "iterations": LuaTableLike({
                    1: {
                        "iteration": 1,
                        "hypothesis": "Tighten income prompt",
                        "metrics": {"alignment": 0.50},
                        "deltas": {"alignment": 0.10},
                    },
                    2: {
                        "iteration": 2,
                        "hypothesis": "Clarify threshold language",
                        "metrics": {"alignment": 0.75},
                        "deltas": {"alignment": 0.15},
                    },
                }),
            },
        }

    monkeypatch.setenv("PLEXUS_ACCOUNT_KEY", "acct")
    monkeypatch.setattr(procedures, "create_client", lambda: object())
    monkeypatch.setattr(procedures, "ProcedureService", FakeProcedureService)
    monkeypatch.setattr(
        "plexus.cli.report.utils.resolve_account_id_for_command",
        lambda client, account: "account-id",
    )
    monkeypatch.setattr(
        "plexus.cli.shared.experiment_runner.run_procedure_with_task_tracking",
        fake_run_procedure_with_task_tracking,
    )

    result = CliRunner().invoke(
        procedures.procedure,
        [
            "optimize",
            "--scorecard",
            "scorecard",
            "--score",
            "score",
        ],
    )

    assert result.exit_code == 0, result.output
    assert "Optimization complete" in result.output
    assert "Total Iterations" in result.output
    assert "2" in result.output
    assert "Tighten income prompt" in result.output
    assert "Clarify threshold language" in result.output


def test_optimize_passes_configured_evaluation_stall_timeout_to_procedure(monkeypatch):
    captured = {}

    class FakeProcedureService:
        def __init__(self, client):
            self.client = client

        def create_procedure(self, **kwargs):
            return SimpleNamespace(success=True, procedure=SimpleNamespace(id="proc-123"))

    async def fake_run_procedure_with_task_tracking(**kwargs):
        captured.update(kwargs)
        return {"success": True, "result": {"success": True, "status": "completed", "iterations": []}}

    monkeypatch.setenv("PLEXUS_ACCOUNT_KEY", "acct")
    monkeypatch.setattr(procedures, "create_client", lambda: object())
    monkeypatch.setattr(procedures, "ProcedureService", FakeProcedureService)
    monkeypatch.setattr(
        "plexus.cli.report.utils.resolve_account_id_for_command",
        lambda client, account: "account-id",
    )
    monkeypatch.setattr(
        "plexus.cli.shared.experiment_runner.run_procedure_with_task_tracking",
        fake_run_procedure_with_task_tracking,
    )

    result = CliRunner().invoke(
        procedures.procedure,
        [
            "optimize",
            "--scorecard", "scorecard",
            "--score", "score",
            "--evaluation-stall-timeout-minutes", "7",
        ],
    )

    assert result.exit_code == 0, result.output
    assert captured["context"]["evaluation_stall_timeout_minutes"] == 7
    assert "evaluation_timeout_minutes" not in captured["context"]


def test_optimize_resume_recent_eval_reuses_frozen_feedback_window(monkeypatch):
    captured = {}

    class FakeProcedureService:
        def __init__(self, client):
            self.client = client

        def create_procedure(self, **kwargs):
            return SimpleNamespace(success=True, procedure=SimpleNamespace(id="proc-123"))

    async def fake_run_procedure_with_task_tracking(**kwargs):
        captured.update(kwargs)
        return {"success": True, "result": {"success": True, "status": "completed", "iterations": []}}

    resumed_evaluation = SimpleNamespace(
        parameters={
            "feedback_start_at": "2026-06-24T17:10:25Z",
            "feedback_end_at": "2026-07-24T17:10:25Z",
            "days": 30,
            "requested_max_items": 75,
        }
    )

    monkeypatch.setenv("PLEXUS_ACCOUNT_KEY", "acct")
    monkeypatch.setattr(procedures, "create_client", lambda: object())
    monkeypatch.setattr(procedures, "ProcedureService", FakeProcedureService)
    monkeypatch.setattr(
        "plexus.dashboard.api.models.evaluation.Evaluation.get_by_id",
        lambda evaluation_id, client: resumed_evaluation,
    )
    monkeypatch.setattr(
        "plexus.cli.report.utils.resolve_account_id_for_command",
        lambda client, account: "account-id",
    )
    monkeypatch.setattr(
        "plexus.cli.shared.experiment_runner.run_procedure_with_task_tracking",
        fake_run_procedure_with_task_tracking,
    )

    result = CliRunner().invoke(
        procedures.procedure,
        [
            "optimize",
            "--scorecard", "scorecard",
            "--score", "score",
            "--days", "7",
            "--max-samples", "9",
            "--resume-recent-eval", "recent-eval-123",
        ],
    )

    assert result.exit_code == 0, result.output
    assert captured["context"]["feedback_window_start_at"] == "2026-06-24T17:10:25Z"
    assert captured["context"]["feedback_window_end_at"] == "2026-07-24T17:10:25Z"
    assert captured["context"]["days"] == 30
    assert captured["context"]["max_samples"] == 75


def test_optimize_resume_recent_eval_fails_closed_without_window_provenance(monkeypatch):
    monkeypatch.setenv("PLEXUS_ACCOUNT_KEY", "acct")
    monkeypatch.setattr(procedures, "create_client", lambda: object())
    monkeypatch.setattr(
        "plexus.dashboard.api.models.evaluation.Evaluation.get_by_id",
        lambda evaluation_id, client: SimpleNamespace(parameters={"days": 30}),
    )

    result = CliRunner().invoke(
        procedures.procedure,
        [
            "optimize",
            "--scorecard", "scorecard",
            "--score", "score",
            "--resume-recent-eval", "recent-eval-without-provenance",
        ],
    )

    assert result.exit_code != 0
    assert "missing frozen-window provenance" in result.output


def test_optimize_passes_candidate_count_and_parent_cost_budget(monkeypatch):
    captured = {}

    class FakeProcedureService:
        def __init__(self, client):
            self.client = client

        def create_procedure(self, **kwargs):
            return SimpleNamespace(success=True, procedure=SimpleNamespace(id="proc-123"))

    async def fake_run_procedure_with_task_tracking(**kwargs):
        captured.update(kwargs)
        return {"success": True, "result": {"success": True, "status": "completed", "iterations": []}}

    monkeypatch.setenv("PLEXUS_ACCOUNT_KEY", "acct")
    monkeypatch.setattr(procedures, "create_client", lambda: object())
    monkeypatch.setattr(procedures, "ProcedureService", FakeProcedureService)
    monkeypatch.setattr(
        "plexus.cli.report.utils.resolve_account_id_for_command",
        lambda client, account: "account-id",
    )
    monkeypatch.setattr(
        "plexus.cli.shared.experiment_runner.run_procedure_with_task_tracking",
        fake_run_procedure_with_task_tracking,
    )

    result = CliRunner().invoke(
        procedures.procedure,
        [
            "optimize",
            "--scorecard", "scorecard",
            "--score", "score",
            "--num-candidates", "2",
            "--max-cost-usd", "7.50",
        ],
    )

    assert result.exit_code == 0, result.output
    assert captured["context"]["num_candidates"] == 2
    assert captured["context"]["max_cost_usd"] == 7.5
    assert captured["context"]["_plexus_child_budget"] == {
        "usd": 7.5,
        "wallclock_seconds": 14400,
        "tool_calls": 5000,
        "depth": 2,
    }


def test_optimize_creates_task_stages_matching_optimizer_progress(monkeypatch):
    captured = {}

    class FakeProcedureService:
        def __init__(self, client):
            self.client = client

        def create_procedure(self, **kwargs):
            captured.update(kwargs)
            return SimpleNamespace(success=True, procedure=SimpleNamespace(id="proc-123"))

    async def fake_run_procedure_with_task_tracking(**kwargs):
        return {"success": True, "result": {"success": True, "status": "completed", "iterations": []}}

    monkeypatch.setenv("PLEXUS_ACCOUNT_KEY", "acct")
    monkeypatch.setattr(procedures, "create_client", lambda: object())
    monkeypatch.setattr(procedures, "ProcedureService", FakeProcedureService)
    monkeypatch.setattr(
        "plexus.cli.report.utils.resolve_account_id_for_command",
        lambda client, account: "account-id",
    )
    monkeypatch.setattr(
        "plexus.cli.shared.experiment_runner.run_procedure_with_task_tracking",
        fake_run_procedure_with_task_tracking,
    )

    result = CliRunner().invoke(
        procedures.procedure,
        ["optimize", "--scorecard", "scorecard", "--score", "score"],
    )

    assert result.exit_code == 0, result.output
    assert list(captured["stage_configs"]) == [
        "Setup", "Baseline", "Exploration", "Selection", "Finalize",
    ]


def test_optimize_json_preserves_persisted_total_cost_ledger(monkeypatch):
    class FakeProcedureService:
        def __init__(self, client):
            self.client = client

        def create_procedure(self, **kwargs):
            return SimpleNamespace(success=True, procedure=SimpleNamespace(id="proc-123"))

    async def fake_run_procedure_with_task_tracking(**kwargs):
        return {
            "success": True,
            "result": {
                "success": True,
                "status": "completed",
                "iterations": [],
                "lab_report": "Long machine-readable optimizer report. " * 40,
                "costs": {
                    "totals": {
                        "overall": {
                            "incurred": 0.1845874,
                        }
                    }
                },
            },
        }

    monkeypatch.setenv("PLEXUS_ACCOUNT_KEY", "acct")
    monkeypatch.setattr(procedures, "create_client", lambda: object())
    monkeypatch.setattr(procedures, "ProcedureService", FakeProcedureService)
    monkeypatch.setattr(
        "plexus.cli.report.utils.resolve_account_id_for_command",
        lambda client, account: "account-id",
    )
    monkeypatch.setattr(
        "plexus.cli.shared.experiment_runner.run_procedure_with_task_tracking",
        fake_run_procedure_with_task_tracking,
    )

    result = CliRunner().invoke(
        procedures.procedure,
        [
            "optimize",
            "--scorecard", "scorecard",
            "--score", "score",
            "--output", "json",
        ],
    )

    assert result.exit_code == 0, result.output
    assert '"costs"' in result.output
    assert '"totals"' in result.output
    assert '"overall"' in result.output
    assert '"incurred": 0.1845874' in result.output
    payload = extract_last_json(result.output)
    assert payload["result"]["costs"]["totals"]["overall"]["incurred"] == 0.1845874

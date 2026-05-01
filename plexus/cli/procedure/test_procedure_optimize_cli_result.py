from types import SimpleNamespace

from click.testing import CliRunner

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

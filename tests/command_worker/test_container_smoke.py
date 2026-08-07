"""The image build invokes this module; keep its action/runtime matrix explicit."""

from pathlib import Path
import tomllib

from plexus.command_worker import smoke


def test_container_smoke_covers_each_enabled_structured_action() -> None:
    assert [action for action, _argv in smoke._REGISTERED_ACTIONS] == [
        "evaluation.accuracy",
        "evaluation.feedback",
        "prediction.run",
        "report.run",
        "feedback.report",
        "procedure.run",
    ]


def test_command_service_runtime_declares_action_import_dependencies() -> None:
    manifest = tomllib.loads(
        (Path(__file__).parents[2] / "pyproject.toml").read_text(encoding="utf-8")
    )
    extra = manifest["tool"]["poetry"]["extras"]["command-service-runtime"]
    assert {
        "biblicus",
        "sentence-transformers",
        "langchain-anthropic",
        "contractions",
        "graphviz",
        "pyairtable",
    } <= set(extra)


def test_container_smoke_exercises_root_cli_and_executor_handoff() -> None:
    smoke.main()

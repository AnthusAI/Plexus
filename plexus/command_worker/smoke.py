"""Build-time parser and import smoke for every enabled command-service action."""

from __future__ import annotations

from datetime import datetime, timezone

from click.testing import CliRunner

from plexus.cli.shared.CommandLineInterface import cli

from .executors.plexus_cli import PlexusCliExecutor
from .models import CommandEnvelope


class _SmokeContext:
    def raise_if_cancellation_requested(self) -> None:
        return None

    def report_progress(self, *_args, **_kwargs) -> None:
        return None


_REGISTERED_ACTIONS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("evaluation.accuracy", ("evaluate", "accuracy", "--help")),
    ("evaluation.feedback", ("evaluate", "feedback", "--help")),
    ("prediction.run", ("predict", "--help")),
    ("report.run", ("report", "run", "--help")),
    ("feedback.report", ("feedback", "report", "recent", "--help")),
    ("procedure.run", ("procedure", "run", "--help")),
)


def _invoke_registered_action(argv: tuple[str, ...]) -> None:
    """Exercise the installed root Click group, not an isolated leaf command."""
    result = CliRunner().invoke(cli, list(argv))
    if result.exit_code != 0 or "--help" not in result.output:
        raise RuntimeError(
            f"{argv[0]} command parser smoke failed (exit {result.exit_code}): {result.output}"
        )


def _smoke_registered_action_parsers() -> None:
    for _action, argv in _REGISTERED_ACTIONS:
        _invoke_registered_action(argv)


def main() -> None:
    """Validate installed command imports and one executor-to-Click handoff."""

    _smoke_registered_action_parsers()

    envelope = CommandEnvelope(
        schema_version=2,
        command_id="container-smoke",
        tenant_id="container-smoke-account",
        target="procedure/run/container-smoke",
        idempotency_key="container-smoke",
        created_at=datetime(2026, 8, 6, tzinfo=timezone.utc),
        payload={"argv": ["procedure", "run", "--help"]},
    )
    result = PlexusCliExecutor(
        invoke_cli=lambda: _invoke_registered_action(("procedure", "run", "--help"))
    ).execute(
        envelope, _SmokeContext()
    )
    if result["argv"][:2] != ["procedure", "run"]:
        raise RuntimeError("command-worker executor smoke did not preserve argv")


if __name__ == "__main__":  # pragma: no cover - exercised by the image build.
    main()

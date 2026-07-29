"""Small top-level dispatcher for commands that must start without scoring extras."""

from __future__ import annotations

import sys
from typing import Sequence


_LIGHTWEIGHT_COMMANDS = {"login", "logout", "whoami"}


def _command_name(arguments: Sequence[str]) -> str | None:
    return arguments[0] if arguments else None


def main() -> None:
    """Dispatch application-auth commands before importing the legacy CLI graph."""
    command_name = _command_name(sys.argv[1:])
    if command_name in _LIGHTWEIGHT_COMMANDS:
        from plexus.cli.auth.commands import login, logout, whoami

        commands = {"login": login, "logout": logout, "whoami": whoami}
        commands[command_name].main(
            args=sys.argv[2:],
            prog_name=f"{sys.argv[0]} {command_name}",
            standalone_mode=True,
        )
        return

    from plexus.cli.shared.CommandLineInterface import main as legacy_main

    legacy_main()

"""
Terminal HITL adapter for CLI-based procedure execution.

Handles Human.approve() and Human.input() by prompting the user
in the terminal instead of suspending and waiting for a dashboard response.
"""

import logging
from datetime import datetime, timezone
from typing import Any

from tactus.protocols.models import HITLRequest, HITLResponse

logger = logging.getLogger(__name__)


class TerminalHITLAdapter:
    """
    Tactus HITLHandler that resolves HITL requests via terminal prompts.

    Used when running procedures from the CLI so that Human.approve() and
    Human.input() calls block at the terminal rather than suspending the
    procedure and waiting for a dashboard response.
    """

    def __init__(self, auto_approve: bool = False):
        """
        Args:
            auto_approve: If True, automatically approve all requests without prompting.
        """
        self.auto_approve = auto_approve

    def request_interaction(
        self,
        procedure_id: str,
        request: HITLRequest,
        execution_context: Any = None,
    ) -> HITLResponse:
        request_type = str(request.request_type or "").lower()

        if self.auto_approve:
            logger.info("Auto-approving HITL request: %s", request.message[:100])
            return HITLResponse(
                value=True if request_type == "approval" else (request.default_value or ""),
                responded_at=datetime.now(timezone.utc),
                timed_out=False,
            )

        if request_type == "approval":
            return self._prompt_approval(request)
        elif request_type == "input":
            return self._prompt_input(request)
        else:
            return self._prompt_approval(request)

    def _prompt_approval(self, request: HITLRequest) -> HITLResponse:
        print()
        print("=" * 70)
        print("APPROVAL REQUIRED")
        print("=" * 70)
        print(request.message)
        print()

        context = getattr(request, "metadata", {})
        if context:
            for key, val in context.items():
                if key not in ("control",):
                    print(f"  {key}: {val}")
            print()

        while True:
            answer = input("Approve? [y/n]: ").strip().lower()
            if answer in ("y", "yes"):
                approved = True
                break
            elif answer in ("n", "no"):
                approved = False
                break
            else:
                print("Please enter y or n.")

        print("=" * 70)
        return HITLResponse(
            value=approved,
            responded_at=datetime.now(timezone.utc),
            timed_out=False,
        )

    def _prompt_input(self, request: HITLRequest) -> HITLResponse:
        print()
        print("=" * 70)
        print("INPUT REQUIRED")
        print("=" * 70)
        print(request.message)

        options = getattr(request, "options", None)
        if options:
            print()
            print("Options:")
            for i, opt in enumerate(options):
                label = opt.get("label", opt) if isinstance(opt, dict) else opt
                print(f"  {i + 1}. {label}")
            print()

            while True:
                answer = input("Choose an option: ").strip().lower()
                # Match by label or number
                for opt in options:
                    label = opt.get("label", opt) if isinstance(opt, dict) else opt
                    if answer == label.lower() or answer == str(options.index(opt) + 1):
                        print("=" * 70)
                        return HITLResponse(
                            value=label,
                            responded_at=datetime.now(timezone.utc),
                            timed_out=False,
                        )
                print(f"Please choose from: {[o.get('label', o) if isinstance(o, dict) else o for o in options]}")
        else:
            default = request.default_value
            prompt = f"Enter value [{default}]: " if default is not None else "Enter value: "
            answer = input(prompt).strip()
            if not answer and default is not None:
                answer = default

        print("=" * 70)
        return HITLResponse(
            value=answer,
            responded_at=datetime.now(timezone.utc),
            timed_out=False,
        )

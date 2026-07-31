"""Durable host authority shared by all semantic diagnosis model attempts."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from typing import Any, Callable, Mapping

from plexus.optimization.semantic_budget import (
    SemanticBudgetLedger,
    SemanticBudgetSpec,
    SemanticCallPlan,
    SemanticUsage,
    canonical_json_bytes,
)


SEMANTIC_PROVIDER = "openai"
SEMANTIC_MODEL = "gpt-5-mini-2025-08-07"
SEMANTIC_PRICING_VERSION = "openai-2025-08-07-v1"


class SemanticAuthorityError(RuntimeError):
    """A semantic attempt could not be safely authorized or reconciled."""


class SemanticAuthorityPublicationError(SemanticAuthorityError):
    """Durable semantic authority state could not be loaded or committed."""


class SemanticReplayBlocked(SemanticAuthorityError):
    """Durable evidence proves that contacting the provider again is unsafe."""


class SemanticOutcomeUnknown(SemanticAuthorityError):
    """Provider contact occurred but durable settlement is incomplete."""


@dataclass(frozen=True)
class SemanticReservationDecision:
    status: str
    reservation_id: str
    replay_payload: dict[str, Any] | None = None


class SemanticBudgetCoordinator:
    """Own one Report-persisted ledger and publish every mutation in order."""

    def __init__(
        self,
        *,
        ledger: SemanticBudgetLedger,
        persist: Callable[[Mapping[str, Any]], Any],
    ) -> None:
        self._ledger = ledger
        self._persist = persist

    @classmethod
    def start_or_resume(
        cls,
        *,
        report_service: Any,
        run_key: str,
        spec: SemanticBudgetSpec,
    ) -> "SemanticBudgetCoordinator":
        load = getattr(report_service, "load_semantic_budget_ledger", None)
        persist = getattr(report_service, "persist_semantic_budget_ledger", None)
        if not callable(load) or not callable(persist):
            raise SemanticAuthorityError(
                "living Report service has no semantic budget persistence authority"
            )
        try:
            durable = load()
        except Exception as exc:
            raise SemanticAuthorityPublicationError(
                "durable semantic authority state could not be loaded"
            ) from exc
        if durable is None:
            # Revision one is the durable declaration of the empty frozen ledger.
            ledger = SemanticBudgetLedger(run_key=run_key, spec=spec, revision=1)
            try:
                persist(ledger.to_dict())
            except Exception as exc:
                raise SemanticAuthorityPublicationError(
                    "initial semantic authority state could not be committed"
                ) from exc
        else:
            ledger = SemanticBudgetLedger.from_dict(durable, expected_spec=spec)
            if ledger.run_key != run_key:
                raise SemanticAuthorityError("semantic ledger belongs to another run")
        return cls(ledger=ledger, persist=persist)

    @property
    def ledger(self) -> SemanticBudgetLedger:
        return SemanticBudgetLedger.from_dict(self._ledger.to_dict())

    def view(
        self,
        *,
        target_id: str,
        call_site: str,
        max_attempts: int,
    ) -> "SemanticAttemptAuthority":
        return SemanticAttemptAuthority(
            coordinator=self,
            target_id=target_id,
            call_site=call_site,
            max_attempts=max_attempts,
        )

    def _commit(
        self, mutation: Callable[[SemanticBudgetLedger], dict[str, Any]]
    ) -> dict[str, Any]:
        candidate = SemanticBudgetLedger.from_dict(self._ledger.to_dict())
        result = mutation(candidate)
        try:
            self._persist(candidate.to_dict())
        except Exception as exc:
            raise SemanticAuthorityPublicationError(
                "semantic authority state could not be committed"
            ) from exc
        self._ledger = candidate
        return result

    def reserve(self, plan: SemanticCallPlan) -> SemanticReservationDecision:
        try:
            existing = self._ledger.get(plan.reservation_id)
        except KeyError:
            existing = None
        if existing is not None:
            if existing.get("plan") != plan.to_dict():
                # Ask the ledger to produce its canonical conflict error.
                self._ledger.reserve(plan)
            status = str(existing.get("status") or "")
            replay = existing.get("replay_payload")
            if status == "settled" and isinstance(replay, dict):
                return SemanticReservationDecision(
                    status="replay",
                    reservation_id=plan.reservation_id,
                    replay_payload=dict(replay),
                )
            raise SemanticReplayBlocked(
                f"semantic attempt {plan.external_attempt_id or plan.reservation_id} "
                f"is durably {status or 'incomplete'} and cannot contact the provider"
            )
        try:
            entry = self._commit(lambda ledger: ledger.reserve(plan))
        except Exception as exc:
            from plexus.optimization.semantic_budget import SemanticBudgetError

            if isinstance(exc, (SemanticBudgetError, SemanticAuthorityPublicationError)):
                raise
            raise SemanticAuthorityError(
                "semantic reservation could not be authorized before provider contact"
            ) from exc
        return SemanticReservationDecision(
            status="approved", reservation_id=str(entry["reservation_id"])
        )

    def settle(
        self,
        reservation_id: str,
        usage: SemanticUsage,
        *,
        replay_payload: Mapping[str, Any],
    ) -> dict[str, Any]:
        return self._commit(
            lambda ledger: ledger.settle(
                reservation_id, usage, replay_payload=replay_payload
            )
        )

    def outcome_unknown(self, reservation_id: str, *, reason: str) -> dict[str, Any]:
        return self._commit(
            lambda ledger: ledger.mark_outcome_unknown(
                reservation_id, reason=reason[:2000] or "provider outcome unknown"
            )
        )


class SemanticAttemptAuthority:
    """Per-target/call-site view over one shared run ledger."""

    def __init__(
        self,
        *,
        coordinator: SemanticBudgetCoordinator,
        target_id: str,
        call_site: str,
        max_attempts: int,
    ) -> None:
        if not target_id or not call_site:
            raise ValueError("semantic authority target_id and call_site are required")
        if isinstance(max_attempts, bool) or not isinstance(max_attempts, int) or max_attempts <= 0:
            raise ValueError("semantic authority max_attempts must be positive")
        self.coordinator = coordinator
        self.target_id = target_id
        self.call_site = call_site
        self.max_attempts = max_attempts

    def direct_plan(
        self,
        *,
        attempt: int,
        max_input_tokens: int,
        max_output_tokens: int,
        request_payload: Mapping[str, Any],
    ) -> SemanticCallPlan:
        request_hash = sha256(canonical_json_bytes(request_payload)).hexdigest()
        return SemanticCallPlan(
            run_key=self.coordinator.ledger.run_key,
            target_id=self.target_id,
            call_site=self.call_site,
            attempt=attempt,
            max_attempts=self.max_attempts,
            provider=SEMANTIC_PROVIDER,
            model=SEMANTIC_MODEL,
            pricing_version=SEMANTIC_PRICING_VERSION,
            max_input_tokens=max_input_tokens,
            max_output_tokens=max_output_tokens,
            request_hash=request_hash,
            external_attempt_id=f"{self.call_site}:{attempt}",
        )

    def reserve_direct(self, plan: SemanticCallPlan) -> SemanticReservationDecision:
        self._validate_plan(plan)
        return self.coordinator.reserve(plan)

    def settle_direct(
        self,
        reservation_id: str,
        usage: SemanticUsage,
        *,
        output_text: str,
    ) -> dict[str, Any]:
        return self.coordinator.settle(
            reservation_id,
            usage,
            replay_payload={
                "version": 1,
                "kind": "plexus-direct-response",
                "output_text": output_text,
            },
        )

    def unknown_direct(self, reservation_id: str, *, reason: str) -> None:
        try:
            self.coordinator.outcome_unknown(reservation_id, reason=reason)
        except Exception:
            # The last known durable state is still reserved and therefore fail-closed.
            pass

    def reserve(self, plan: Any) -> Any:
        """Implement Tactus ModelAttemptAuthority without importing it eagerly."""
        from tactus.protocols.model_attempt import ModelAttemptReservation

        semantic_plan = self._from_tactus_plan(plan)
        try:
            decision = self.coordinator.reserve(semantic_plan)
        except SemanticReplayBlocked as exc:
            return ModelAttemptReservation.rejected(str(exc))
        if decision.status == "replay":
            return ModelAttemptReservation.replay(
                decision.reservation_id,
                replay_payload=decision.replay_payload,
            )
        return ModelAttemptReservation.approved(decision.reservation_id)

    def settle(self, outcome: Any) -> None:
        from tactus.protocols.model_attempt import ModelAttemptOutcomeUnknown

        if outcome.status in {"rejected", "replayed"}:
            return
        reservation_id = str(outcome.reservation_id or "")
        if not reservation_id:
            raise ModelAttemptOutcomeUnknown("semantic settlement has no reservation id")
        if outcome.status == "outcome_unknown":
            try:
                self.coordinator.outcome_unknown(
                    reservation_id,
                    reason=str(outcome.error or "Tactus provider outcome unknown"),
                )
            finally:
                raise ModelAttemptOutcomeUnknown(
                    str(outcome.error or "Tactus provider outcome unknown")
                )
        usage = outcome.usage
        if usage is None or outcome.replay_payload is None:
            self._mark_unknown_after_contact(
                reservation_id, "Tactus succeeded without usage or replay evidence"
            )
        try:
            self.coordinator.settle(
                reservation_id,
                SemanticUsage(
                    input_tokens=usage.input_tokens,
                    output_tokens=usage.output_tokens,
                    cached_input_tokens=usage.cached_tokens or 0,
                    provider_request_id=outcome.provider_request_id,
                ),
                replay_payload=outcome.replay_payload,
            )
        except Exception as exc:
            self._mark_unknown_after_contact(reservation_id, str(exc))

    def _mark_unknown_after_contact(self, reservation_id: str, reason: str) -> None:
        from tactus.protocols.model_attempt import ModelAttemptOutcomeUnknown

        try:
            self.coordinator.outcome_unknown(reservation_id, reason=reason)
        except Exception:
            pass
        raise ModelAttemptOutcomeUnknown(reason)

    def _from_tactus_plan(self, plan: Any) -> SemanticCallPlan:
        semantic_plan = SemanticCallPlan(
            run_key=self.coordinator.ledger.run_key,
            target_id=self.target_id,
            call_site=self.call_site,
            attempt=plan.attempt_number,
            max_attempts=plan.max_attempts,
            provider=plan.provider,
            model=plan.model,
            pricing_version=SEMANTIC_PRICING_VERSION,
            max_input_tokens=plan.max_input_tokens,
            max_output_tokens=plan.max_output_tokens,
            request_hash=plan.request_hash,
            external_attempt_id=plan.attempt_id,
        )
        self._validate_plan(semantic_plan)
        return semantic_plan

    def _validate_plan(self, plan: SemanticCallPlan) -> None:
        if (
            plan.provider != SEMANTIC_PROVIDER
            or plan.model != SEMANTIC_MODEL
            or plan.pricing_version != SEMANTIC_PRICING_VERSION
        ):
            raise SemanticAuthorityError("semantic attempt requested an unauthorized model")
        if plan.max_attempts != self.max_attempts or plan.attempt > self.max_attempts:
            raise SemanticAuthorityError("semantic attempt exceeded its physical-attempt bound")


def semantic_budget_spec(max_cost_usd: str) -> SemanticBudgetSpec:
    return SemanticBudgetSpec(
        max_cost_usd=max_cost_usd,
        pricing_version=SEMANTIC_PRICING_VERSION,
    )

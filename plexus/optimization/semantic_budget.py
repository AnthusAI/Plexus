"""Exact, replay-safe authorization ledger for semantic model calls.

This module is intentionally independent from the float-oriented runtime and
optimizer budgets.  It authorizes calls from a checked-in pricing snapshot and
serializes all money as canonical decimal strings.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from hashlib import sha256
import json
import math
from pathlib import Path
from typing import Any, Mapping


SEMANTIC_BUDGET_SCHEMA_VERSION = "semantic-budget-v1"
SEMANTIC_BUDGET_POLICY_VERSION = "semantic-budget-policy-v1"
SEMANTIC_LEDGER_SCHEMA_VERSION = "semantic-budget-ledger-v1"
SEMANTIC_CALL_PLAN_SCHEMA_VERSION = "semantic-call-plan-v1"
SEMANTIC_USAGE_SCHEMA_VERSION = "semantic-usage-v1"
_PRICING_FILES = {
    "openai-2025-08-07-v1": "openai-2025-08-07-v1.json",
}
_MILLION = Decimal(1_000_000)


class SemanticBudgetError(RuntimeError):
    """Base class for semantic budget authorization failures."""


class UnknownSemanticPricing(SemanticBudgetError):
    """The requested immutable provider/model price is not authorized."""


class SemanticBudgetExceeded(SemanticBudgetError):
    """A worst-case reservation would exceed the frozen run budget."""


class SemanticBudgetConflict(SemanticBudgetError):
    """Replay supplied data that conflicts with a durable ledger entry."""


def _decimal(value: Any, *, field: str, non_negative: bool = True) -> Decimal:
    if not isinstance(value, str):
        raise TypeError(f"{field} must be a decimal string")
    if not value or value != value.strip():
        raise ValueError(f"{field} must be a nonempty canonical decimal string")
    try:
        parsed = Decimal(value)
    except InvalidOperation as exc:
        raise ValueError(f"{field} must be a decimal string") from exc
    if not parsed.is_finite():
        raise ValueError(f"{field} must be finite")
    if non_negative and parsed < 0:
        raise ValueError(f"{field} must be non-negative")
    return parsed


def decimal_string(value: Decimal) -> str:
    """Return stable non-exponent decimal JSON text without losing precision."""
    if not isinstance(value, Decimal) or not value.is_finite():
        raise TypeError("value must be a finite Decimal")
    if value == 0:
        return "0"
    rendered = format(value, "f")
    if "." in rendered:
        rendered = rendered.rstrip("0").rstrip(".")
    return rendered


def stakeholder_budget_evidence(
    ledger_value: Mapping[str, Any],
    *,
    evidence_reference: str,
) -> dict[str, Any]:
    """Return a privacy-safe, deterministic projection of a frozen ledger.

    This is intentionally an aggregate rather than a transport copy of the
    ledger.  Operators need exact Decimal reconciliation and a durable digest,
    but stakeholder artifacts must not expose target identifiers, request
    payloads, replay payloads, provider request IDs, or unknown-outcome text.
    """
    if not isinstance(evidence_reference, str) or not evidence_reference.strip():
        raise ValueError("semantic budget evidence reference is required")
    ledger = SemanticBudgetLedger.from_dict(ledger_value)
    entries = ledger.to_dict()["entries"]
    statuses = {
        "reserved": 0,
        "settled": 0,
        "outcome_unknown": 0,
        "cancelled_pre_contact": 0,
    }
    call_sites: dict[str, int] = {}
    targets: set[str] = set()
    providers: set[str] = set()
    models: set[str] = set()
    for entry in entries:
        plan = entry["plan"]
        status = str(entry["status"])
        statuses[status] += 1
        call_site = str(plan["call_site"])
        call_sites[call_site] = call_sites.get(call_site, 0) + 1
        targets.add(str(plan["target_id"]))
        providers.add(str(plan["provider"]))
        models.add(str(plan["model"]))
    if not providers and not models:
        authorized = list(load_semantic_pricing(ledger.spec.pricing_version).models.values())
        if len(authorized) == 1:
            providers.add(authorized[0].provider)
            models.add(authorized[0].model)
    summary = ledger.summary()
    return {
        "policy_version": SEMANTIC_BUDGET_POLICY_VERSION,
        "budget_spec_schema_version": ledger.spec.schema_version,
        "ledger_schema_version": SEMANTIC_LEDGER_SCHEMA_VERSION,
        "pricing_version": ledger.spec.pricing_version,
        "provider": next(iter(providers)) if len(providers) == 1 else "mixed",
        "model": next(iter(models)) if len(models) == 1 else "mixed",
        "authorized_max_usd": summary["max_cost_usd"],
        "settled_actual_usd": summary["settled_usd"],
        "held_reserved_usd": summary["held_usd"],
        "available_usd": summary["available_usd"],
        "reservation_count": summary["reservation_count"],
        "reserved_count": statuses["reserved"],
        "settled_count": summary["settled_count"],
        "unknown_count": summary["outcome_unknown_count"],
        "cancelled_count": statuses["cancelled_pre_contact"],
        "target_count": len(targets),
        "call_site_coverage": [
            {"call_site": call_site, "count": count}
            for call_site, count in sorted(call_sites.items())
        ],
        "ledger_revision": ledger.revision,
        "evidence_reference": evidence_reference.strip(),
        "evidence_digest": ledger.digest(),
    }


def canonical_json_bytes(value: Mapping[str, Any]) -> bytes:
    return json.dumps(
        dict(value),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("utf-8")


def _non_negative_int(value: Any, *, field: str, positive: bool = False) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{field} must be an integer")
    if value < (1 if positive else 0):
        qualifier = "positive" if positive else "non-negative"
        raise ValueError(f"{field} must be {qualifier}")
    return value


@dataclass(frozen=True)
class SemanticModelPrice:
    provider: str
    model: str
    input_usd_per_million: Decimal
    cached_input_usd_per_million: Decimal
    output_usd_per_million: Decimal


@dataclass(frozen=True)
class SemanticPricingSnapshot:
    pricing_version: str
    models: Mapping[str, SemanticModelPrice]

    def price_for(self, provider: str, model: str) -> SemanticModelPrice:
        key = f"{provider}:{model}"
        price = self.models.get(key)
        if price is None:
            raise UnknownSemanticPricing(
                f"no semantic pricing for exact provider/model {key!r} in "
                f"{self.pricing_version!r}"
            )
        return price


def load_semantic_pricing(pricing_version: str) -> SemanticPricingSnapshot:
    filename = _PRICING_FILES.get(pricing_version)
    if filename is None:
        raise UnknownSemanticPricing(
            f"unknown semantic pricing version: {pricing_version!r}"
        )
    path = Path(__file__).with_name("semantic_pricing") / filename
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise UnknownSemanticPricing(
            f"semantic pricing snapshot {pricing_version!r} is unavailable"
        ) from exc
    if (
        not isinstance(raw, dict)
        or raw.get("schema_version") != "semantic-pricing-v1"
        or raw.get("pricing_version") != pricing_version
        or raw.get("currency") != "USD"
        or raw.get("unit_tokens") != 1_000_000
        or not isinstance(raw.get("models"), dict)
    ):
        raise UnknownSemanticPricing(
            f"semantic pricing snapshot {pricing_version!r} is malformed"
        )
    models: dict[str, SemanticModelPrice] = {}
    for key, value in raw["models"].items():
        if not isinstance(key, str) or ":" not in key or not isinstance(value, dict):
            raise UnknownSemanticPricing("semantic pricing model entry is malformed")
        provider, model = key.split(":", 1)
        try:
            price = SemanticModelPrice(
                provider=provider,
                model=model,
                input_usd_per_million=_decimal(
                    value.get("input_usd_per_million"),
                    field="input_usd_per_million",
                ),
                cached_input_usd_per_million=_decimal(
                    value.get("cached_input_usd_per_million"),
                    field="cached_input_usd_per_million",
                ),
                output_usd_per_million=_decimal(
                    value.get("output_usd_per_million"),
                    field="output_usd_per_million",
                ),
            )
        except (TypeError, ValueError) as exc:
            raise UnknownSemanticPricing(
                f"semantic pricing model entry {key!r} is malformed"
            ) from exc
        if price.cached_input_usd_per_million > price.input_usd_per_million:
            raise UnknownSemanticPricing(
                f"cached input pricing exceeds input pricing for {key!r}"
            )
        models[key] = price
    return SemanticPricingSnapshot(pricing_version=pricing_version, models=models)


@dataclass(frozen=True)
class SemanticBudgetSpec:
    max_cost_usd: str
    pricing_version: str
    schema_version: str = SEMANTIC_BUDGET_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.schema_version != SEMANTIC_BUDGET_SCHEMA_VERSION:
            raise ValueError("unsupported semantic budget schema version")
        normalized = decimal_string(
            _decimal(self.max_cost_usd, field="max_cost_usd")
        )
        if not isinstance(self.pricing_version, str) or not self.pricing_version:
            raise ValueError("pricing_version is required")
        load_semantic_pricing(self.pricing_version)
        object.__setattr__(self, "max_cost_usd", normalized)

    @property
    def max_cost(self) -> Decimal:
        return Decimal(self.max_cost_usd)

    def to_dict(self) -> dict[str, str]:
        return {
            "schema_version": self.schema_version,
            "max_cost_usd": self.max_cost_usd,
            "pricing_version": self.pricing_version,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "SemanticBudgetSpec":
        if not isinstance(value, Mapping):
            raise TypeError("semantic budget spec must be an object")
        return cls(
            schema_version=value.get("schema_version", SEMANTIC_BUDGET_SCHEMA_VERSION),
            max_cost_usd=value.get("max_cost_usd"),
            pricing_version=value.get("pricing_version"),
        )


@dataclass(frozen=True)
class SemanticCallPlan:
    run_key: str
    target_id: str
    call_site: str
    attempt: int
    max_attempts: int
    provider: str
    model: str
    pricing_version: str
    max_input_tokens: int
    max_output_tokens: int
    request_hash: str | None = None
    external_attempt_id: str | None = None
    schema_version: str = SEMANTIC_CALL_PLAN_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.schema_version != SEMANTIC_CALL_PLAN_SCHEMA_VERSION:
            raise ValueError("unsupported semantic call plan schema version")
        for field in ("run_key", "target_id", "call_site", "provider", "model", "pricing_version"):
            value = getattr(self, field)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{field} is required")
        _non_negative_int(self.attempt, field="attempt", positive=True)
        _non_negative_int(self.max_attempts, field="max_attempts", positive=True)
        if self.attempt > self.max_attempts:
            raise ValueError("attempt cannot exceed max_attempts")
        _non_negative_int(self.max_input_tokens, field="max_input_tokens")
        _non_negative_int(
            self.max_output_tokens, field="max_output_tokens", positive=True
        )
        for field in ("request_hash", "external_attempt_id"):
            value = getattr(self, field)
            if value is not None and (not isinstance(value, str) or not value.strip()):
                raise ValueError(f"{field} must be a nonempty string")

    def identity_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "run_key": self.run_key,
            "target_id": self.target_id,
            "call_site": self.call_site,
            "attempt": self.attempt,
        }

    @property
    def reservation_id(self) -> str:
        return sha256(canonical_json_bytes(self.identity_dict())).hexdigest()

    def to_dict(self) -> dict[str, Any]:
        return {
            **self.identity_dict(),
            "max_attempts": self.max_attempts,
            "provider": self.provider,
            "model": self.model,
            "pricing_version": self.pricing_version,
            "max_input_tokens": self.max_input_tokens,
            "max_output_tokens": self.max_output_tokens,
            "request_hash": self.request_hash,
            "external_attempt_id": self.external_attempt_id,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "SemanticCallPlan":
        if not isinstance(value, Mapping):
            raise TypeError("semantic call plan must be an object")
        return cls(**dict(value))


@dataclass(frozen=True)
class SemanticUsage:
    input_tokens: int
    output_tokens: int
    cached_input_tokens: int = 0
    provider_request_id: str | None = None
    schema_version: str = SEMANTIC_USAGE_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.schema_version != SEMANTIC_USAGE_SCHEMA_VERSION:
            raise ValueError("unsupported semantic usage schema version")
        _non_negative_int(self.input_tokens, field="input_tokens")
        _non_negative_int(self.output_tokens, field="output_tokens")
        _non_negative_int(self.cached_input_tokens, field="cached_input_tokens")
        if self.cached_input_tokens > self.input_tokens:
            raise ValueError("cached_input_tokens cannot exceed input_tokens")
        if self.provider_request_id is not None and (
            not isinstance(self.provider_request_id, str)
            or not self.provider_request_id
        ):
            raise ValueError("provider_request_id must be a nonempty string")

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "input_tokens": self.input_tokens,
            "cached_input_tokens": self.cached_input_tokens,
            "output_tokens": self.output_tokens,
            "provider_request_id": self.provider_request_id,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "SemanticUsage":
        if not isinstance(value, Mapping):
            raise TypeError("semantic usage must be an object")
        return cls(**dict(value))


def _reserved_cost(plan: SemanticCallPlan, price: SemanticModelPrice) -> Decimal:
    return (
        Decimal(plan.max_input_tokens) * price.input_usd_per_million
        + Decimal(plan.max_output_tokens) * price.output_usd_per_million
    ) / _MILLION


def _actual_cost(usage: SemanticUsage, price: SemanticModelPrice) -> Decimal:
    uncached = usage.input_tokens - usage.cached_input_tokens
    return (
        Decimal(uncached) * price.input_usd_per_million
        + Decimal(usage.cached_input_tokens) * price.cached_input_usd_per_million
        + Decimal(usage.output_tokens) * price.output_usd_per_million
    ) / _MILLION


def _validated_replay_payload(
    value: Mapping[str, Any] | None,
) -> dict[str, Any] | None:
    """Validate the two versioned JSON-native replay envelopes we persist."""
    if value is None:
        return None
    if not isinstance(value, Mapping):
        raise TypeError("semantic replay payload must be an object")
    _validate_json_native(value)
    try:
        canonical = json.loads(canonical_json_bytes(value).decode("utf-8"))
    except (TypeError, ValueError) as exc:
        raise ValueError("semantic replay payload must be JSON-compatible") from exc
    if canonical.get("version") != 1:
        raise ValueError("unsupported semantic replay payload version")
    kind = canonical.get("kind")
    if kind == "prediction":
        if set(canonical) != {"version", "kind", "fields", "typed_fields"}:
            raise ValueError("Tactus replay payload has unexpected fields")
        if not isinstance(canonical.get("fields"), dict) or not isinstance(
            canonical.get("typed_fields"), dict
        ):
            raise ValueError("Tactus replay payload fields are malformed")
        if any(
            not isinstance(key, str) or value != "tool_calls"
            for key, value in canonical["typed_fields"].items()
        ):
            raise ValueError("Tactus replay typed_fields are malformed")
    elif kind == "plexus-direct-response":
        if set(canonical) != {"version", "kind", "output_text"} or not isinstance(
            canonical.get("output_text"), str
        ):
            raise ValueError("direct semantic replay payload is malformed")
    else:
        raise ValueError("unsupported semantic replay payload kind")
    return canonical


def _validate_json_native(value: Any) -> None:
    if value is None or isinstance(value, (str, bool, int)):
        return
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("semantic replay payload numbers must be finite")
        return
    if isinstance(value, Mapping):
        for key, item in value.items():
            if not isinstance(key, str):
                raise ValueError("semantic replay payload object keys must be strings")
            _validate_json_native(item)
        return
    if isinstance(value, list):
        for item in value:
            _validate_json_native(item)
        return
    raise ValueError("semantic replay payload must contain only JSON-native values")


class SemanticBudgetLedger:
    """Single-run authorization ledger with deterministic replay transitions."""

    def __init__(
        self,
        *,
        run_key: str,
        spec: SemanticBudgetSpec,
        revision: int = 0,
        entries: Mapping[str, Mapping[str, Any]] | None = None,
    ) -> None:
        if not isinstance(run_key, str) or not run_key:
            raise ValueError("run_key is required")
        if not isinstance(spec, SemanticBudgetSpec):
            raise TypeError("spec must be a SemanticBudgetSpec")
        _non_negative_int(revision, field="revision")
        self.run_key = run_key
        self.spec = spec
        self.revision = revision
        self._entries = {
            str(key): deepcopy(dict(value)) for key, value in (entries or {}).items()
        }

    def _price(self, plan: SemanticCallPlan) -> SemanticModelPrice:
        if plan.pricing_version != self.spec.pricing_version:
            raise UnknownSemanticPricing(
                "call plan pricing version differs from the frozen budget"
            )
        return load_semantic_pricing(self.spec.pricing_version).price_for(
            plan.provider, plan.model
        )

    def _used(self) -> Decimal:
        total = Decimal(0)
        for entry in self._entries.values():
            status = entry.get("status")
            if status == "settled":
                total += _decimal(
                    entry.get("actual_cost_usd"), field="actual_cost_usd"
                )
            elif status in {"reserved", "outcome_unknown"}:
                total += _decimal(entry.get("reserved_usd"), field="reserved_usd")
        return total

    def reserve(self, plan: SemanticCallPlan) -> dict[str, Any]:
        if not isinstance(plan, SemanticCallPlan):
            raise TypeError("plan must be a SemanticCallPlan")
        if plan.run_key != self.run_key:
            raise SemanticBudgetConflict("call plan belongs to another run")
        reservation_id = plan.reservation_id
        existing = self._entries.get(reservation_id)
        if existing is not None:
            if existing.get("plan") != plan.to_dict():
                raise SemanticBudgetConflict(
                    "replay attempted to change an existing semantic call plan"
                )
            return deepcopy(existing)
        price = self._price(plan)
        reserved = _reserved_cost(plan, price)
        if self._used() + reserved > self.spec.max_cost:
            raise SemanticBudgetExceeded(
                "semantic call worst-case reservation exceeds the frozen run budget"
            )
        entry = {
            "reservation_id": reservation_id,
            "plan": plan.to_dict(),
            "status": "reserved",
            "reserved_usd": decimal_string(reserved),
        }
        self._entries[reservation_id] = entry
        self.revision += 1
        return deepcopy(entry)

    def settle(
        self,
        reservation_id: str,
        usage: SemanticUsage,
        *,
        replay_payload: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        entry = self._required_entry(reservation_id)
        if not isinstance(usage, SemanticUsage):
            raise TypeError("usage must be SemanticUsage")
        usage_dict = usage.to_dict()
        replay_value = _validated_replay_payload(replay_payload)
        if entry.get("status") == "settled":
            if (
                entry.get("usage") != usage_dict
                or entry.get("replay_payload") != replay_value
            ):
                raise SemanticBudgetConflict(
                    "replay attempted to change settled semantic usage"
                )
            return deepcopy(entry)
        if entry.get("status") not in {"reserved", "outcome_unknown"}:
            raise SemanticBudgetConflict(
                "only a reserved or unknown semantic call can be settled"
            )
        plan = SemanticCallPlan.from_dict(entry["plan"])
        if usage.input_tokens > plan.max_input_tokens:
            raise ValueError("actual input usage exceeds the authorized bound")
        if usage.output_tokens > plan.max_output_tokens:
            raise ValueError("actual output usage exceeds the authorized bound")
        actual = _actual_cost(usage, self._price(plan))
        reserved = _decimal(entry["reserved_usd"], field="reserved_usd")
        if actual > reserved:
            raise ValueError("actual semantic cost exceeds the reservation")
        entry = {
            **entry,
            "status": "settled",
            "usage": usage_dict,
            "actual_cost_usd": decimal_string(actual),
            **({"replay_payload": replay_value} if replay_value is not None else {}),
        }
        entry.pop("outcome_unknown_reason", None)
        self._entries[reservation_id] = entry
        self.revision += 1
        return deepcopy(entry)

    def mark_outcome_unknown(self, reservation_id: str, *, reason: str) -> dict[str, Any]:
        entry = self._required_entry(reservation_id)
        if not isinstance(reason, str) or not reason.strip():
            raise ValueError("outcome unknown reason is required")
        if entry.get("status") == "outcome_unknown":
            if entry.get("outcome_unknown_reason") != reason:
                raise SemanticBudgetConflict(
                    "replay attempted to change the unknown-outcome reason"
                )
            return deepcopy(entry)
        if entry.get("status") != "reserved":
            raise SemanticBudgetConflict("only a reserved call can become outcome unknown")
        entry = {
            **entry,
            "status": "outcome_unknown",
            "outcome_unknown_reason": reason,
        }
        self._entries[reservation_id] = entry
        self.revision += 1
        return deepcopy(entry)

    def cancel_pre_contact(self, reservation_id: str, *, reason: str) -> dict[str, Any]:
        entry = self._required_entry(reservation_id)
        if not isinstance(reason, str) or not reason.strip():
            raise ValueError("pre-contact cancellation reason is required")
        if entry.get("status") == "cancelled_pre_contact":
            if entry.get("cancellation_reason") != reason:
                raise SemanticBudgetConflict(
                    "replay attempted to change the cancellation reason"
                )
            return deepcopy(entry)
        if entry.get("status") != "reserved":
            raise SemanticBudgetConflict("only a reserved call can be cancelled")
        entry = {
            **entry,
            "status": "cancelled_pre_contact",
            "cancellation_reason": reason,
        }
        self._entries[reservation_id] = entry
        self.revision += 1
        return deepcopy(entry)

    def _required_entry(self, reservation_id: str) -> dict[str, Any]:
        if not isinstance(reservation_id, str) or reservation_id not in self._entries:
            raise KeyError("unknown semantic reservation")
        return deepcopy(self._entries[reservation_id])

    def get(self, reservation_id: str) -> dict[str, Any]:
        return self._required_entry(reservation_id)

    def summary(self) -> dict[str, Any]:
        settled = sum(
            (
                _decimal(entry["actual_cost_usd"], field="actual_cost_usd")
                for entry in self._entries.values()
                if entry.get("status") == "settled"
            ),
            Decimal(0),
        )
        held = sum(
            (
                _decimal(entry["reserved_usd"], field="reserved_usd")
                for entry in self._entries.values()
                if entry.get("status") in {"reserved", "outcome_unknown"}
            ),
            Decimal(0),
        )
        return {
            "max_cost_usd": self.spec.max_cost_usd,
            "settled_usd": decimal_string(settled),
            "held_usd": decimal_string(held),
            "available_usd": decimal_string(self.spec.max_cost - settled - held),
            "reservation_count": len(self._entries),
            "settled_count": sum(
                entry.get("status") == "settled" for entry in self._entries.values()
            ),
            "outcome_unknown_count": sum(
                entry.get("status") == "outcome_unknown"
                for entry in self._entries.values()
            ),
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": SEMANTIC_LEDGER_SCHEMA_VERSION,
            "run_key": self.run_key,
            "budget_spec": self.spec.to_dict(),
            "revision": self.revision,
            "entries": [
                deepcopy(self._entries[key]) for key in sorted(self._entries)
            ],
            "summary": self.summary(),
        }

    def digest(self) -> str:
        return sha256(canonical_json_bytes(self.to_dict())).hexdigest()

    @classmethod
    def from_dict(
        cls,
        value: Mapping[str, Any],
        *,
        expected_spec: SemanticBudgetSpec | None = None,
    ) -> "SemanticBudgetLedger":
        if not isinstance(value, Mapping):
            raise TypeError("semantic budget ledger must be an object")
        if value.get("schema_version") != SEMANTIC_LEDGER_SCHEMA_VERSION:
            raise ValueError("unsupported semantic budget ledger schema version")
        spec = SemanticBudgetSpec.from_dict(value.get("budget_spec") or {})
        if expected_spec is not None and spec != expected_spec:
            raise SemanticBudgetConflict(
                "durable ledger budget differs from the frozen run budget"
            )
        raw_entries = value.get("entries")
        if not isinstance(raw_entries, list):
            raise TypeError("semantic budget ledger entries must be a list")
        entries: dict[str, dict[str, Any]] = {}
        for raw_entry in raw_entries:
            if not isinstance(raw_entry, Mapping):
                raise TypeError("semantic budget ledger entry must be an object")
            entry = dict(raw_entry)
            plan = SemanticCallPlan.from_dict(entry.get("plan") or {})
            reservation_id = entry.get("reservation_id")
            if reservation_id != plan.reservation_id or reservation_id in entries:
                raise SemanticBudgetConflict("semantic reservation identity is invalid")
            price = load_semantic_pricing(spec.pricing_version).price_for(
                plan.provider, plan.model
            )
            if plan.run_key != value.get("run_key") or plan.pricing_version != spec.pricing_version:
                raise SemanticBudgetConflict("semantic call plan conflicts with ledger identity")
            if entry.get("reserved_usd") != decimal_string(_reserved_cost(plan, price)):
                raise SemanticBudgetConflict("semantic reservation cost is invalid")
            status = entry.get("status")
            if status not in {
                "reserved", "settled", "outcome_unknown", "cancelled_pre_contact"
            }:
                raise SemanticBudgetConflict("semantic reservation status is invalid")
            if status == "outcome_unknown" and (
                not isinstance(entry.get("outcome_unknown_reason"), str)
                or not entry["outcome_unknown_reason"].strip()
            ):
                raise SemanticBudgetConflict("outcome_unknown_reason is required")
            if status == "cancelled_pre_contact" and (
                not isinstance(entry.get("cancellation_reason"), str)
                or not entry["cancellation_reason"].strip()
            ):
                raise SemanticBudgetConflict("cancellation_reason is required")
            if status == "settled":
                usage = SemanticUsage.from_dict(entry.get("usage") or {})
                if (
                    usage.input_tokens > plan.max_input_tokens
                    or usage.output_tokens > plan.max_output_tokens
                    or entry.get("actual_cost_usd")
                    != decimal_string(_actual_cost(usage, price))
                ):
                    raise SemanticBudgetConflict("settled semantic usage is invalid")
                if "replay_payload" in entry:
                    entry["replay_payload"] = _validated_replay_payload(
                        entry.get("replay_payload")
                    )
            entries[str(reservation_id)] = entry
        ledger = cls(
            run_key=value.get("run_key"),
            spec=spec,
            revision=value.get("revision"),
            entries=entries,
        )
        if value.get("summary") != ledger.summary():
            raise SemanticBudgetConflict("semantic budget ledger summary is invalid")
        if ledger._used() > spec.max_cost:
            raise SemanticBudgetConflict("semantic budget ledger exceeds its frozen budget")
        return ledger

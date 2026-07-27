"""Durable storage for optimization decision packets.

The decision service remains transport and storage agnostic.  This adapter is
the only optional persistence path: it delegates to the established
Task -> Report -> ReportBlock implementation, which uploads the full payload
as a ReportBlock attachment and keeps only a compact pointer envelope inline.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Optional


DECISION_PACKET_BLOCK_TYPE = "OptimizationDecisionPacket"
DECISION_PACKET_REPORT_NAME = "Optimization decision packet"


@dataclass(frozen=True)
class PersistedDecisionPacket:
    """Reference to a durable copy of a decision packet."""

    report_id: str


def persist_decision_packet(
    packet: Mapping[str, Any],
    *,
    client: Any,
    account_id: Optional[str] = None,
    persist: bool = False,
    report_name: str = DECISION_PACKET_REPORT_NAME,
) -> Optional[PersistedDecisionPacket]:
    """Optionally persist an unchanged decision packet through Report blocks.

    With ``persist=False`` this function deliberately performs no imports of
    report services and no external writes.  With ``persist=True`` every
    storage failure is allowed to propagate; callers must not reinterpret a
    failed persistence request as an ephemeral success.
    """
    if not persist:
        return None
    if not isinstance(packet, Mapping):
        raise TypeError("packet must be a mapping")

    resolved_account_id = account_id or _string_value(packet.get("account_id"))
    if not resolved_account_id:
        raise ValueError("account_id is required to persist a decision packet")

    packet_version = _string_value(packet.get("version")) or _string_value(
        packet.get("packet_version")
    )
    report_parameters = {
        "packet_type": DECISION_PACKET_BLOCK_TYPE,
        "packet_version": packet_version or "unknown",
    }
    block_definition = {
        "class_name": DECISION_PACKET_BLOCK_TYPE,
        "block_name": "Optimization decision packet",
        "config": report_parameters,
        # Do not transform, compact, or otherwise alter the packet.  The
        # report service serializes this exact object to its S3 attachment.
        "output": packet,
    }

    # Local import keeps all read-only callers independent from dashboard/S3
    # dependencies and makes this boundary easy to replace in tests.
    from plexus.reports.service import persist_precomputed_report_blocks

    report_id = persist_precomputed_report_blocks(
        report_name=report_name,
        block_definitions=[block_definition],
        account_id=resolved_account_id,
        client=client,
        report_parameters=report_parameters,
        display_title="Optimization decision",
        display_description="Durable optimization decision packet",
    )
    if not isinstance(report_id, str) or not report_id:
        raise RuntimeError("Decision packet persistence returned no report ID.")
    return PersistedDecisionPacket(report_id=report_id)


def _string_value(value: Any) -> Optional[str]:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None

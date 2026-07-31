from __future__ import annotations

import json

import pytest


def test_persist_false_does_not_invoke_report_persistence(monkeypatch) -> None:
    from plexus.optimization.persistence import persist_decision_packet

    invoked = False

    def unexpected_persist(**_kwargs):
        nonlocal invoked
        invoked = True

    monkeypatch.setattr(
        "plexus.reports.service.persist_precomputed_report_blocks", unexpected_persist
    )

    reference = persist_decision_packet(
        {"packet_version": "optimization-decision-packet-v1", "summary": "test"},
        client=object(),
        account_id="account-1",
        persist=False,
    )

    assert reference is None
    assert invoked is False


def test_persist_true_stores_full_packet_only_as_report_block_attachment(monkeypatch) -> None:
    from plexus.optimization.persistence import persist_decision_packet

    packet = {
        "packet_version": "optimization-decision-packet-v1",
        "summary": "exact decision packet",
        "evidence": {"watermark": "frozen"},
    }
    captured = {}

    def fake_persist(**kwargs):
        captured.update(kwargs)
        return "report-1"

    monkeypatch.setattr(
        "plexus.reports.service.persist_precomputed_report_blocks", fake_persist
    )

    reference = persist_decision_packet(
        packet,
        client=object(),
        account_id="account-1",
        persist=True,
    )

    assert reference.report_id == "report-1"
    assert captured["account_id"] == "account-1"
    assert captured["client"] is not None
    assert captured["block_definitions"][0]["output"] is packet
    assert captured["block_definitions"][0]["output"] == packet
    assert captured["report_parameters"] == {
        "packet_type": "OptimizationDecisionPacket",
        "packet_version": "optimization-decision-packet-v1",
    }
    assert json.dumps(captured["block_definitions"][0]["config"])


def test_persistence_failure_is_propagated_without_ephemeral_result(monkeypatch) -> None:
    from plexus.optimization.persistence import persist_decision_packet

    def broken_persist(**_kwargs):
        raise RuntimeError("S3 unavailable")

    monkeypatch.setattr(
        "plexus.reports.service.persist_precomputed_report_blocks", broken_persist
    )

    with pytest.raises(RuntimeError, match="S3 unavailable"):
        persist_decision_packet(
            {"packet_version": "optimization-decision-packet-v1"},
            client=object(),
            account_id="account-1",
            persist=True,
        )

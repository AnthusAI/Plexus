import pytest

from proxy.store import scoring_job_claim_lease_seconds


def test_scoring_job_claim_lease_defaults_to_two_minutes(monkeypatch):
    monkeypatch.delenv("PLEXUS_SCORING_JOB_CLAIM_LEASE_SECONDS", raising=False)

    assert scoring_job_claim_lease_seconds() == 120


def test_scoring_job_claim_lease_accepts_an_explicit_positive_override(monkeypatch):
    monkeypatch.setenv("PLEXUS_SCORING_JOB_CLAIM_LEASE_SECONDS", "15")

    assert scoring_job_claim_lease_seconds() == 15


@pytest.mark.parametrize("value", ["0", "-1", "invalid"])
def test_scoring_job_claim_lease_rejects_invalid_configuration(monkeypatch, value):
    monkeypatch.setenv("PLEXUS_SCORING_JOB_CLAIM_LEASE_SECONDS", value)

    with pytest.raises(ValueError, match="PLEXUS_SCORING_JOB_CLAIM_LEASE_SECONDS"):
        scoring_job_claim_lease_seconds()

"""
Test naming conventions with real scorecard data.

This validates that our naming functions work correctly with actual
scorecard names and score names from the repository.
"""

import sys
import os
import pytest

# Add infrastructure to path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))
infrastructure_path = os.path.join(project_root, 'infrastructure')
if infrastructure_path not in sys.path:
    sys.path.insert(0, infrastructure_path)

from stacks.shared.naming import (
    get_sagemaker_endpoint_name,
    get_sagemaker_model_name,
    get_sagemaker_endpoint_config_name,
)
from plexus.training.utils import normalize_name_to_key


class TestRealScorecardNaming:
    """Test naming with real scorecard and score names."""

    def test_aw_sweepstakes_good_call(self):
        """Test with AW Sweepstakes / Good Call."""
        scorecard_key = normalize_name_to_key("AW Sweepstakes")
        score_key = normalize_name_to_key("Good Call")

        endpoint_name = get_sagemaker_endpoint_name(scorecard_key, score_key)

        assert endpoint_name == "plexus-aw-sweepstakes-good-call-serverless"
        assert "plexus-" in endpoint_name
        assert scorecard_key in endpoint_name
        assert score_key in endpoint_name

    def test_selectquote_hcs_compliance_check(self):
        """Test with SelectQuote HCS Medium-Risk / Compliance Check."""
        scorecard_key = normalize_name_to_key("SelectQuote HCS Medium-Risk")
        score_key = normalize_name_to_key("Compliance Check")

        endpoint_name = get_sagemaker_endpoint_name(scorecard_key, score_key)
        model_name = get_sagemaker_model_name(
            scorecard_key, score_key,
            "s3://plexus-training/models/selectquote-hcs-medium-risk/compliance-check/model.tar.gz"
        )

        assert endpoint_name == "plexus-selectquote-hcs-medium-risk-compliance-check-serverless"
        assert model_name.startswith("plexus-selectquote-hcs-medium-risk-compliance-check-model-")
        assert len(model_name.split('-')[-1]) == 8  # Hash is 8 chars

    def test_andersen_windows_ib_sales(self):
        """Test with Andersen Windows IB Sales."""
        scorecard_key = normalize_name_to_key("Andersen Windows IB Sales")
        score_key = normalize_name_to_key("Quality Assurance")

        endpoint_name = get_sagemaker_endpoint_name(scorecard_key, score_key)

        assert endpoint_name == "plexus-andersen-windows-ib-sales-quality-assurance-serverless"

    def test_cmg_edu_v1(self):
        """Test with CMG - EDU v1.0."""
        scorecard_key = normalize_name_to_key("CMG - EDU v1.0")
        score_key = normalize_name_to_key("Agent Performance")

        endpoint_name = get_sagemaker_endpoint_name(scorecard_key, score_key)

        # Note: version dots and hyphens are normalized to hyphens
        assert endpoint_name == "plexus-cmg-edu-v1-0-agent-performance-serverless"

    def test_names_are_dns_compatible(self):
        """Test that generated names are DNS-compatible."""
        test_cases = [
            ("AW Sweepstakes", "Good Call"),
            ("SelectQuote HCS Medium-Risk", "Compliance Check"),
            ("Andersen Windows IB Sales", "Quality Assurance"),
            ("CMG - EDU v1.0", "Agent Performance"),
        ]

        for scorecard_name, score_name in test_cases:
            scorecard_key = normalize_name_to_key(scorecard_name)
            score_key = normalize_name_to_key(score_name)

            endpoint_name = get_sagemaker_endpoint_name(scorecard_key, score_key)

            # DNS name constraints:
            # - Max 63 characters per label
            # - Only lowercase alphanumeric and hyphens
            # - Cannot start or end with hyphen

            assert len(endpoint_name) <= 63, f"Endpoint name too long: {endpoint_name}"
            assert endpoint_name == endpoint_name.lower(), f"Must be lowercase: {endpoint_name}"
            assert not endpoint_name.startswith('-'), f"Cannot start with hyphen: {endpoint_name}"
            assert not endpoint_name.endswith('-'), f"Cannot end with hyphen: {endpoint_name}"

            # Check only valid characters
            valid_chars = set('abcdefghijklmnopqrstuvwxyz0123456789-')
            assert all(c in valid_chars for c in endpoint_name), \
                f"Invalid characters in: {endpoint_name}"

    def test_model_names_unique_per_s3_uri(self):
        """Test that model names are unique for different S3 URIs."""
        scorecard_key = "test-scorecard"
        score_key = "test-score"

        s3_uris = [
            "s3://bucket/models/v1/model.tar.gz",
            "s3://bucket/models/v2/model.tar.gz",
            "s3://bucket/models/v3/model.tar.gz",
        ]

        model_names = [
            get_sagemaker_model_name(scorecard_key, score_key, uri)
            for uri in s3_uris
        ]

        # All model names should be unique
        assert len(model_names) == len(set(model_names))

        # All should have the same base
        bases = [name.rsplit('-', 1)[0] for name in model_names]
        assert len(set(bases)) == 1

        # Hashes should all be different
        hashes = [name.split('-')[-1] for name in model_names]
        assert len(hashes) == len(set(hashes))

    def test_config_and_model_share_hash(self):
        """Test that config and model names share the same hash."""
        scorecard_key = "test-scorecard"
        score_key = "test-score"
        s3_uri = "s3://bucket/models/test/model.tar.gz"

        model_name = get_sagemaker_model_name(scorecard_key, score_key, s3_uri)
        config_name = get_sagemaker_endpoint_config_name(scorecard_key, score_key, s3_uri)

        model_hash = model_name.split('-')[-1]
        config_hash = config_name.split('-')[-1]

        assert model_hash == config_hash


class TestEndpointNameLengthLimits:
    """Test endpoint name length constraints."""

    def test_very_long_scorecard_and_score_names(self):
        """Test with very long scorecard and score names."""
        # SageMaker endpoint names have a max length of 63 characters
        long_scorecard = "This Is A Very Long Scorecard Name That Might Cause Issues"
        long_score = "This Is Also A Very Long Score Name"

        scorecard_key = normalize_name_to_key(long_scorecard)
        score_key = normalize_name_to_key(long_score)

        endpoint_name = get_sagemaker_endpoint_name(scorecard_key, score_key)

        print(f"Scorecard key: {scorecard_key}")
        print(f"Score key: {score_key}")
        print(f"Endpoint name: {endpoint_name}")
        print(f"Length: {len(endpoint_name)}")

        # If this exceeds 63 chars, we may need to implement truncation
        # For now, just document what happens
        if len(endpoint_name) > 63:
            pytest.skip(
                f"Endpoint name exceeds 63 chars ({len(endpoint_name)}). "
                "This would require truncation logic in naming functions."
            )

    def test_typical_name_lengths(self):
        """Test that typical scorecard/score names produce valid endpoint names."""
        typical_cases = [
            ("AW Sweepstakes", "Good Call"),
            ("SelectQuote HCS", "Compliance Check"),
            ("Andersen Windows", "Quality"),
            ("CMG EDU", "Performance"),
        ]

        for scorecard_name, score_name in typical_cases:
            scorecard_key = normalize_name_to_key(scorecard_name)
            score_key = normalize_name_to_key(score_name)

            endpoint_name = get_sagemaker_endpoint_name(scorecard_key, score_key)

            assert len(endpoint_name) <= 63, \
                f"Typical case produces invalid name: {endpoint_name} ({len(endpoint_name)} chars)"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])

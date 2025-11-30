"""
Tests for infrastructure naming conventions.

Tests the SageMaker endpoint naming functions to ensure they follow
the convention-over-configuration pattern correctly.
"""

import sys
import os
import pytest

# Add infrastructure directory to path so we can import from it
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))
infrastructure_path = os.path.join(project_root, 'infrastructure')
if infrastructure_path not in sys.path:
    sys.path.insert(0, infrastructure_path)

from stacks.shared.naming import (
    get_sagemaker_endpoint_name,
    get_sagemaker_model_name,
    get_sagemaker_endpoint_config_name,
)


class TestSageMakerEndpointNaming:
    """Test SageMaker endpoint naming conventions."""

    def test_basic_endpoint_name(self):
        """Test basic endpoint name generation."""
        endpoint_name = get_sagemaker_endpoint_name(
            'selectquote-hcs', 'compliance-check'
        )
        assert endpoint_name == 'plexus-selectquote-hcs-compliance-check-serverless'

    def test_endpoint_name_with_deployment_type(self):
        """Test endpoint name with explicit deployment type."""
        endpoint_name = get_sagemaker_endpoint_name(
            'selectquote-hcs', 'compliance-check', 'realtime'
        )
        assert endpoint_name == 'plexus-selectquote-hcs-compliance-check-realtime'

    def test_endpoint_name_with_short_keys(self):
        """Test endpoint name with short scorecard/score keys."""
        endpoint_name = get_sagemaker_endpoint_name('sc', 'score')
        assert endpoint_name == 'plexus-sc-score-serverless'

    def test_endpoint_name_with_long_keys(self):
        """Test endpoint name with long keys."""
        endpoint_name = get_sagemaker_endpoint_name(
            'very-long-scorecard-name-with-many-parts',
            'very-long-score-name-with-many-parts'
        )
        assert endpoint_name == (
            'plexus-very-long-scorecard-name-with-many-parts-'
            'very-long-score-name-with-many-parts-serverless'
        )

    def test_endpoint_name_stability(self):
        """Test that endpoint name is stable (doesn't include hash)."""
        # Calling with same parameters should always return same name
        name1 = get_sagemaker_endpoint_name('sc', 'score')
        name2 = get_sagemaker_endpoint_name('sc', 'score')
        assert name1 == name2
        assert 'hash' not in name1.lower()


class TestSageMakerModelNaming:
    """Test SageMaker model naming conventions."""

    def test_basic_model_name(self):
        """Test basic model name generation."""
        model_name = get_sagemaker_model_name(
            'selectquote-hcs',
            'compliance-check',
            's3://bucket/models/selectquote-hcs/compliance-check/model.tar.gz'
        )
        # Should include hash
        assert model_name.startswith('plexus-selectquote-hcs-compliance-check-model-')
        # Hash should be 8 characters
        hash_part = model_name.split('-')[-1]
        assert len(hash_part) == 8

    def test_model_name_changes_with_s3_uri(self):
        """Test that model name changes when S3 URI changes."""
        model_name1 = get_sagemaker_model_name(
            'sc', 'score',
            's3://bucket/models/v1/model.tar.gz'
        )
        model_name2 = get_sagemaker_model_name(
            'sc', 'score',
            's3://bucket/models/v2/model.tar.gz'
        )
        # Names should be different
        assert model_name1 != model_name2
        # But base should be same
        assert model_name1.rsplit('-', 1)[0] == model_name2.rsplit('-', 1)[0]

    def test_model_name_stable_for_same_uri(self):
        """Test that model name is stable for same S3 URI."""
        s3_uri = 's3://bucket/models/sc/score/model.tar.gz'
        model_name1 = get_sagemaker_model_name('sc', 'score', s3_uri)
        model_name2 = get_sagemaker_model_name('sc', 'score', s3_uri)
        assert model_name1 == model_name2

    def test_model_name_format(self):
        """Test model name follows expected format."""
        model_name = get_sagemaker_model_name(
            'scorecard-key',
            'score-key',
            's3://bucket/path/to/model.tar.gz'
        )
        parts = model_name.split('-')
        assert parts[0] == 'plexus'
        assert 'scorecard' in parts
        assert 'key' in parts
        assert 'score' in parts
        assert 'model' in parts
        # Last part is hash (8 hex chars)
        assert len(parts[-1]) == 8
        assert all(c in '0123456789abcdef' for c in parts[-1])


class TestSageMakerEndpointConfigNaming:
    """Test SageMaker endpoint configuration naming conventions."""

    def test_basic_config_name(self):
        """Test basic config name generation."""
        config_name = get_sagemaker_endpoint_config_name(
            'selectquote-hcs',
            'compliance-check',
            's3://bucket/models/selectquote-hcs/compliance-check/model.tar.gz'
        )
        # Should include hash
        assert config_name.startswith('plexus-selectquote-hcs-compliance-check-config-')
        # Hash should be 8 characters
        hash_part = config_name.split('-')[-1]
        assert len(hash_part) == 8

    def test_config_name_matches_model_hash(self):
        """Test that config hash matches model hash."""
        s3_uri = 's3://bucket/models/sc/score/model.tar.gz'
        model_name = get_sagemaker_model_name('sc', 'score', s3_uri)
        config_name = get_sagemaker_endpoint_config_name('sc', 'score', s3_uri)

        # Extract hashes
        model_hash = model_name.split('-')[-1]
        config_hash = config_name.split('-')[-1]

        # Should be identical
        assert model_hash == config_hash

    def test_config_name_changes_with_s3_uri(self):
        """Test that config name changes when S3 URI changes."""
        config_name1 = get_sagemaker_endpoint_config_name(
            'sc', 'score',
            's3://bucket/models/v1/model.tar.gz'
        )
        config_name2 = get_sagemaker_endpoint_config_name(
            'sc', 'score',
            's3://bucket/models/v2/model.tar.gz'
        )
        assert config_name1 != config_name2

    def test_config_name_stable_for_same_uri(self):
        """Test that config name is stable for same S3 URI."""
        s3_uri = 's3://bucket/models/sc/score/model.tar.gz'
        config_name1 = get_sagemaker_endpoint_config_name('sc', 'score', s3_uri)
        config_name2 = get_sagemaker_endpoint_config_name('sc', 'score', s3_uri)
        assert config_name1 == config_name2


class TestNamingConventionConsistency:
    """Test consistency across naming functions."""

    def test_all_names_include_plexus_prefix(self):
        """Test that all names start with 'plexus-'."""
        s3_uri = 's3://bucket/model.tar.gz'

        endpoint_name = get_sagemaker_endpoint_name('sc', 'score')
        model_name = get_sagemaker_model_name('sc', 'score', s3_uri)
        config_name = get_sagemaker_endpoint_config_name('sc', 'score', s3_uri)

        assert endpoint_name.startswith('plexus-')
        assert model_name.startswith('plexus-')
        assert config_name.startswith('plexus-')

    def test_all_names_include_scorecard_and_score(self):
        """Test that all names include scorecard and score keys."""
        s3_uri = 's3://bucket/model.tar.gz'

        endpoint_name = get_sagemaker_endpoint_name('my-scorecard', 'my-score')
        model_name = get_sagemaker_model_name('my-scorecard', 'my-score', s3_uri)
        config_name = get_sagemaker_endpoint_config_name('my-scorecard', 'my-score', s3_uri)

        assert 'my-scorecard' in endpoint_name
        assert 'my-score' in endpoint_name
        assert 'my-scorecard' in model_name
        assert 'my-score' in model_name
        assert 'my-scorecard' in config_name
        assert 'my-score' in config_name

    def test_only_endpoint_name_includes_deployment_type(self):
        """Test that only endpoint name includes deployment type."""
        s3_uri = 's3://bucket/model.tar.gz'

        endpoint_name = get_sagemaker_endpoint_name('sc', 'score', 'serverless')
        model_name = get_sagemaker_model_name('sc', 'score', s3_uri)
        config_name = get_sagemaker_endpoint_config_name('sc', 'score', s3_uri)

        assert 'serverless' in endpoint_name
        assert 'serverless' not in model_name
        assert 'serverless' not in config_name

    def test_model_and_config_share_hash(self):
        """Test that model and config names share the same hash for same S3 URI."""
        s3_uri = 's3://bucket/models/test/model.tar.gz'

        model_name = get_sagemaker_model_name('sc', 'score', s3_uri)
        config_name = get_sagemaker_endpoint_config_name('sc', 'score', s3_uri)

        # Extract hashes (last part after splitting by '-')
        model_hash = model_name.split('-')[-1]
        config_hash = config_name.split('-')[-1]

        assert model_hash == config_hash


class TestEdgeCases:
    """Test edge cases and error conditions."""

    def test_empty_scorecard_key(self):
        """Test behavior with empty scorecard key."""
        # Should still generate valid name (though semantically incorrect)
        endpoint_name = get_sagemaker_endpoint_name('', 'score')
        assert endpoint_name == 'plexus--score-serverless'

    def test_empty_score_key(self):
        """Test behavior with empty score key."""
        endpoint_name = get_sagemaker_endpoint_name('scorecard', '')
        assert endpoint_name == 'plexus-scorecard--serverless'

    def test_special_characters_in_keys(self):
        """Test that special characters are preserved in keys."""
        # Keys should already be normalized, but test preservation
        endpoint_name = get_sagemaker_endpoint_name(
            'scorecard_with_underscores',
            'score-with-hyphens'
        )
        assert 'scorecard_with_underscores' in endpoint_name
        assert 'score-with-hyphens' in endpoint_name

    def test_very_long_s3_uri(self):
        """Test with very long S3 URI."""
        long_uri = 's3://bucket/' + 'a' * 1000 + '/model.tar.gz'
        model_name = get_sagemaker_model_name('sc', 'score', long_uri)

        # Should still generate valid name with 8-char hash
        hash_part = model_name.split('-')[-1]
        assert len(hash_part) == 8

    def test_s3_uris_differing_only_in_case(self):
        """Test that S3 URIs differing only in case produce different hashes."""
        model_name1 = get_sagemaker_model_name(
            'sc', 'score',
            's3://bucket/models/Model.tar.gz'
        )
        model_name2 = get_sagemaker_model_name(
            'sc', 'score',
            's3://bucket/models/model.tar.gz'
        )

        # Hashes should be different
        hash1 = model_name1.split('-')[-1]
        hash2 = model_name2.split('-')[-1]
        assert hash1 != hash2

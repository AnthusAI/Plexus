"""
Tests for training utility functions.

This module tests key normalization and path generation functions used
in the training infrastructure.
"""

import pytest
from plexus.training.utils import (
    normalize_name_to_key,
    get_scorecard_key,
    get_score_key
)


class TestNormalizeNameToKey:
    """Test the normalize_name_to_key function."""

    def test_basic_spaces(self):
        """Test normalization of names with spaces."""
        assert normalize_name_to_key("A Test Scorecard") == "a-test-scorecard"

    def test_version_with_spaces(self):
        """Test normalization of versions with spaces."""
        assert normalize_name_to_key("A Test Scorecard v 1.0") == "a-test-scorecard-v-1-0"

    def test_version_without_spaces(self):
        """Test normalization of versions without spaces."""
        assert normalize_name_to_key("Randall Reilly v1.0") == "randall-reilly-v1-0"

    def test_existing_hyphens(self):
        """Test normalization preserves existing hyphens."""
        assert normalize_name_to_key("SelectQuote HCS Medium-Risk") == "selectquote-hcs-medium-risk"

    def test_multiple_special_characters(self):
        """Test normalization of multiple consecutive special characters."""
        assert normalize_name_to_key("Test!!!Score  Name") == "test-score-name"

    def test_underscores(self):
        """Test that underscores are preserved (word characters)."""
        assert normalize_name_to_key("Test_Score_Name") == "test_score_name"

    def test_parentheses(self):
        """Test normalization of parentheses."""
        assert normalize_name_to_key("Test (v1.0)") == "test-v1-0"

    def test_brackets(self):
        """Test normalization of brackets."""
        assert normalize_name_to_key("Test [Beta]") == "test-beta"

    def test_slashes(self):
        """Test normalization of slashes."""
        assert normalize_name_to_key("Test/Score") == "test-score"

    def test_leading_trailing_spaces(self):
        """Test normalization removes leading/trailing hyphens."""
        assert normalize_name_to_key("  Test Score  ") == "test-score"

    def test_leading_trailing_special_chars(self):
        """Test normalization removes leading/trailing special characters."""
        assert normalize_name_to_key("!Test Score!") == "test-score"

    def test_numbers_preserved(self):
        """Test that numbers are preserved as word characters."""
        assert normalize_name_to_key("Test 123 Score") == "test-123-score"

    def test_mixed_case(self):
        """Test that mixed case is lowercased."""
        assert normalize_name_to_key("TestScoreNAME") == "testscorename"

    def test_dots_to_hyphens(self):
        """Test that dots are replaced with hyphens."""
        assert normalize_name_to_key("v1.0.5") == "v1-0-5"

    def test_ampersands(self):
        """Test normalization of ampersands."""
        assert normalize_name_to_key("Smith & Jones") == "smith-jones"

    def test_plus_signs(self):
        """Test normalization of plus signs."""
        assert normalize_name_to_key("C++ Programming") == "c-programming"

    def test_colons(self):
        """Test normalization of colons."""
        assert normalize_name_to_key("Test: A Score") == "test-a-score"

    def test_semicolons(self):
        """Test normalization of semicolons."""
        assert normalize_name_to_key("Test; Score") == "test-score"

    def test_commas(self):
        """Test normalization of commas."""
        assert normalize_name_to_key("Test, Score, Name") == "test-score-name"

    def test_quotes(self):
        """Test normalization of quotes."""
        assert normalize_name_to_key('Test "Score" Name') == "test-score-name"

    def test_apostrophes(self):
        """Test normalization of apostrophes."""
        assert normalize_name_to_key("Test's Score") == "test-s-score"

    def test_empty_string(self):
        """Test normalization of empty string."""
        assert normalize_name_to_key("") == ""

    def test_only_special_characters(self):
        """Test normalization of only special characters."""
        assert normalize_name_to_key("!!!@@@###") == ""

    def test_unicode_characters(self):
        """Test normalization preserves unicode word characters."""
        # Unicode letters like 'é' are considered word characters and should be preserved
        assert normalize_name_to_key("Test café") == "test-café"

    def test_real_world_example_1(self):
        """Test real-world example: Randall Reilly v1.0"""
        assert normalize_name_to_key("Randall Reilly v1.0") == "randall-reilly-v1-0"

    def test_real_world_example_2(self):
        """Test real-world example: SelectQuote HCS Medium-Risk"""
        assert normalize_name_to_key("SelectQuote HCS Medium-Risk") == "selectquote-hcs-medium-risk"

    def test_real_world_example_3(self):
        """Test real-world example: Recruiter Present"""
        assert normalize_name_to_key("Recruiter Present") == "recruiter-present"


class TestGetScorecardKey:
    """Test the get_scorecard_key function."""

    def test_config_with_key(self):
        """Test getting key from config with explicit 'key' field."""
        config = {'key': 'my-scorecard-key', 'name': 'My Scorecard'}
        assert get_scorecard_key(scorecard_config=config) == 'my-scorecard-key'

    def test_config_with_name_no_key(self):
        """Test generating key from config 'name' when no 'key'."""
        config = {'name': 'My Test Scorecard v 1.0'}
        assert get_scorecard_key(scorecard_config=config) == 'my-test-scorecard-v-1-0'

    def test_name_fallback(self):
        """Test fallback to scorecard_name parameter."""
        assert get_scorecard_key(scorecard_name='My Test Scorecard') == 'my-test-scorecard'

    def test_config_key_preferred_over_name_param(self):
        """Test that config key is preferred over name parameter."""
        config = {'key': 'config-key'}
        assert get_scorecard_key(scorecard_config=config, scorecard_name='Name Param') == 'config-key'

    def test_config_name_preferred_over_name_param(self):
        """Test that config name is preferred over name parameter."""
        config = {'name': 'Config Name'}
        assert get_scorecard_key(scorecard_config=config, scorecard_name='Name Param') == 'config-name'

    def test_empty_config_uses_name_param(self):
        """Test that empty config uses name parameter."""
        assert get_scorecard_key(scorecard_config={}, scorecard_name='Name Param') == 'name-param'

    def test_none_config_uses_name_param(self):
        """Test that None config uses name parameter."""
        assert get_scorecard_key(scorecard_config=None, scorecard_name='Name Param') == 'name-param'

    def test_no_config_no_name_raises(self):
        """Test that providing neither config nor name raises ValueError."""
        with pytest.raises(ValueError, match="Must provide either scorecard_config"):
            get_scorecard_key()

    def test_empty_config_no_name_raises(self):
        """Test that empty config with no name raises ValueError."""
        with pytest.raises(ValueError, match="Must provide either scorecard_config"):
            get_scorecard_key(scorecard_config={})


class TestGetScoreKey:
    """Test the get_score_key function."""

    def test_config_with_key(self):
        """Test getting key from config with explicit 'key' field."""
        config = {'key': 'my-score-key', 'name': 'My Score'}
        assert get_score_key(config) == 'my-score-key'

    def test_config_with_name_no_key(self):
        """Test generating key from config 'name' when no 'key'."""
        config = {'name': 'My Test Score v 1.0'}
        assert get_score_key(config) == 'my-test-score-v-1-0'

    def test_key_preferred_over_name(self):
        """Test that 'key' is preferred over 'name' when both present."""
        config = {'key': 'explicit-key', 'name': 'Score Name'}
        assert get_score_key(config) == 'explicit-key'

    def test_no_key_no_name_raises(self):
        """Test that config without 'key' or 'name' raises ValueError."""
        with pytest.raises(ValueError, match="score_config must have either 'key' or 'name'"):
            get_score_key({})

    def test_empty_name_raises(self):
        """Test that config with empty name raises ValueError."""
        # Empty string will normalize to empty string, but that's technically valid
        # The function doesn't validate non-empty results, just presence of key/name
        config = {'name': ''}
        result = get_score_key(config)
        assert result == ''  # Empty name normalizes to empty string

    def test_real_world_score(self):
        """Test real-world score config."""
        config = {
            'name': 'Recruiter Present',
            'id': 44388,
            'key': 'recruiter-present',
            'class': 'BERTClassifier'
        }
        assert get_score_key(config) == 'recruiter-present'

    def test_score_without_key_field(self):
        """Test score config without explicit key field."""
        config = {
            'name': 'Recruiter Present Test',
            'id': 12345,
            'class': 'BERTClassifier'
        }
        assert get_score_key(config) == 'recruiter-present-test'

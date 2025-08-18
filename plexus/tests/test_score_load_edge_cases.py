"""
Edge case and error scenario tests for Score.load() integration.

This module focuses on testing edge cases, error conditions, and
boundary scenarios for the Score.load() integration changes:
- Network failures
- Malformed configurations
- Missing dependencies
- Cache inconsistencies
- Concurrent access scenarios
"""

import unittest
from unittest.mock import patch, MagicMock, Mock, call
import pytest
import tempfile
import os
import json


class TestScoreLoadErrorScenarios(unittest.TestCase):
    """Test error scenarios in Score.load() integration."""
    
    def setUp(self):
        """Set up test fixtures."""
        from plexus.Evaluation import AccuracyEvaluation
        self.evaluation = MagicMock()
        self.evaluation.scorecard_name = "test_scorecard"
        self.evaluation.logging = MagicMock()
        self.get_score_instance = AccuracyEvaluation.get_score_instance
    
    @patch('plexus.scores.Score.Score.load')
    def test_network_timeout_error(self, mock_score_load):
        """Test handling of network timeout errors."""
        # Arrange
        mock_score_load.side_effect = ConnectionError("Network timeout")
        
        # Act & Assert - ConnectionError should be re-raised immediately
        with self.assertRaises(ConnectionError) as context:
            self.get_score_instance(self.evaluation, "test_score")
        
        # Should only make one call since ConnectionError isn't handled by fallback
        self.assertEqual(mock_score_load.call_count, 1)
        self.assertEqual(str(context.exception), "Network timeout")
    
    @patch('plexus.scores.Score.Score.load')
    def test_permission_denied_error(self, mock_score_load):
        """Test handling of permission denied errors."""
        # Arrange
        mock_score_load.side_effect = PermissionError("Access denied to scorecard")
        
        # Act & Assert
        with self.assertRaises(PermissionError):
            self.get_score_instance(self.evaluation, "test_score")
        
        # Should not attempt fallback for permission errors
        mock_score_load.assert_called_once()
    
    @patch('plexus.scores.Score.Score.load')
    def test_malformed_config_error(self, mock_score_load):
        """Test handling of malformed configuration errors."""
        # Arrange - API error should be propagated directly, no fallback
        mock_score_load.side_effect = ValueError("API loading failed - Invalid YAML structure")
        
        # Act & Assert
        with self.assertRaises(ValueError) as context:
            self.get_score_instance(self.evaluation, "test_score")
        
        error_msg = str(context.exception)
        self.assertIn("Invalid YAML structure", error_msg)
    
    @patch('plexus.scores.Score.Score.load')
    def test_empty_scorecard_name(self, mock_score_load):
        """Test handling of empty scorecard name."""
        # Arrange
        self.evaluation.scorecard_name = ""
        
        # Act
        self.get_score_instance(self.evaluation, "test_score")
        
        # Assert - should still attempt to load with empty string
        mock_score_load.assert_called_with(
            scorecard_identifier="",
            score_name="test_score",
            use_cache=True,
            yaml_only=False
        )
    
    @patch('plexus.scores.Score.Score.load')
    def test_none_scorecard_name(self, mock_score_load):
        """Test handling of None scorecard name."""
        # Arrange
        self.evaluation.scorecard_name = None
        
        # Act
        self.get_score_instance(self.evaluation, "test_score")
        
        # Assert - should still attempt to load with None
        mock_score_load.assert_called_with(
            scorecard_identifier=None,
            score_name="test_score", 
            use_cache=True,
            yaml_only=False
        )


class TestConcurrentAccessScenarios(unittest.TestCase):
    """Test concurrent access scenarios."""
    
    @patch('plexus.scores.Score.Score.load')
    def test_concurrent_evaluation_instances(self, mock_score_load):
        """Test multiple evaluation instances loading same score concurrently."""
        # Arrange
        from plexus.Evaluation import AccuracyEvaluation
        
        eval1 = MagicMock()
        eval1.scorecard_name = "scorecard1"
        eval1.logging = MagicMock()
        
        eval2 = MagicMock()
        eval2.scorecard_name = "scorecard2"
        eval2.logging = MagicMock()
        
        mock_score1 = MagicMock()
        mock_score2 = MagicMock()
        mock_score_load.side_effect = [mock_score1, mock_score2]
        
        # Act
        result1 = AccuracyEvaluation.get_score_instance(eval1, "same_score")
        result2 = AccuracyEvaluation.get_score_instance(eval2, "same_score")
        
        # Assert - both should succeed with correct parameters
        expected_calls = [
            call(scorecard_identifier="scorecard1", score_name="same_score", use_cache=True, yaml_only=False),
            call(scorecard_identifier="scorecard2", score_name="same_score", use_cache=True, yaml_only=False)
        ]
        mock_score_load.assert_has_calls(expected_calls)
        self.assertEqual(result1, mock_score1)
        self.assertEqual(result2, mock_score2)


class TestDataDrivenSamplesEdgeCases(unittest.TestCase):
    """Test edge cases in get_data_driven_samples function."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.scorecard_instance = MagicMock()
        self.scorecard_name = "test_scorecard"
        self.score_name = "test_score"
        self.score_config = {"class": "TestScore", "data": {}}
        self.content_ids_set = set()
    
    @patch('plexus.scores.Score.Score.load')
    @patch('plexus.cli.evaluation.evaluations.logging')
    def test_score_instance_missing_dataframe(self, mock_logging, mock_score_load):
        """Test handling when score instance doesn't have dataframe attribute."""
        # Arrange
        mock_score_instance = MagicMock()
        # Remove dataframe attribute
        del mock_score_instance.dataframe
        mock_score_load.return_value = mock_score_instance
        
        from plexus.cli.evaluation.evaluations import get_data_driven_samples
        
        # Act
        result = get_data_driven_samples(
            self.scorecard_instance, self.scorecard_name, self.score_name,
            self.score_config, fresh=False, reload=False, content_ids_to_sample_set=self.content_ids_set
        )
        
        # Assert - should return empty list and log error
        self.assertEqual(result, [])
        mock_logging.error.assert_called()
        error_calls = [str(call) for call in mock_logging.error.call_args_list]
        self.assertTrue(any("does not have a 'dataframe' attribute" in str(call) for call in error_calls))
    
    @patch('plexus.scores.Score.Score.load')
    @patch('plexus.cli.evaluation.evaluations.logging')
    def test_score_instance_none_dataframe(self, mock_logging, mock_score_load):
        """Test handling when score instance has None dataframe."""
        # Arrange
        mock_score_instance = MagicMock()
        mock_score_instance.dataframe = None
        mock_score_load.return_value = mock_score_instance
        
        from plexus.cli.evaluation.evaluations import get_data_driven_samples
        
        # Act
        result = get_data_driven_samples(
            self.scorecard_instance, self.scorecard_name, self.score_name,
            self.score_config, fresh=False, reload=False, content_ids_to_sample_set=self.content_ids_set
        )
        
        # Assert - should return empty list and log error
        self.assertEqual(result, [])
        mock_logging.error.assert_called()
        error_calls = [str(call) for call in mock_logging.error.call_args_list]
        self.assertTrue(any("dataframe is None" in str(call) for call in error_calls))
    
    @patch('plexus.scores.Score.Score.load')
    @patch('plexus.cli.evaluation.evaluations.logging')
    def test_score_instance_empty_dataframe(self, mock_logging, mock_score_load):
        """Test handling when score instance has empty dataframe."""
        # Arrange
        mock_score_instance = MagicMock()
        mock_score_instance.dataframe = MagicMock()
        mock_score_instance.dataframe.__len__ = MagicMock(return_value=0)  # Empty dataframe
        mock_score_load.return_value = mock_score_instance
        
        from plexus.cli.evaluation.evaluations import get_data_driven_samples
        
        # Act
        result = get_data_driven_samples(
            self.scorecard_instance, self.scorecard_name, self.score_name,
            self.score_config, fresh=False, reload=False, content_ids_to_sample_set=self.content_ids_set
        )
        
        # Assert - should return empty list and log error with helpful message
        self.assertEqual(result, [])
        mock_logging.error.assert_called()
        error_calls = [str(call) for call in mock_logging.error.call_args_list]
        self.assertTrue(any("dataframe is empty" in str(call) for call in error_calls))
        # Check for helpful error messages
        self.assertTrue(any("No data matching the specified criteria" in str(call) for call in error_calls))
    
    @patch('plexus.scores.Score.Score.load')
    @patch('plexus.cli.evaluation.evaluations.importlib')
    @patch('plexus.cli.evaluation.evaluations.logging')
    def test_fallback_import_error(self, mock_logging, mock_importlib, mock_score_load):
        """Test handling when both Score.load() and manual import fail."""
        # Arrange
        mock_score_load.side_effect = ValueError("Score.load() failed")
        mock_importlib.import_module.side_effect = ImportError("Module not found")
        
        from plexus.cli.evaluation.evaluations import get_data_driven_samples
        
        # Act
        result = get_data_driven_samples(
            self.scorecard_instance, self.scorecard_name, self.score_name,
            self.score_config, fresh=False, reload=False, content_ids_to_sample_set=self.content_ids_set
        )
        
        # Assert - should return empty list
        self.assertEqual(result, [])
        mock_logging.error.assert_called()


class TestDashboardClientEdgeCases(unittest.TestCase):
    """Test edge cases in dashboard client score loading."""
    
    def setUp(self):
        """Set up test fixtures."""
        from plexus.dashboard.api.client import PlexusDashboardClient
        self.client = PlexusDashboardClient.__new__(PlexusDashboardClient)
    
    @patch('plexus.scores.Score.Score.load')
    def test_load_with_special_characters(self, mock_score_load):
        """Test loading scores with special characters in names."""
        # Arrange
        mock_score_instance = MagicMock()
        mock_score_load.return_value = mock_score_instance
        
        # Act
        result = self.client.load_score_configuration(
            "scorecard/with/slashes", "score-with-dashes_and_underscores"
        )
        
        # Assert
        mock_score_load.assert_called_once_with(
            scorecard_identifier="scorecard/with/slashes",
            score_name="score-with-dashes_and_underscores",
            use_cache=False,
            yaml_only=False
        )
        self.assertEqual(result, mock_score_instance)
    
    @patch('plexus.scores.Score.Score.load')
    def test_load_with_unicode_characters(self, mock_score_load):
        """Test loading scores with unicode characters in names."""
        # Arrange
        mock_score_instance = MagicMock()
        mock_score_load.return_value = mock_score_instance
        
        # Act
        result = self.client.load_score_configuration(
            "scorecard_ñámé", "score_测试"
        )
        
        # Assert
        mock_score_load.assert_called_once_with(
            scorecard_identifier="scorecard_ñámé",
            score_name="score_测试",
            use_cache=False,
            yaml_only=False
        )
        self.assertEqual(result, mock_score_instance)
    
    @patch('plexus.scores.Score.Score.load')
    def test_load_with_very_long_names(self, mock_score_load):
        """Test loading scores with very long names."""
        # Arrange
        mock_score_instance = MagicMock()
        mock_score_load.return_value = mock_score_instance
        long_name = "a" * 1000  # Very long name
        
        # Act
        result = self.client.load_score_configuration(long_name, long_name)
        
        # Assert
        mock_score_load.assert_called_once_with(
            scorecard_identifier=long_name,
            score_name=long_name,
            use_cache=False,
            yaml_only=False
        )
        self.assertEqual(result, mock_score_instance)


class TestParameterValidation(unittest.TestCase):
    """Test parameter validation and boundary conditions."""
    
    def setUp(self):
        """Set up test fixtures."""
        from plexus.dashboard.api.client import PlexusDashboardClient
        self.client = PlexusDashboardClient.__new__(PlexusDashboardClient)
    
    @patch('plexus.scores.Score.Score.load')
    def test_empty_string_parameters(self, mock_score_load):
        """Test handling of empty string parameters."""
        # Arrange
        mock_score_instance = MagicMock()
        mock_score_load.return_value = mock_score_instance
        
        # Act
        result = self.client.load_score_configuration("", "")
        
        # Assert - should pass empty strings through
        mock_score_load.assert_called_once_with(
            scorecard_identifier="",
            score_name="",
            use_cache=False,
            yaml_only=False
        )
        self.assertEqual(result, mock_score_instance)
    
    @patch('plexus.scores.Score.Score.load')
    def test_none_parameters(self, mock_score_load):
        """Test handling of None parameters."""
        # Arrange
        mock_score_instance = MagicMock()
        mock_score_load.return_value = mock_score_instance
        
        # Act
        result = self.client.load_score_configuration(None, None)
        
        # Assert - should pass None values through
        mock_score_load.assert_called_once_with(
            scorecard_identifier=None,
            score_name=None,
            use_cache=False,
            yaml_only=False
        )
        self.assertEqual(result, mock_score_instance)
    
    @patch('plexus.scores.Score.Score.load')
    def test_boolean_parameter_combinations(self, mock_score_load):
        """Test all combinations of boolean parameters."""
        # Arrange
        mock_score_instance = MagicMock()
        mock_score_load.return_value = mock_score_instance
        
        combinations = [
            (True, True),
            (True, False),
            (False, True),
            (False, False)
        ]
        
        for use_cache, yaml_only in combinations:
            with self.subTest(use_cache=use_cache, yaml_only=yaml_only):
                # Act
                result = self.client.load_score_configuration(
                    "test_scorecard", "test_score", 
                    use_cache=use_cache, yaml_only=yaml_only
                )
                
                # Assert
                mock_score_load.assert_called_with(
                    scorecard_identifier="test_scorecard",
                    score_name="test_score",
                    use_cache=use_cache,
                    yaml_only=yaml_only
                )
                self.assertEqual(result, mock_score_instance)


class TestLoggingAndDebugging(unittest.TestCase):
    """Test logging and debugging functionality."""
    
    @patch('plexus.scores.Score.Score.load')
    def test_logging_in_fallback_scenario(self, mock_score_load):
        """Test that API errors are propagated directly without any fallback."""
        # Arrange
        from plexus.Evaluation import AccuracyEvaluation
        evaluation = MagicMock()
        evaluation.scorecard_name = "test_scorecard"
        evaluation.logging = MagicMock()
        
        mock_score_load.side_effect = ValueError("API loading failed")
        
        # Act & Assert
        with self.assertRaises(ValueError) as context:
            AccuracyEvaluation.get_score_instance(evaluation, "test_score")
        
        # Verify the original error is propagated
        self.assertIn("API loading failed", str(context.exception))
        
        # Verify no fallback logging occurred
        evaluation.logging.info.assert_not_called()
        evaluation.logging.warning.assert_not_called()
    
    @patch('plexus.scores.Score.Score.load')
    def test_logging_in_double_failure_scenario(self, mock_score_load):
        """Test that API errors are propagated directly without fallback."""
        # Arrange
        from plexus.Evaluation import AccuracyEvaluation
        evaluation = MagicMock()
        evaluation.scorecard_name = "test_scorecard"
        evaluation.logging = MagicMock()
        
        mock_score_load.side_effect = ValueError("API loading failed")
        
        # Act & Assert
        with self.assertRaises(ValueError) as context:
            AccuracyEvaluation.get_score_instance(evaluation, "test_score")
        
        # Verify the original error is propagated
        self.assertIn("API loading failed", str(context.exception))
        
        # Verify no fallback logging occurred
        evaluation.logging.info.assert_not_called()
        evaluation.logging.warning.assert_not_called()


if __name__ == '__main__':
    # Run with high verbosity for detailed output
    unittest.main(verbosity=2)
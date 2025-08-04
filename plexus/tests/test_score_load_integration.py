"""
Tests for Score.load() integration in the evaluation system.

This module tests the standardized Score.load() method integration across:
- Evaluation.get_score_instance()
- EvaluationCommands.get_data_driven_samples()  
- PlexusDashboardClient.load_score_configuration()

Focus areas:
- API loading with caching
- YAML-only loading
- Direct error propagation (no fallback behavior)
- Error handling
- Backward compatibility
"""

import unittest
from unittest.mock import patch, MagicMock, Mock
import pytest

from plexus.scores.Score import Score


class TestEvaluationGetScoreInstance(unittest.TestCase):
    """Test the updated get_score_instance method in Evaluation class."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Create a mock evaluation instance
        self.evaluation = MagicMock()
        self.evaluation.scorecard_name = "test_scorecard"
        self.evaluation.logging = MagicMock()
        
        # Import the actual method we want to test
        from plexus.Evaluation import AccuracyEvaluation
        # Get the actual method implementation
        self.get_score_instance = AccuracyEvaluation.get_score_instance
    
    @patch('plexus.scores.Score.Score.load')
    def test_successful_score_load(self, mock_score_load):
        """Test successful score loading using Score.load()."""
        # Arrange
        mock_score_instance = MagicMock()
        mock_score_load.return_value = mock_score_instance
        
        # Act
        result = self.get_score_instance(self.evaluation, "test_score")
        
        # Assert
        mock_score_load.assert_called_once_with(
            scorecard_identifier="test_scorecard",
            score_name="test_score",
            use_cache=True,
            yaml_only=False
        )
        self.assertEqual(result, mock_score_instance)
    
    @patch('plexus.scores.Score.Score.load')
    def test_api_load_fails_fallback_to_yaml(self, mock_score_load):
        """Test that API errors are propagated directly without fallback."""
        # Arrange
        mock_score_load.side_effect = ValueError("API loading failed")
        
        # Act & Assert
        with self.assertRaises(ValueError) as context:
            self.get_score_instance(self.evaluation, "test_score")
        
        # Verify error is propagated
        self.assertIn("API loading failed", str(context.exception))
        
        # Verify only one call was made (no fallback)
        self.assertEqual(mock_score_load.call_count, 1)
        mock_score_load.assert_called_once_with(
            scorecard_identifier="test_scorecard",
            score_name="test_score",
            use_cache=True,
            yaml_only=False
        )
    
    @patch('plexus.scores.Score.Score.load')
    def test_both_load_methods_fail(self, mock_score_load):
        """Test that API errors are propagated directly without fallback attempts."""
        # Arrange
        mock_score_load.side_effect = ValueError("API loading failed")
        
        # Act & Assert
        with self.assertRaises(ValueError) as context:
            self.get_score_instance(self.evaluation, "test_score")
        
        # Verify error is propagated directly
        self.assertEqual(str(context.exception), "API loading failed")
        
        # Verify only one call was made (no fallback)
        self.assertEqual(mock_score_load.call_count, 1)
        mock_score_load.assert_called_once_with(
            scorecard_identifier="test_scorecard",
            score_name="test_score",
            use_cache=True,
            yaml_only=False
        )
    
    @patch('plexus.scores.Score.Score.load')
    def test_non_not_found_error_propagated(self, mock_score_load):
        """Test that non-'not found' errors are propagated directly."""
        # Arrange
        mock_score_load.side_effect = ValueError("Some other error")
        
        # Act & Assert
        with self.assertRaises(ValueError) as context:
            self.get_score_instance(self.evaluation, "test_score")
        
        # Should only make one call and propagate the error
        mock_score_load.assert_called_once()
        self.assertEqual(str(context.exception), "Some other error")


class TestEvaluationCommandsDataDrivenSamples(unittest.TestCase):
    """Test the updated get_data_driven_samples function."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Mock dependencies
        self.scorecard_instance = MagicMock()
        self.scorecard_name = "test_scorecard" 
        self.score_name = "test_score"
        self.score_config = {"class": "TestScore", "data": {}}
        self.content_ids_set = set()
    
    @patch('plexus.scores.Score.Score.load')
    @patch('plexus.cli.EvaluationCommands.logging')
    def test_successful_score_load(self, mock_logging, mock_score_load):
        """Test successful score loading using Score.load()."""
        # Arrange
        mock_score_instance = MagicMock()
        mock_score_instance.dataframe = MagicMock()
        mock_score_instance.dataframe.__len__ = MagicMock(return_value=10)
        mock_score_instance.dataframe.to_dict.return_value = [{"content_id": 1, "text": "test"}]
        mock_score_load.return_value = mock_score_instance
        
        # Import the function to test
        from plexus.cli.EvaluationCommands import get_data_driven_samples
        
        # Act
        result = get_data_driven_samples(
            self.scorecard_instance, self.scorecard_name, self.score_name,
            self.score_config, fresh=False, content_ids_to_sample_set=self.content_ids_set
        )
        
        # Assert
        mock_score_load.assert_called_once_with(
            scorecard_identifier="test_scorecard",
            score_name="test_score", 
            use_cache=True,
            yaml_only=False
        )
        mock_logging.info.assert_any_call("Successfully loaded score 'test_score' using Score.load()")
        # Verify that Score.load() was used successfully
        self.assertTrue(mock_score_load.called)
        self.assertIsInstance(result, list)
    
    @patch('plexus.scores.Score.Score.load')
    def test_score_load_fails_returns_empty_list(self, mock_score_load):
        """Test that Score.load() failures result in empty list returned."""
        # Arrange
        mock_score_load.side_effect = ValueError("Score.load() failed")
        
        # Import the function to test
        from plexus.cli.EvaluationCommands import get_data_driven_samples
        
        # Act
        result = get_data_driven_samples(
            self.scorecard_instance, self.scorecard_name, self.score_name,
            self.score_config, fresh=False, content_ids_to_sample_set=self.content_ids_set
        )
        
        # Assert - function catches exception and returns empty list
        mock_score_load.assert_called_once()
        self.assertEqual(result, [])
        self.assertIsInstance(result, list)


class TestPlexusDashboardClient(unittest.TestCase):
    """Test the new load_score_configuration method in PlexusDashboardClient."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Create a mock client instance without full initialization
        from plexus.dashboard.api.client import PlexusDashboardClient
        self.client = PlexusDashboardClient.__new__(PlexusDashboardClient)
    
    @patch('plexus.scores.Score.Score.load')
    def test_load_score_configuration_default_params(self, mock_score_load):
        """Test load_score_configuration with default parameters."""
        # Arrange
        mock_score_instance = MagicMock()
        mock_score_load.return_value = mock_score_instance
        
        # Act
        result = self.client.load_score_configuration("test_scorecard", "test_score")
        
        # Assert
        mock_score_load.assert_called_once_with(
            scorecard_identifier="test_scorecard",
            score_name="test_score",
            use_cache=False,  # Default is False for dashboard client (no-cache mode)
            yaml_only=False
        )
        self.assertEqual(result, mock_score_instance)
    
    @patch('plexus.scores.Score.Score.load')
    def test_load_score_configuration_custom_params(self, mock_score_load):
        """Test load_score_configuration with custom parameters."""
        # Arrange
        mock_score_instance = MagicMock()
        mock_score_load.return_value = mock_score_instance
        
        # Act
        result = self.client.load_score_configuration(
            "test_scorecard", "test_score", use_cache=False, yaml_only=True
        )
        
        # Assert
        mock_score_load.assert_called_once_with(
            scorecard_identifier="test_scorecard",
            score_name="test_score",
            use_cache=False,
            yaml_only=True
        )
        self.assertEqual(result, mock_score_instance)
    
    @patch('plexus.scores.Score.Score.load')
    def test_load_score_configuration_error_propagation(self, mock_score_load):
        """Test that errors from Score.load() are properly propagated."""
        # Arrange
        mock_score_load.side_effect = ValueError("Score not found")
        
        # Act & Assert
        with self.assertRaises(ValueError) as context:
            self.client.load_score_configuration("test_scorecard", "test_score")
        
        self.assertEqual(str(context.exception), "Score not found")


class TestScoreLoadOperationalModes(unittest.TestCase):
    """Test the three operational modes of Score.load() integration."""
    
    @patch('plexus.scores.Score.Score.load')
    def test_api_plus_cache_mode(self, mock_score_load):
        """Test the default API + cache mode."""
        # Test through Evaluation.get_score_instance
        from plexus.Evaluation import AccuracyEvaluation
        evaluation = MagicMock()
        evaluation.scorecard_name = "test_scorecard"
        evaluation.logging = MagicMock()
        
        mock_score_instance = MagicMock()
        mock_score_load.return_value = mock_score_instance
        
        # Act
        result = AccuracyEvaluation.get_score_instance(evaluation, "test_score")
        
        # Assert - should use API + cache mode
        mock_score_load.assert_called_with(
            scorecard_identifier="test_scorecard",
            score_name="test_score",
            use_cache=True,
            yaml_only=False
        )
    
    @patch('plexus.scores.Score.Score.load')
    def test_yaml_only_mode_no_fallback(self, mock_score_load):
        """Test that API errors are propagated directly without YAML-only fallback."""
        from plexus.Evaluation import AccuracyEvaluation
        evaluation = MagicMock()
        evaluation.scorecard_name = "test_scorecard"
        evaluation.logging = MagicMock()
        
        # First call fails - no fallback should occur
        mock_score_load.side_effect = ValueError("API not found")
        
        # Act & Assert
        with self.assertRaises(ValueError) as context:
            AccuracyEvaluation.get_score_instance(evaluation, "test_score")
        
        # Should propagate the error directly
        self.assertEqual(str(context.exception), "API not found")
        
        # Should only make one call (no fallback)
        self.assertEqual(mock_score_load.call_count, 1)
        mock_score_load.assert_called_once_with(
            scorecard_identifier="test_scorecard",
            score_name="test_score", 
            use_cache=True,
            yaml_only=False
        )


class TestBackwardCompatibility(unittest.TestCase):
    """Test that changes maintain backward compatibility."""
    
    def test_evaluation_interface_unchanged(self):
        """Test that Evaluation class interface is unchanged."""
        from plexus.Evaluation import AccuracyEvaluation
        
        # Verify get_score_instance method exists and has expected signature
        method = getattr(AccuracyEvaluation, 'get_score_instance')
        self.assertTrue(callable(method))
        
        # Check method signature (should take self and score_name)
        import inspect
        sig = inspect.signature(method)
        params = list(sig.parameters.keys())
        self.assertIn('self', params)
        self.assertIn('score_name', params)
    
    def test_dashboard_client_interface_extended(self):
        """Test that dashboard client has new method without breaking existing interface."""
        from plexus.dashboard.api.client import PlexusDashboardClient
        
        # Verify new method exists
        self.assertTrue(hasattr(PlexusDashboardClient, 'load_score_configuration'))
        method = getattr(PlexusDashboardClient, 'load_score_configuration')
        self.assertTrue(callable(method))
        
        # Check method signature
        import inspect
        sig = inspect.signature(method)
        params = list(sig.parameters.keys())
        self.assertIn('self', params)
        self.assertIn('scorecard_identifier', params)
        self.assertIn('score_name', params)
        self.assertIn('use_cache', params)
        self.assertIn('yaml_only', params)
    
    @patch('plexus.scores.Score.Score.load')
    def test_get_data_driven_samples_error_handling(self, mock_score_load):
        """Test that get_data_driven_samples returns empty list on Score.load() errors."""
        # Arrange - Score.load() fails
        mock_score_load.side_effect = ValueError("Score.load() failed")
        
        from plexus.cli.EvaluationCommands import get_data_driven_samples
        
        score_config = {"class": "TestScore", "data": {}}
        
        # Act - should not raise exception, should return empty list
        result = get_data_driven_samples(
            MagicMock(), "test_scorecard", "test_score", 
            score_config, False, set()
        )
        
        # Assert - should have attempted Score.load() and returned empty list on error
        mock_score_load.assert_called_once()
        self.assertEqual(result, [])
        self.assertIsInstance(result, list)


if __name__ == '__main__':
    # Run with verbose output
    unittest.main(verbosity=2)
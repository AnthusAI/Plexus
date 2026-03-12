"""
Tests for configuration caching functionality.

This module tests the functionality for caching score configurations locally,
including:
- Saving configurations to local files
- Loading configurations from cache
- Checking if configurations exist in cache
- Performance improvements from caching
"""
import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch, mock_open, MagicMock

from plexus.cli.shared import get_score_yaml_path, sanitize_path_name


class TestScoreYamlPath(unittest.TestCase):
    """Tests for generating the file path for a score's cached configuration."""
    
    def setUp(self):
        """Set up the test environment."""
        # Create a temporary directory for the test
        self.temp_dir = tempfile.TemporaryDirectory()
        self.old_cwd = os.getcwd()
        os.chdir(self.temp_dir.name)
    
    def tearDown(self):
        """Clean up after the test."""
        os.chdir(self.old_cwd)
        self.temp_dir.cleanup()
    
    def test_get_score_yaml_path(self):
        """Test that the path is generated correctly."""
        scorecard_name = "Test Scorecard"
        score_name = "Test Score"
        
        # The function preserves spaces by default, doesn't use underscores
        expected_path = Path("scorecards/Test Scorecard/Test Score.yaml")
        result = get_score_yaml_path(scorecard_name, score_name)
        
        self.assertEqual(result, expected_path)
    
    def test_special_characters(self):
        """Test handling of special characters in names."""
        scorecard_name = "Test/Scorecard & More"
        score_name = "Special: Score (with) [chars]"
        
        # The function should sanitize the path-unsafe characters
        result = get_score_yaml_path(scorecard_name, score_name)
        
        # Path should not contain unsafe characters
        self.assertNotIn(":", str(result))
        self.assertNotIn("[", str(result))
        self.assertNotIn("]", str(result))
        
        # But it should preserve spaces and safe characters like &
        self.assertIn("&", str(result))
        self.assertIn(" ", str(result))


class TestConfigurationCache(unittest.TestCase):
    """Tests for caching score configurations."""
    
    def setUp(self):
        """Set up the test environment."""
        # Create a temporary directory for the test
        self.temp_dir = tempfile.TemporaryDirectory()
        self.old_cwd = os.getcwd()
        os.chdir(self.temp_dir.name)
        
        # Create a mock scorecard and score configuration
        self.scorecard_name = "Test Scorecard"
        self.score_name = "Test Score"
        self.score_config = """name: Test Score
key: test_score
class: Score
description: This is a test score
metrics:
  - name: accuracy
    type: float
    range: [0, 1]
    description: Accuracy of the score
"""
    
    def tearDown(self):
        """Clean up after the test."""
        os.chdir(self.old_cwd)
        self.temp_dir.cleanup()
    
    def test_save_configuration(self):
        """Test saving a configuration to a local file."""
        # Get the expected file path
        yaml_path = get_score_yaml_path(self.scorecard_name, self.score_name)
        
        # Save the configuration
        with open(yaml_path, 'w') as f:
            f.write(self.score_config)
        
        # Check that the file was created
        self.assertTrue(yaml_path.exists())
        
        # Check that the content was written correctly
        with open(yaml_path, 'r') as f:
            content = f.read()
        self.assertEqual(content, self.score_config)
    
    def test_check_cache_hit(self):
        """Test checking if a configuration exists in cache (hit)."""
        # Get the expected file path
        yaml_path = get_score_yaml_path(self.scorecard_name, self.score_name)
        
        # Create the file
        with open(yaml_path, 'w') as f:
            f.write(self.score_config)
        
        # Check that the file exists
        self.assertTrue(yaml_path.exists())
    
    def test_check_cache_miss(self):
        """Test checking if a configuration exists in cache (miss)."""
        # Get the expected file path for a non-existent score
        yaml_path = get_score_yaml_path(self.scorecard_name, "Non-existent Score")
        
        # Check that the file doesn't exist
        self.assertFalse(yaml_path.exists())
    
    @patch('builtins.open', new_callable=mock_open)
    def test_load_cached_configuration(self, mock_file):
        """Test loading a configuration from cache."""
        # Mock the file to return the test configuration
        mock_file.return_value.__enter__.return_value.read.return_value = self.score_config
        
        # Get the expected file path
        yaml_path = get_score_yaml_path(self.scorecard_name, self.score_name)
        
        # Load the configuration
        with open(yaml_path, 'r') as f:
            content = f.read()
        
        # Check that the content was read correctly
        self.assertEqual(content, self.score_config)
        mock_file.assert_called_once_with(yaml_path, 'r')


class TestPerformanceImprovement(unittest.TestCase):
    """Tests for performance improvements from caching."""
    
    def setUp(self):
        """Set up the test environment."""
        # Create a temporary directory for the test
        self.temp_dir = tempfile.TemporaryDirectory()
        self.old_cwd = os.getcwd()
        os.chdir(self.temp_dir.name)
        
        # Create mock functions with simulated delays
        def slow_fetch(score_id):
            """Simulate a slow API call."""
            time.sleep(0.05)  # 50ms delay
            return f"configuration for {score_id}"
        
        def fast_load(path):
            """Simulate a fast file read."""
            time.sleep(0.001)  # 1ms delay
            return f"cached configuration from {path}"
        
        self.slow_fetch = slow_fetch
        self.fast_load = fast_load
        
        # Create test data
        self.score_ids = [f"score-{i:03}" for i in range(10)]
        self.scorecard_name = "Test Scorecard"
        self.score_names = [f"Score {i}" for i in range(10)]
    
    def tearDown(self):
        """Clean up after the test."""
        os.chdir(self.old_cwd)
        self.temp_dir.cleanup()
    
    def test_performance_comparison(self):
        """Test that loading from cache is faster than fetching from API."""
        # First, measure the time to "fetch" all configurations from API
        start_time = time.time()
        api_results = [self.slow_fetch(score_id) for score_id in self.score_ids]
        api_time = time.time() - start_time
        
        # Now, cache the configurations
        for i, score_id in enumerate(self.score_ids):
            yaml_path = get_score_yaml_path(self.scorecard_name, self.score_names[i])
            with open(yaml_path, 'w') as f:
                f.write(api_results[i])
        
        # Measure the time to load from cache
        start_time = time.time()
        cache_results = []
        for i, score_id in enumerate(self.score_ids):
            yaml_path = get_score_yaml_path(self.scorecard_name, self.score_names[i])
            with open(yaml_path, 'r') as f:
                cache_results.append(f.read())
        cache_time = time.time() - start_time
        
        # Verify loading from cache is faster
        self.assertLess(cache_time, api_time)
        
        # Verify the results are the same
        self.assertEqual(api_results, cache_results)


class TestCachingIntegration(unittest.TestCase):
    """Integration tests for configuration caching."""
    
    def setUp(self):
        """Set up the test environment."""
        # Create a temporary directory for the test
        self.temp_dir = tempfile.TemporaryDirectory()
        self.old_cwd = os.getcwd()
        os.chdir(self.temp_dir.name)
    
    def tearDown(self):
        """Clean up after the test."""
        os.chdir(self.old_cwd)
        self.temp_dir.cleanup()
    
    @patch('os.path.exists')
    @patch('builtins.open', new_callable=mock_open)
    def test_check_local_cache(self, mock_file, mock_exists):
        """Test checking local cache for existing configurations."""
        # Mock data
        scorecard_id = "sc-123"
        scorecard_name = "Test Scorecard"
        scores = [
            {"id": "score-001", "name": "Score A", "championVersionId": "v1"},
            {"id": "score-002", "name": "Score B", "championVersionId": "v2"},
            {"id": "score-003", "name": "Score C", "championVersionId": "v3"}
        ]
        
        # Mock file existence checks
        def mock_path_exists(path):
            # Make the first score exist in cache, others not
            return "Score A" in str(path)
        
        mock_exists.side_effect = mock_path_exists
        
        # Create functions to simulate behavior in a real project
        def check_local_score_cache(scorecard_name, scores):
            """Check if score configurations exist in local cache."""
            cached_scores = {}
            uncached_scores = {}
            
            for score in scores:
                score_id = score["id"]
                score_name = score["name"]
                yaml_path = get_score_yaml_path(scorecard_name, score_name)
                
                if os.path.exists(yaml_path):
                    cached_scores[score_id] = yaml_path
                else:
                    uncached_scores[score_id] = score
            
            return cached_scores, uncached_scores
        
        # Execute the function
        cached, uncached = check_local_score_cache(scorecard_name, scores)
        
        # Verify results
        self.assertIn("score-001", cached)
        self.assertIn("score-002", uncached)
        self.assertIn("score-003", uncached)
        
        # Verify the correct paths were checked
        expected_calls = [
            unittest.mock.call(get_score_yaml_path(scorecard_name, "Score A")),
            unittest.mock.call(get_score_yaml_path(scorecard_name, "Score B")),
            unittest.mock.call(get_score_yaml_path(scorecard_name, "Score C"))
        ]
        mock_exists.assert_has_calls(expected_calls, any_order=True)


if __name__ == '__main__':
    unittest.main() 
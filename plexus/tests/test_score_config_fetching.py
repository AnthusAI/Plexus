"""Unit tests for the score_config_fetching module."""

import unittest
from unittest.mock import MagicMock, patch
from pathlib import Path
import tempfile
import os
import sys

# Add the parent directory to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from plexus.cli.shared.score_config_fetching import fetch_and_cache_single_score


class TestScoreConfigFetching(unittest.TestCase):
    """Tests for the score_config_fetching module."""

    def setUp(self):
        """Set up test fixtures."""
        # Create a temporary directory for tests
        self.temp_dir = tempfile.TemporaryDirectory()
        
        # Sample data for tests
        self.scorecard_identifier = "test-scorecard"
        self.score_identifier = "test-score"
        self.scorecard_id = "123456789"
        self.score_id = "987654321"
        self.champion_version_id = "version-123"
        
        # Sample YAML configuration
        self.yaml_content = """
name: Test Score
key: test-score
id: 987654321
class: SimpleScore
description: A test score
threshold: 0.5
"""
        
        # Mock client
        self.mock_client = MagicMock()
        
        # Mock session for context manager pattern
        self.mock_session = MagicMock()
        self.mock_client.__enter__.return_value = self.mock_session
        
        # Sample scorecard data
        self.scorecard_data = {
            "id": self.scorecard_id,
            "name": "Test Scorecard",
            "key": "test-scorecard",
            "sections": {
                "items": [
                    {
                        "id": "section-1",
                        "name": "Test Section",
                        "scores": {
                            "items": [
                                {
                                    "id": self.score_id,
                                    "name": "Test Score",
                                    "key": "test-score",
                                    "championVersionId": self.champion_version_id
                                }
                            ]
                        }
                    }
                ]
            }
        }

    def tearDown(self):
        """Clean up test fixtures."""
        self.temp_dir.cleanup()

    @patch('plexus.cli.shared.score_config_fetching.direct_memoized_resolve_scorecard_identifier')
    @patch('plexus.cli.shared.score_config_fetching.direct_memoized_resolve_score_identifier')
    @patch('plexus.cli.shared.score_config_fetching.fetch_scorecard_structure')
    @patch('plexus.cli.shared.score_config_fetching.get_score_yaml_path')
    @patch('plexus.cli.shared.score_config_fetching.get_score_guidelines_path')
    def test_fetch_and_cache_happy_path(self, mock_get_guidelines_path, mock_get_path,
                                        mock_fetch_structure, mock_resolve_score,
                                        mock_resolve_scorecard):
        """Test the happy path for fetch_and_cache_single_score."""
        # Set up mocks
        mock_resolve_scorecard.return_value = self.scorecard_id
        mock_resolve_score.return_value = self.score_id
        mock_fetch_structure.return_value = self.scorecard_data

        # Set up temp file paths
        temp_file = Path(self.temp_dir.name) / "test-score.yaml"
        temp_guidelines_file = Path(self.temp_dir.name) / "test-score.md"
        mock_get_path.return_value = temp_file
        mock_get_guidelines_path.return_value = temp_guidelines_file
        
        # Configure mock for version query
        self.mock_session.execute.return_value = {
            "getScoreVersion": {
                "id": self.champion_version_id,
                "configuration": self.yaml_content,
                "createdAt": "2023-01-01T00:00:00Z",
                "updatedAt": "2023-01-01T00:00:00Z",
                "note": "Test version"
            }
        }
        
        # Call the function
        result, path, guidelines_path, from_cache = fetch_and_cache_single_score(
            self.mock_client,
            self.scorecard_identifier,
            self.score_identifier,
            use_cache=False,
            verbose=True
        )

        # Verify results
        self.assertEqual(path, temp_file)
        self.assertEqual(guidelines_path, temp_guidelines_file)
        self.assertFalse(from_cache)
        self.assertIsInstance(result, dict)
        self.assertEqual(result.get('name'), "Test Score")
        self.assertEqual(result.get('key'), "test-score")
        
        # Fix: Handle numeric ID by comparing as strings or accepting either type
        id_value = result.get('id')
        self.assertTrue(id_value == '987654321' or id_value == 987654321, 
                        f"ID value {id_value} doesn't match expected '987654321'")
        
        # Verify mocks were called correctly
        mock_resolve_scorecard.assert_called_once_with(self.mock_client, self.scorecard_identifier)
        mock_resolve_score.assert_called_once_with(self.mock_client, self.scorecard_id, self.score_identifier)
        mock_fetch_structure.assert_called_once_with(self.mock_client, self.scorecard_id)
        mock_get_path.assert_called_once()
        mock_get_guidelines_path.assert_called_once()

        # Verify files were written
        self.assertTrue(temp_file.exists())
        self.assertTrue(temp_guidelines_file.exists())
        
    @patch('plexus.cli.shared.score_config_fetching.direct_memoized_resolve_scorecard_identifier')
    @patch('plexus.cli.shared.score_config_fetching.direct_memoized_resolve_score_identifier')
    @patch('plexus.cli.shared.score_config_fetching.fetch_scorecard_structure')
    @patch('plexus.cli.shared.score_config_fetching.get_score_yaml_path')
    @patch('plexus.cli.shared.score_config_fetching.get_score_guidelines_path')
    def test_fetch_and_cache_from_cache(self, mock_get_guidelines_path, mock_get_path,
                                       mock_fetch_structure, mock_resolve_score,
                                       mock_resolve_scorecard):
        """Test loading from cache when use_cache=True."""
        # Set up mocks
        mock_resolve_scorecard.return_value = self.scorecard_id
        mock_resolve_score.return_value = self.score_id
        mock_fetch_structure.return_value = self.scorecard_data

        # Set up temp file paths and create cache file
        temp_file = Path(self.temp_dir.name) / "test-score.yaml"
        temp_guidelines_file = Path(self.temp_dir.name) / "test-score.md"
        mock_get_path.return_value = temp_file
        mock_get_guidelines_path.return_value = temp_guidelines_file
        
        # Write test data to cache file
        with open(temp_file, 'w') as f:
            f.write(self.yaml_content)
        
        # Call the function with use_cache=True
        result, path, guidelines_path, from_cache = fetch_and_cache_single_score(
            self.mock_client,
            self.scorecard_identifier,
            self.score_identifier,
            use_cache=True,
            verbose=True
        )

        # Verify results
        self.assertEqual(path, temp_file)
        self.assertEqual(guidelines_path, temp_guidelines_file)
        self.assertTrue(from_cache)
        self.assertIsInstance(result, dict)
        self.assertEqual(result.get('name'), "Test Score")
        
        # Verify mock session was not called (because we loaded from cache)
        self.mock_session.execute.assert_not_called()
        
    @patch('plexus.cli.shared.score_config_fetching.direct_memoized_resolve_scorecard_identifier')
    def test_scorecard_not_found(self, mock_resolve_scorecard):
        """Test handling of scorecard not found."""
        # Set up mock to return None (scorecard not found)
        mock_resolve_scorecard.return_value = None
        
        # Call the function and verify exception
        with self.assertRaises(ValueError) as context:
            fetch_and_cache_single_score(
                self.mock_client,
                self.scorecard_identifier,
                self.score_identifier
            )
        
        # Verify error message
        self.assertIn("Could not find scorecard", str(context.exception))
        

if __name__ == '__main__':
    unittest.main() 
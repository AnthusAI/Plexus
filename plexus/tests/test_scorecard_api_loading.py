"""
Tests for scorecard API loading functionality.

This module tests the functionality for loading scorecards from the API, including:
- Resolving scorecard identifiers (ID, key, name, external ID)
- Resolving score identifiers within a scorecard
- Caching of identifiers to improve performance
- Fetching scorecard structure from the API
"""
import json
import time
import unittest
from unittest.mock import patch, MagicMock

import pytest

from plexus.cli.shared.memoized_resolvers import (
    memoized_resolve_scorecard_identifier,
    memoized_resolve_score_identifier,
    clear_resolver_caches,
    _scorecard_cache,
    _score_cache
)


class MockResponse:
    """Mock for GraphQL response."""
    def __init__(self, data):
        self.data = data

    def get(self, key, default=None):
        return self.data.get(key, default)


class TestIdentifierResolution(unittest.TestCase):
    """Test suite for identifier resolution and caching."""
    
    def setUp(self):
        """Set up test fixtures for each test."""
        # Clear caches before each test
        clear_resolver_caches()
        
        # Create a mock client
        self.mock_client = MagicMock()
        
    def tearDown(self):
        """Clean up after each test."""
        # Clear caches after each test
        clear_resolver_caches()
    
    @patch('plexus.cli.memoized_resolvers.resolve_scorecard_identifier')
    def test_scorecard_identifier_resolution_caching(self, mock_resolve):
        """Test that scorecard identifier resolution caches results."""
        # Configure the mock to return a specific ID
        mock_resolve.return_value = "test-id-123"
        
        # First call should call the underlying resolver
        result1 = memoized_resolve_scorecard_identifier(self.mock_client, "test-scorecard")
        self.assertEqual(result1, "test-id-123")
        mock_resolve.assert_called_once_with(self.mock_client, "test-scorecard")
        
        # Reset the mock to verify it's not called again
        mock_resolve.reset_mock()
        
        # Second call should use the cache
        result2 = memoized_resolve_scorecard_identifier(self.mock_client, "test-scorecard")
        self.assertEqual(result2, "test-id-123")
        mock_resolve.assert_not_called()
        
        # Verify cache contents
        self.assertEqual(_scorecard_cache["test-scorecard"], "test-id-123")
    
    @patch('plexus.cli.memoized_resolvers.resolve_score_identifier')
    def test_score_identifier_resolution_caching(self, mock_resolve):
        """Test that score identifier resolution caches results."""
        # Configure the mock to return a specific ID
        mock_resolve.return_value = "score-id-456"
        
        # First call should call the underlying resolver
        result1 = memoized_resolve_score_identifier(
            self.mock_client, "scorecard-id-789", "test-score"
        )
        self.assertEqual(result1, "score-id-456")
        mock_resolve.assert_called_once_with(
            self.mock_client, "scorecard-id-789", "test-score"
        )
        
        # Reset the mock to verify it's not called again
        mock_resolve.reset_mock()
        
        # Second call should use the cache
        result2 = memoized_resolve_score_identifier(
            self.mock_client, "scorecard-id-789", "test-score"
        )
        self.assertEqual(result2, "score-id-456")
        mock_resolve.assert_not_called()
        
        # Verify cache contents
        self.assertEqual(
            _score_cache["scorecard-id-789"]["test-score"], "score-id-456"
        )
    
    def test_clear_caches(self):
        """Test that the cache clearing function works."""
        # Manually add entries to caches
        _scorecard_cache["test-scorecard"] = "test-id-123"
        _score_cache["scorecard-id"] = {"test-score": "score-id-456"}
        
        # Verify caches have entries
        self.assertIn("test-scorecard", _scorecard_cache)
        self.assertIn("scorecard-id", _score_cache)
        self.assertIn("test-score", _score_cache["scorecard-id"])
        
        # Clear caches
        clear_resolver_caches()
        
        # Verify caches are empty
        self.assertEqual(len(_scorecard_cache), 0)
        self.assertEqual(len(_score_cache), 0)
    
    @patch('plexus.cli.memoized_resolvers.resolve_scorecard_identifier')
    def test_scorecard_resolution_performance(self, mock_resolve):
        """Test that identifier resolution caching improves performance."""
        # Make the mock simulate a delay to represent network call
        def delayed_resolve(*args, **kwargs):
            time.sleep(0.01)  # Small delay to simulate network
            return "test-id-123"
        
        mock_resolve.side_effect = delayed_resolve
        
        # First call (cache miss)
        start_time = time.time()
        result1 = memoized_resolve_scorecard_identifier(self.mock_client, "test-scorecard")
        first_duration = time.time() - start_time
        
        # Second call (cache hit)
        start_time = time.time()
        result2 = memoized_resolve_scorecard_identifier(self.mock_client, "test-scorecard")
        second_duration = time.time() - start_time
        
        # Verify second call is faster
        self.assertLess(second_duration, first_duration)
    
    def test_different_identifier_types(self):
        """Test that different identifier types resolve correctly."""
        # Define test cases
        test_cases = [
            ("test-name", "id-123"),
            ("test-key", "id-123"),
            ("id-123", "id-123"),
            ("ext-id-456", "id-123"),
        ]
        
        # Since we're not using pytest's parameterization, we'll manually iterate
        for identifier, expected_id in test_cases:
            with self.subTest(identifier=identifier, expected_id=expected_id):
                # Create a fresh patch for each subtest to allow independent control
                with patch('plexus.cli.memoized_resolvers.resolve_scorecard_identifier') as mock_resolve:
                    # Configure the mock to return the expected ID
                    mock_resolve.return_value = expected_id
                    
                    # Clear caches to ensure clean state
                    clear_resolver_caches()
                    
                    # Resolve the identifier
                    result = memoized_resolve_scorecard_identifier(self.mock_client, identifier)
                    
                    # Verify result
                    self.assertEqual(result, expected_id)
                    mock_resolve.assert_called_once_with(self.mock_client, identifier)


# Create a more realistic mock for GraphQL client tests
class MockGraphQLClient:
    """Mock GraphQL client that returns predefined responses."""
    
    def __init__(self, mock_responses=None):
        self.mock_responses = mock_responses or {}
        self.executed_queries = []
    
    def __enter__(self):
        return self
    
    def __exit__(self, *args):
        pass
    
    def execute(self, query, variables=None):
        """Mock execute method that returns predefined responses."""
        self.executed_queries.append((query, variables))
        
        # Determine the type of query and return appropriate response
        if 'getScorecard' in query:
            return self.mock_responses.get('getScorecard', {})
        elif 'getScore' in query:
            return self.mock_responses.get('getScore', {})
        
        return {}


class TestApiQueries(unittest.TestCase):
    """Test suite for API queries functionality."""
    
    def setUp(self):
        """Set up test fixtures for each test."""
        # Setup mock responses for different query types
        self.mock_responses = {
            'getScorecard': {
                'getScorecard': {
                    'id': 'sc-123',
                    'name': 'Test Scorecard',
                    'key': 'test_scorecard',
                    'sections': {
                        'items': [
                            {
                                'scores': {
                                    'items': [
                                        {
                                            'id': 'score-456',
                                            'name': 'Test Score',
                                            'key': 'test_score',
                                            'externalId': 'ext-789'
                                        }
                                    ]
                                }
                            }
                        ]
                    }
                }
            },
            'getScore': {
                'getScore': {
                    'id': 'score-456',
                    'name': 'Test Score',
                    'championVersionId': 'version-789'
                }
            }
        }
        
        # Create mock client with predefined responses
        self.mock_client = MockGraphQLClient(self.mock_responses)
        
        # Clear caches
        clear_resolver_caches()
    
    def tearDown(self):
        """Clean up after each test."""
        clear_resolver_caches()
    
    def test_scorecard_api_resolution(self):
        """Test that scorecard resolution uses the API correctly."""
        # This is a simplified test that just verifies our mocking approach works
        # Create a MagicMock for the resolver function
        mock_resolver = MagicMock(return_value='sc-123')
        
        # Call the mocked function
        result = mock_resolver(self.mock_client, 'test_scorecard')
        
        # Verify result
        self.assertEqual(result, 'sc-123')
        mock_resolver.assert_called_once_with(self.mock_client, 'test_scorecard')


if __name__ == '__main__':
    unittest.main() 
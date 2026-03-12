"""
Unit tests for the metrics calculator module.
"""

import unittest
import json
import os
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, patch, MagicMock
from typing import Dict, Any

from plexus.metrics.calculator import MetricsCalculator, create_calculator_from_env


class TestMetricsCalculator(unittest.TestCase):
    """Test cases for MetricsCalculator class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.test_endpoint = "https://api.example.com/graphql"
        self.test_api_key = "test-api-key-123"
        self.test_account_id = "test-account-123"
        
        self.calculator = MetricsCalculator(self.test_endpoint, self.test_api_key)
    
    def test_init(self):
        """Test MetricsCalculator initialization."""
        assert self.calculator.graphql_endpoint == self.test_endpoint
        assert self.calculator.api_key == self.test_api_key
        assert self.calculator.cache_bucket_minutes == 5
    
    @patch('plexus.metrics.calculator.requests.post')
    def test_make_graphql_request_success(self, mock_post):
        """Test successful GraphQL request."""
        # Mock successful response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'data': {'test': 'result'}
        }
        mock_post.return_value = mock_response
        
        query = "query { test }"
        variables = {"var1": "value1"}
        
        result = self.calculator.make_graphql_request(query, variables)
        
        # Verify the request was made correctly
        mock_post.assert_called_once_with(
            self.test_endpoint,
            json={'query': query, 'variables': variables},
            headers={'x-api-key': self.test_api_key, 'Content-Type': 'application/json'},
            timeout=60
        )
        
        # Verify the result
        assert result == {'test': 'result'}
    
    @patch('plexus.metrics.calculator.requests.post')
    def test_make_graphql_request_with_errors(self, mock_post):
        """Test GraphQL request with errors."""
        # Mock response with errors
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'errors': [
                {'message': 'Test error 1'},
                {'message': 'Test error 2'}
            ]
        }
        mock_post.return_value = mock_response
        
        query = "query { test }"
        variables = {}
        
        with self.assertRaises(Exception) as context:
            self.calculator.make_graphql_request(query, variables)
        
        assert "GraphQL errors: Test error 1, Test error 2" in str(context.exception)
    
    @patch.object(MetricsCalculator, 'make_graphql_request')
    def test_count_items_in_timeframe(self, mock_request):
        """Test counting items in a timeframe."""
        # Mock GraphQL response
        mock_request.return_value = {
            'listItemByAccountIdAndCreatedAt': {
                'items': [{'id': '1'}, {'id': '2'}, {'id': '3'}],
                'nextToken': None
            }
        }
        
        start_time = datetime(2023, 1, 1, 10, 0, 0)
        end_time = datetime(2023, 1, 1, 11, 0, 0)
        
        result = self.calculator.count_items_in_timeframe(self.test_account_id, start_time, end_time)
        
        assert result == 3
        
        # Verify the GraphQL query was called with correct parameters
        mock_request.assert_called_once()
        call_args = mock_request.call_args
        assert 'accountId' in call_args[0][1]
        assert call_args[0][1]['accountId'] == self.test_account_id
    
    @patch.object(MetricsCalculator, 'make_graphql_request')
    def test_count_items_with_pagination(self, mock_request):
        """Test counting items with pagination."""
        # Mock paginated GraphQL responses
        mock_request.side_effect = [
            {
                'listItemByAccountIdAndCreatedAt': {
                    'items': [{'id': '1'}, {'id': '2'}],
                    'nextToken': 'token123'
                }
            },
            {
                'listItemByAccountIdAndCreatedAt': {
                    'items': [{'id': '3'}, {'id': '4'}, {'id': '5'}],
                    'nextToken': None
                }
            }
        ]
        
        start_time = datetime(2023, 1, 1, 10, 0, 0)
        end_time = datetime(2023, 1, 1, 11, 0, 0)
        
        result = self.calculator.count_items_in_timeframe(self.test_account_id, start_time, end_time)
        
        assert result == 5
        assert mock_request.call_count == 2
    
    @patch.object(MetricsCalculator, 'make_graphql_request')
    def test_count_score_results_in_timeframe(self, mock_request):
        """Test counting score results in a timeframe."""
        # Mock GraphQL response
        mock_request.return_value = {
            'listScoreResultByAccountIdAndUpdatedAt': {
                'items': [{'id': '1'}, {'id': '2'}],
                'nextToken': None
            }
        }
        
        start_time = datetime(2023, 1, 1, 10, 0, 0)
        end_time = datetime(2023, 1, 1, 11, 0, 0)
        
        result = self.calculator.count_score_results_in_timeframe(self.test_account_id, start_time, end_time)
        
        assert result == 2
        
        # Verify the GraphQL query was called with correct parameters
        mock_request.assert_called_once()
        call_args = mock_request.call_args
        assert 'accountId' in call_args[0][1]
        assert call_args[0][1]['accountId'] == self.test_account_id
    
    def test_generate_time_buckets(self):
        """Test time bucket generation."""
        with patch('plexus.metrics.calculator.datetime') as mock_datetime:
            # Mock current time
            mock_now = datetime(2023, 1, 1, 15, 30, 45)  # 3:30:45 PM
            mock_datetime.now.return_value = mock_now.replace(tzinfo=timezone.utc)
            mock_datetime.side_effect = lambda *args, **kwargs: datetime(*args, **kwargs)

            # Test generating 3 hour buckets
            start_time = datetime(2023, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
            end_time = datetime(2023, 1, 1, 15, 0, 0, tzinfo=timezone.utc)
            buckets = self.calculator.get_time_buckets(start_time, end_time, 60)
    
            assert len(buckets) == 3
    
            # Buckets are ordered oldest to newest.
            # Check first bucket (oldest)
            first_bucket_start, first_bucket_end = buckets[0]
            assert first_bucket_start.isoformat() == '2023-01-01T12:00:00+00:00'
            assert first_bucket_end.isoformat() == '2023-01-01T13:00:00+00:00'
    
            # Check last bucket (most recent)
            last_bucket_start, last_bucket_end = buckets[-1]
            assert last_bucket_start.isoformat() == '2023-01-01T14:00:00+00:00'
            assert last_bucket_end.isoformat() == '2023-01-01T15:00:00+00:00'
    
    @patch.object(MetricsCalculator, '_get_count_for_window')
    def test_calculate_metrics(self, mock_get_count):
        """Test the main metrics summary calculation."""
        # Mock the count so we don't make real API calls
        mock_get_count.return_value = 15

        # Call the summary function
        summary = self.calculator.get_items_summary(self.test_account_id, 24)

        # Assert that the summary has the correct shape
        assert 'itemsPerHour' in summary
        assert 'itemsAveragePerHour' in summary
        assert 'itemsPeakHourly' in summary
        assert 'itemsTotal24h' in summary
        assert 'chartData' in summary
        assert len(summary['chartData']) == 24

        # Assert that the mocked value is reflected in the summary
        assert summary['itemsTotal24h'] == 15 * 24 # 15 items per hour * 24 hours
        assert summary['itemsPeakHourly'] > 0
        assert summary['itemsAveragePerHour'] > 0


class TestCreateCalculatorFromEnv(unittest.TestCase):
    """Test cases for create_calculator_from_env function."""
    
    @patch.dict('os.environ', {'PLEXUS_API_URL': 'https://test.com/graphql', 'PLEXUS_API_KEY': 'test-key'})
    def test_create_calculator_from_env_success(self):
        """Test successful creation from environment variables."""
        with patch('plexus.metrics.calculator.load_dotenv'):
            calculator = create_calculator_from_env()
            
            assert calculator.graphql_endpoint == 'https://test.com/graphql'
            assert calculator.api_key == 'test-key'
    
    @patch.dict('os.environ', {'PLEXUS_API_KEY': 'test-key'}, clear=True)  # Only API key, no endpoint
    def test_create_calculator_from_env_missing_endpoint(self):
        """Test creation fails when endpoint is missing."""
        with patch('plexus.metrics.calculator.load_dotenv'):
            with self.assertRaises(Exception) as context:
                create_calculator_from_env()
            
            assert "GraphQL endpoint and API key environment variables must be set" in str(context.exception)
    
    @patch.dict('os.environ', {'PLEXUS_API_URL': 'https://test.com/graphql'}, clear=True)  # Only endpoint, no API key
    def test_create_calculator_from_env_missing_api_key(self):
        """Test creation fails when API key is missing."""
        with patch('plexus.metrics.calculator.load_dotenv'):
            with self.assertRaises(Exception) as context:
                create_calculator_from_env()
            
            assert "GraphQL endpoint and API key environment variables must be set" in str(context.exception)


if __name__ == '__main__':
    unittest.main() 
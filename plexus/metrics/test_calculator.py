"""
Unit tests for the metrics calculator module.
"""

import unittest
import json
import os
from datetime import datetime, timedelta
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
        assert self.calculator.cache_bucket_minutes == 15
    
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
            headers=self.calculator.headers,
            timeout=30
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
            mock_datetime.utcnow.return_value = mock_now
            
            # Test generating 3 hour buckets  
            start_time = datetime(2023, 1, 1, 12, 0, 0)
            end_time = datetime(2023, 1, 1, 15, 0, 0)
            buckets = self.calculator.get_time_buckets(start_time, end_time, 60)
            
            assert len(buckets) == 3
            
            # Check first bucket (most recent hour)
            first_bucket = buckets[0]
            assert first_bucket['bucketStart'] == '2023-01-01T14:00:00'  # 2 PM
            assert first_bucket['bucketEnd'] == '2023-01-01T15:00:00'    # 3 PM
            assert first_bucket['items'] == 0
            assert first_bucket['scoreResults'] == 0
            assert 'time' in first_bucket
    
    @patch.object(MetricsCalculator, 'count_items_in_timeframe')
    @patch.object(MetricsCalculator, 'count_score_results_in_timeframe')
    @patch.object(MetricsCalculator, 'get_time_buckets')
    def test_calculate_metrics(self, mock_buckets, mock_score_results, mock_items):
        """Test metrics calculation."""
        # Mock time buckets
        mock_buckets.return_value = [
            {'time': '2 pm', 'bucketStart': '2023-01-01T14:00:00', 'bucketEnd': '2023-01-01T15:00:00', 'items': 0, 'scoreResults': 0},
            {'time': '1 pm', 'bucketStart': '2023-01-01T13:00:00', 'bucketEnd': '2023-01-01T14:00:00', 'items': 0, 'scoreResults': 0},
            {'time': '12 pm', 'bucketStart': '2023-01-01T12:00:00', 'bucketEnd': '2023-01-01T13:00:00', 'items': 0, 'scoreResults': 0}
        ]
        
        # Mock count methods
        mock_items.side_effect = [10, 8, 6]  # Items counts for each bucket
        mock_score_results.side_effect = [5, 4, 3]  # Score results counts for each bucket
        
        result = self.calculator.get_items_summary(self.test_account_id, 3)
        
        # Verify structure
        assert 'itemsPerHour' in result
        assert 'scoreResultsPerHour' in result
        assert 'itemsAveragePerHour' in result
        assert 'scoreResultsAveragePerHour' in result
        assert 'itemsPeakHourly' in result
        assert 'scoreResultsPeakHourly' in result
        assert 'itemsTotal24h' in result
        assert 'scoreResultsTotal24h' in result
        assert 'chartData' in result
        
        # Verify calculations
        assert result['itemsPerHour'] == 10  # Current hour
        assert result['scoreResultsPerHour'] == 5  # Current hour
        assert result['itemsTotal24h'] == 24  # Sum of all buckets
        assert result['scoreResultsTotal24h'] == 12  # Sum of all buckets
        assert result['itemsPeakHourly'] == 10  # Maximum
        assert result['scoreResultsPeakHourly'] == 5  # Maximum
        assert result['itemsAveragePerHour'] == 8.0  # Average
        assert result['scoreResultsAveragePerHour'] == 4.0  # Average


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
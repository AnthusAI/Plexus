#!/usr/bin/env python3
"""
Tests for FeedbackItems data cache.
This module validates that the class can be instantiated and parameters are validated correctly.
"""

import pytest
import logging
from pydantic import ValidationError
from unittest.mock import patch, Mock

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

from plexus.data.FeedbackItems import FeedbackItems


def test_parameter_validation():
    """Test parameter validation."""
    
    # Mock the network calls to avoid actual API requests
    with patch('plexus.data.FeedbackItems.create_client') as mock_create_client, \
         patch('plexus.data.FeedbackItems.resolve_account_id_for_command') as mock_resolve_account:
        
        # Mock client and account resolution
        mock_client = Mock()
        mock_create_client.return_value = mock_client
        mock_resolve_account.return_value = 'test-account-id'
        
        # Test valid parameters
        valid_params = {
            'scorecard': 'test_scorecard',
            'score': 'test_score',
            'days': 14,
            'limit': 100
        }
        feedback_items = FeedbackItems(**valid_params)
        assert feedback_items is not None
    
    # Test invalid days (negative)
    with pytest.raises(ValidationError):
        invalid_days = {
            'scorecard': 'test_scorecard',
            'score': 'test_score',
            'days': -5,
            'limit': 100
        }
        FeedbackItems(**invalid_days)
    
    # Test invalid limit (zero)
    with pytest.raises(ValidationError):
        invalid_limit = {
            'scorecard': 'test_scorecard',
            'score': 'test_score',
            'days': 14,
            'limit': 0
        }
        FeedbackItems(**invalid_limit)


def test_cache_methods():
    """Test cache-related methods."""
    
    # Mock the network calls to avoid actual API requests
    with patch('plexus.data.FeedbackItems.create_client') as mock_create_client, \
         patch('plexus.data.FeedbackItems.resolve_account_id_for_command') as mock_resolve_account:
        
        # Mock client and account resolution
        mock_client = Mock()
        mock_create_client.return_value = mock_client
        mock_resolve_account.return_value = 'test-account-id'
        
        params = {
            'scorecard': 'test_scorecard',
            'score': 'test_score',
            'days': 14,
            'limit': 100
        }
        feedback_items = FeedbackItems(**params)
        
        # Test identifier generation with mock IDs to avoid API calls
        mock_scorecard_id = 'scorecard-123'
        mock_score_id = 'score-456'
        identifier = feedback_items._generate_cache_identifier(mock_scorecard_id, mock_score_id)
        assert identifier is not None
        assert isinstance(identifier, str)
        assert 'scorecard-123' in identifier
        assert 'score-456' in identifier
        
        # Test cache existence check (should be False for new identifier)
        exists = feedback_items._cache_exists(identifier)
        assert isinstance(exists, bool)
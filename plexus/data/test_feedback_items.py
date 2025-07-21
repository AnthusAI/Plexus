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


def test_initial_value_and_final_value_parameters():
    """Test the new initial_value and final_value parameters."""
    
    # Mock the network calls to avoid actual API requests
    with patch('plexus.data.FeedbackItems.create_client') as mock_create_client, \
         patch('plexus.data.FeedbackItems.resolve_account_id_for_command') as mock_resolve_account:
        
        # Mock client and account resolution
        mock_client = Mock()
        mock_create_client.return_value = mock_client
        mock_resolve_account.return_value = 'test-account-id'
        
        # Test with initial_value and final_value parameters
        params_with_values = {
            'scorecard': 'test_scorecard',
            'score': 'test_score',
            'days': 14,
            'initial_value': 'No',
            'final_value': 'Yes'
        }
        feedback_items = FeedbackItems(**params_with_values)
        assert feedback_items is not None
        assert feedback_items.parameters.initial_value == 'No'
        assert feedback_items.parameters.final_value == 'Yes'
        
        # Test with None values (should be allowed)
        params_none_values = {
            'scorecard': 'test_scorecard',
            'score': 'test_score',
            'days': 14,
            'initial_value': None,
            'final_value': None
        }
        feedback_items_none = FeedbackItems(**params_none_values)
        assert feedback_items_none is not None
        assert feedback_items_none.parameters.initial_value is None
        assert feedback_items_none.parameters.final_value is None


def test_case_insensitive_normalization():
    """Test case-insensitive normalization of filter values."""
    
    # Mock the network calls to avoid actual API requests
    with patch('plexus.data.FeedbackItems.create_client') as mock_create_client, \
         patch('plexus.data.FeedbackItems.resolve_account_id_for_command') as mock_resolve_account:
        
        # Mock client and account resolution
        mock_client = Mock()
        mock_create_client.return_value = mock_client
        mock_resolve_account.return_value = 'test-account-id'
        
        # Test case normalization with various cases and whitespace
        test_cases = [
            ('Yes', 'yes'),
            ('NO', 'no'),
            (' Maybe ', 'maybe'),
            ('  YES  ', 'yes'),
            ('nO', 'no')
        ]
        
        for input_value, expected_normalized in test_cases:
            params = {
                'scorecard': 'test_scorecard',
                'score': 'test_score',
                'days': 14,
                'initial_value': input_value
            }
            feedback_items = FeedbackItems(**params)
            assert feedback_items.normalized_initial_value == expected_normalized
        
        # Test _normalize_value method directly
        params = {
            'scorecard': 'test_scorecard',
            'score': 'test_score', 
            'days': 14
        }
        feedback_items = FeedbackItems(**params)
        
        # Test normalization method
        assert feedback_items._normalize_value('Yes') == 'yes'
        assert feedback_items._normalize_value('NO') == 'no'
        assert feedback_items._normalize_value(' Maybe ') == 'maybe'
        assert feedback_items._normalize_value(None) is None
        
        # Test _normalize_item_value method (should work the same)
        assert feedback_items._normalize_item_value('Yes') == 'yes'
        assert feedback_items._normalize_item_value('NO') == 'no'
        assert feedback_items._normalize_item_value(' Maybe ') == 'maybe'
        assert feedback_items._normalize_item_value(None) is None


def test_cache_identifier_with_filter_values():
    """Test cache identifier generation includes filter values."""
    
    # Mock the network calls to avoid actual API requests
    with patch('plexus.data.FeedbackItems.create_client') as mock_create_client, \
         patch('plexus.data.FeedbackItems.resolve_account_id_for_command') as mock_resolve_account:
        
        # Mock client and account resolution
        mock_client = Mock()
        mock_create_client.return_value = mock_client
        mock_resolve_account.return_value = 'test-account-id'
        
        # Test cache identifier with filter values
        params_with_filters = {
            'scorecard': 'test_scorecard',
            'score': 'test_score',
            'days': 14,
            'initial_value': 'No',
            'final_value': 'Yes'
        }
        feedback_items = FeedbackItems(**params_with_filters)
        
        mock_scorecard_id = 'scorecard-123'
        mock_score_id = 'score-456'
        identifier_with_filters = feedback_items._generate_cache_identifier(mock_scorecard_id, mock_score_id)
        
        # Test cache identifier without filter values
        params_no_filters = {
            'scorecard': 'test_scorecard',
            'score': 'test_score',
            'days': 14
        }
        feedback_items_no_filters = FeedbackItems(**params_no_filters)
        identifier_no_filters = feedback_items_no_filters._generate_cache_identifier(mock_scorecard_id, mock_score_id)
        
        # Identifiers should be different when filters are applied
        assert identifier_with_filters != identifier_no_filters
        
        # Test that case variations produce the same cache identifier
        params_upper = {
            'scorecard': 'test_scorecard',
            'score': 'test_score',
            'days': 14,
            'initial_value': 'NO',  # Different case
            'final_value': 'YES'    # Different case
        }
        feedback_items_upper = FeedbackItems(**params_upper)
        identifier_upper = feedback_items_upper._generate_cache_identifier(mock_scorecard_id, mock_score_id)
        
        # Should be the same as lowercase version due to normalization
        assert identifier_with_filters == identifier_upper


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


def test_parameter_defaults():
    """Test that new parameters have correct defaults."""
    
    # Mock the network calls to avoid actual API requests
    with patch('plexus.data.FeedbackItems.create_client') as mock_create_client, \
         patch('plexus.data.FeedbackItems.resolve_account_id_for_command') as mock_resolve_account:
        
        # Mock client and account resolution
        mock_client = Mock()
        mock_create_client.return_value = mock_client
        mock_resolve_account.return_value = 'test-account-id'
        
        # Test minimal parameters (new fields should default to None)
        minimal_params = {
            'scorecard': 'test_scorecard',
            'score': 'test_score',
            'days': 14
        }
        feedback_items = FeedbackItems(**minimal_params)
        assert feedback_items.parameters.initial_value is None
        assert feedback_items.parameters.final_value is None
        assert feedback_items.normalized_initial_value is None
        assert feedback_items.normalized_final_value is None
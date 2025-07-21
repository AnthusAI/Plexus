#!/usr/bin/env python3
"""
Tests for FeedbackItems data cache.
This module validates that the class can be instantiated and parameters are validated correctly.
"""

import pytest
import logging
import pandas as pd
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


def test_create_dataset_rows_structure():
    """Test that _create_dataset_rows creates the correct column structure."""
    
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
        
        # Create mock feedback items
        mock_feedback_items = []
        
        # Test with empty list
        df_empty = feedback_items._create_dataset_rows(mock_feedback_items, "Test Score")
        
        # Verify empty DataFrame has correct columns
        expected_columns = [
            'content_id',
            'feedback_item_id', 
            'IDs',
            'metadata',
            'text',
            'Test Score',
            'Test Score comment',
            'Test Score edit comment'
        ]
        assert list(df_empty.columns) == expected_columns
        assert len(df_empty) == 0


def test_create_dataset_rows_with_data():
    """Test that _create_dataset_rows creates correct data with actual feedback items."""
    
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
        
        # Create mock feedback item
        mock_item = Mock()
        mock_item.id = 'item-123'
        mock_item.text = 'This is a test transcript'
        mock_item.externalId = 'ext-456'
        mock_item.createdAt = '2024-01-01T00:00:00Z'
        mock_item.updatedAt = '2024-01-01T00:00:00Z'
        mock_item.metadata = None
        mock_item.identifiers = None
        
        mock_feedback_item = Mock()
        mock_feedback_item.id = 'feedback-789'
        mock_feedback_item.itemId = 'item-123'
        mock_feedback_item.item = mock_item
        mock_feedback_item.finalAnswerValue = 'Yes'
        mock_feedback_item.editCommentValue = 'This is an edit comment'
        mock_feedback_item.initialCommentValue = 'Initial comment'
        mock_feedback_item.finalCommentValue = 'Final comment'
        mock_feedback_item.scorecardId = 'scorecard-123'
        mock_feedback_item.scoreId = 'score-456'
        mock_feedback_item.accountId = 'account-789'
        mock_feedback_item.createdAt = '2024-01-01T00:00:00Z'
        mock_feedback_item.updatedAt = '2024-01-01T00:00:00Z'
        mock_feedback_item.editedAt = '2024-01-01T01:00:00Z'
        mock_feedback_item.editorName = 'Test Editor'
        mock_feedback_item.isAgreement = False
        mock_feedback_item.cacheKey = 'cache-key-123'
        
        mock_feedback_items = [mock_feedback_item]
        
        # Create dataset
        df = feedback_items._create_dataset_rows(mock_feedback_items, "Test Score")
        
        # Verify DataFrame structure
        expected_columns = [
            'content_id',
            'feedback_item_id',
            'IDs',
            'metadata', 
            'text',
            'Test Score',
            'Test Score comment',
            'Test Score edit comment'
        ]
        assert list(df.columns) == expected_columns
        assert len(df) == 1
        
        # Verify data content
        row = df.iloc[0]
        assert row['content_id'] == 'item-123'
        assert row['feedback_item_id'] == 'feedback-789'
        assert row['text'] == 'This is a test transcript'
        assert row['Test Score'] == 'Yes'
        assert row['Test Score edit comment'] == 'This is an edit comment'
        
        # Verify metadata is JSON string
        import json
        metadata = json.loads(row['metadata'])
        assert metadata['feedback_item_id'] == 'feedback-789'
        assert metadata['scorecard_id'] == 'scorecard-123'
        assert metadata['score_id'] == 'score-456'
        
        # Verify IDs is JSON string
        ids = json.loads(row['IDs'])
        assert isinstance(ids, list)


def test_create_dataset_rows_comment_logic():
    """Test the comment logic in _create_dataset_rows."""
    
    with patch('plexus.data.FeedbackItems.create_client') as mock_create_client, \
         patch('plexus.data.FeedbackItems.resolve_account_id_for_command') as mock_resolve_account:
        
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
        
        # Test case 1: Edit comment is 'agree' with no final comment
        mock_item1 = Mock()
        mock_item1.id = 'item-1'
        mock_item1.text = 'Test text 1'
        mock_item1.externalId = 'ext-1'
        mock_item1.createdAt = '2024-01-01T00:00:00Z'
        mock_item1.updatedAt = '2024-01-01T00:00:00Z'
        mock_item1.metadata = None
        mock_item1.identifiers = None
        
        mock_feedback_item1 = Mock()
        mock_feedback_item1.id = 'feedback-1'
        mock_feedback_item1.itemId = 'item-1'
        mock_feedback_item1.item = mock_item1
        mock_feedback_item1.finalAnswerValue = 'Yes'
        mock_feedback_item1.editCommentValue = 'agree'
        mock_feedback_item1.initialCommentValue = 'Original explanation'
        mock_feedback_item1.finalCommentValue = ''
        # Add required attributes
        for attr in ['scorecardId', 'scoreId', 'accountId', 'createdAt', 'updatedAt', 'editedAt', 'editorName', 'isAgreement', 'cacheKey']:
            setattr(mock_feedback_item1, attr, f'test-{attr}')
        
        df1 = feedback_items._create_dataset_rows([mock_feedback_item1], "Test Score")
        row1 = df1.iloc[0]
        
        # Should use initial comment when edit is 'agree' and no final comment
        assert row1['Test Score comment'] == 'Original explanation'
        assert row1['Test Score edit comment'] == 'agree'
        
        # Test case 2: Edit comment has meaningful content
        mock_item2 = Mock()
        mock_item2.id = 'item-2'
        mock_item2.text = 'Test text 2'
        mock_item2.externalId = 'ext-2'
        mock_item2.createdAt = '2024-01-01T00:00:00Z'
        mock_item2.updatedAt = '2024-01-01T00:00:00Z'
        mock_item2.metadata = None
        mock_item2.identifiers = None
        
        mock_feedback_item2 = Mock()
        mock_feedback_item2.id = 'feedback-2'
        mock_feedback_item2.itemId = 'item-2'
        mock_feedback_item2.item = mock_item2
        mock_feedback_item2.finalAnswerValue = 'No'
        mock_feedback_item2.editCommentValue = 'Actually this should be No'
        mock_feedback_item2.initialCommentValue = 'Original explanation'
        mock_feedback_item2.finalCommentValue = 'Final explanation'
        # Add required attributes
        for attr in ['scorecardId', 'scoreId', 'accountId', 'createdAt', 'updatedAt', 'editedAt', 'editorName', 'isAgreement', 'cacheKey']:
            setattr(mock_feedback_item2, attr, f'test-{attr}')
        
        df2 = feedback_items._create_dataset_rows([mock_feedback_item2], "Test Score")
        row2 = df2.iloc[0]
        
        # Should use edit comment when it has meaningful content
        assert row2['Test Score comment'] == 'Actually this should be No'
        assert row2['Test Score edit comment'] == 'Actually this should be No'


def test_create_dataset_rows_handles_missing_edit_comment():
    """Test that _create_dataset_rows handles missing edit comments correctly."""
    
    with patch('plexus.data.FeedbackItems.create_client') as mock_create_client, \
         patch('plexus.data.FeedbackItems.resolve_account_id_for_command') as mock_resolve_account:
        
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
        
        # Create mock feedback item with no edit comment
        mock_item = Mock()
        mock_item.id = 'item-123'
        mock_item.text = 'Test text'
        mock_item.externalId = 'ext-123'
        mock_item.createdAt = '2024-01-01T00:00:00Z'
        mock_item.updatedAt = '2024-01-01T00:00:00Z'
        mock_item.metadata = None
        mock_item.identifiers = None
        
        mock_feedback_item = Mock()
        mock_feedback_item.id = 'feedback-123'
        mock_feedback_item.itemId = 'item-123'
        mock_feedback_item.item = mock_item
        mock_feedback_item.finalAnswerValue = 'Yes'
        mock_feedback_item.editCommentValue = None  # No edit comment
        mock_feedback_item.initialCommentValue = 'Initial comment'
        mock_feedback_item.finalCommentValue = 'Final comment'
        # Add required attributes
        for attr in ['scorecardId', 'scoreId', 'accountId', 'createdAt', 'updatedAt', 'editedAt', 'editorName', 'isAgreement', 'cacheKey']:
            setattr(mock_feedback_item, attr, f'test-{attr}')
        
        df = feedback_items._create_dataset_rows([mock_feedback_item], "Test Score")
        row = df.iloc[0]
        
        # Edit comment column should be empty string when None
        assert row['Test Score edit comment'] == ''
        # Should fall back to final comment when no edit comment
        assert row['Test Score comment'] == 'Final comment'
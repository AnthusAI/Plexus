#!/usr/bin/env python3
"""
Unit tests for DataCache upsert_item_for_dataset_row functionality.

Tests the centralized Item creation logic that was added to DataCache
to reduce code duplication across subclasses like FeedbackItems.
"""

import pytest
import json
import uuid
from unittest.mock import Mock, patch
from plexus.data.DataCache import DataCache


class MockDataCache(DataCache):
    """Mock DataCache implementation for testing the upsert functionality."""
    
    def load_dataframe(self, fresh=False):
        """Mock implementation of abstract method."""
        import pandas as pd
        return pd.DataFrame()


class TestDataCacheUpsertFunctionality:
    """Test DataCache upsert_item_for_dataset_row method."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.account_id = str(uuid.uuid4())
        self.external_id = "test-item-123"
        self.item_uuid = str(uuid.uuid4())
        self.score_id = str(uuid.uuid4())
        
        # Mock dashboard client
        self.mock_client = Mock()
        
        # Mock identifiers dict
        self.identifiers_dict = {
            'report_id': 'report_12345',
            'session_id': 'session_67890',
            'form_id': 'form_555'
        }
        
        # Create DataCache instance
        self.data_cache = MockDataCache()

    def test_upsert_with_dict_item_data(self):
        """Test upsert with dictionary item data."""
        item_data = {
            'id': self.external_id,
            'description': 'Test item description',
            'text': 'This is test text content',
            'metadata': {'source': 'test', 'priority': 'high'}
        }
        
        # Mock Item.upsert_by_identifiers
        with patch('plexus.dashboard.api.models.item.Item.upsert_by_identifiers') as mock_upsert:
            mock_upsert.return_value = (self.item_uuid, True, None)
            
            result = self.data_cache.upsert_item_for_dataset_row(
                dashboard_client=self.mock_client,
                account_id=self.account_id,
                item_data=item_data,
                identifiers_dict=self.identifiers_dict,
                score_id=self.score_id
            )
            
            # Verify return value
            item_id, was_created, error_msg = result
            assert item_id == self.item_uuid
            assert was_created is True
            assert error_msg is None
            
            # Verify Item.upsert_by_identifiers was called correctly
            mock_upsert.assert_called_once_with(
                client=self.mock_client,
                account_id=self.account_id,
                identifiers=self.identifiers_dict,
                external_id=self.external_id,
                description='Test item description',
                text='This is test text content',
                metadata={'source': 'test', 'priority': 'high'},
                is_evaluation=False,
                score_id=self.score_id,
                debug=True
            )

    def test_upsert_with_object_item_data(self):
        """Test upsert with object-style item data."""
        # Mock item data object
        item_data = Mock()
        item_data.id = self.external_id
        item_data.description = 'Object item description'
        item_data.text = 'Object text content'
        item_data.metadata = {'type': 'object_test'}
        
        with patch('plexus.dashboard.api.models.item.Item.upsert_by_identifiers') as mock_upsert:
            mock_upsert.return_value = (self.item_uuid, False, None)  # Item was updated, not created
            
            result = self.data_cache.upsert_item_for_dataset_row(
                dashboard_client=self.mock_client,
                account_id=self.account_id,
                item_data=item_data,
                identifiers_dict=self.identifiers_dict
            )
            
            # Verify return value
            item_id, was_created, error_msg = result
            assert item_id == self.item_uuid
            assert was_created is False
            assert error_msg is None
            
            # Verify correct parameters were extracted from object
            mock_upsert.assert_called_once_with(
                client=self.mock_client,
                account_id=self.account_id,
                identifiers=self.identifiers_dict,
                external_id=self.external_id,
                description='Object item description',
                text='Object text content',
                metadata={'type': 'object_test'},
                is_evaluation=False,
                score_id=None,  # No score_id provided
                debug=True
            )

    def test_upsert_with_external_id_override(self):
        """Test that explicit external_id parameter overrides item_data.id."""
        override_external_id = "override-123"
        item_data = {'id': 'original-456', 'description': 'Test item'}
        
        with patch('plexus.dashboard.api.models.item.Item.upsert_by_identifiers') as mock_upsert:
            mock_upsert.return_value = (self.item_uuid, True, None)
            
            self.data_cache.upsert_item_for_dataset_row(
                dashboard_client=self.mock_client,
                account_id=self.account_id,
                item_data=item_data,
                identifiers_dict=self.identifiers_dict,
                external_id=override_external_id
            )
            
            # Should use override external_id, not the one from item_data
            mock_upsert.assert_called_once()
            call_args = mock_upsert.call_args[1]  # Get keyword arguments
            assert call_args['external_id'] == override_external_id

    def test_upsert_with_json_string_metadata(self):
        """Test handling of JSON string metadata conversion."""
        metadata_dict = {'key1': 'value1', 'key2': 42, 'nested': {'key3': 'value3'}}
        metadata_json = json.dumps(metadata_dict)
        
        item_data = {
            'id': self.external_id,
            'description': 'JSON metadata test',
            'text': 'Test content',
            'metadata': metadata_json  # JSON string
        }
        
        with patch('plexus.dashboard.api.models.item.Item.upsert_by_identifiers') as mock_upsert:
            mock_upsert.return_value = (self.item_uuid, True, None)
            
            self.data_cache.upsert_item_for_dataset_row(
                dashboard_client=self.mock_client,
                account_id=self.account_id,
                item_data=item_data,
                identifiers_dict=self.identifiers_dict
            )
            
            # Should convert JSON string back to dict
            call_args = mock_upsert.call_args[1]
            assert call_args['metadata'] == metadata_dict
            assert isinstance(call_args['metadata'], dict)

    def test_upsert_with_invalid_json_metadata(self):
        """Test handling of invalid JSON string metadata."""
        invalid_json = "{'invalid': json}"  # Single quotes, not valid JSON
        
        item_data = {
            'id': self.external_id,
            'description': 'Invalid JSON test',
            'metadata': invalid_json
        }
        
        with patch('plexus.dashboard.api.models.item.Item.upsert_by_identifiers') as mock_upsert:
            mock_upsert.return_value = (self.item_uuid, True, None)
            
            self.data_cache.upsert_item_for_dataset_row(
                dashboard_client=self.mock_client,
                account_id=self.account_id,
                item_data=item_data,
                identifiers_dict=self.identifiers_dict
            )
            
            # Should leave invalid JSON as string
            call_args = mock_upsert.call_args[1]
            assert call_args['metadata'] == invalid_json
            assert isinstance(call_args['metadata'], str)

    def test_upsert_with_minimal_item_data(self):
        """Test upsert with minimal item data (only external_id)."""
        item_data = {}  # Empty dict
        
        with patch('plexus.dashboard.api.models.item.Item.upsert_by_identifiers') as mock_upsert:
            mock_upsert.return_value = (self.item_uuid, True, None)
            
            self.data_cache.upsert_item_for_dataset_row(
                dashboard_client=self.mock_client,
                account_id=self.account_id,
                item_data=item_data,
                identifiers_dict=self.identifiers_dict,
                external_id=self.external_id  # Provided explicitly
            )
            
            call_args = mock_upsert.call_args[1]
            assert call_args['external_id'] == self.external_id
            assert call_args['description'] == f"Dataset Item - {self.external_id}"
            assert call_args['text'] == ""
            assert call_args['metadata'] is None

    def test_upsert_with_alternative_id_fields(self):
        """Test extraction of external_id from alternative fields."""
        # Test with externalId field
        item_data_external_id = {'externalId': 'ext-123', 'description': 'External ID test'}
        
        with patch('plexus.dashboard.api.models.item.Item.upsert_by_identifiers') as mock_upsert:
            mock_upsert.return_value = (self.item_uuid, True, None)
            
            self.data_cache.upsert_item_for_dataset_row(
                dashboard_client=self.mock_client,
                account_id=self.account_id,
                item_data=item_data_external_id,
                identifiers_dict=self.identifiers_dict
            )
            
            call_args = mock_upsert.call_args[1]
            assert call_args['external_id'] == 'ext-123'

        # Test with object having externalId attribute
        mock_upsert.reset_mock()
        item_object = Mock()
        item_object.externalId = 'obj-ext-456'
        del item_object.id  # Make sure id attribute doesn't exist
        
        self.data_cache.upsert_item_for_dataset_row(
            dashboard_client=self.mock_client,
            account_id=self.account_id,
            item_data=item_object,
            identifiers_dict=self.identifiers_dict
        )
        
        call_args = mock_upsert.call_args[1]
        assert call_args['external_id'] == 'obj-ext-456'

    def test_upsert_error_handling(self):
        """Test error handling when Item.upsert_by_identifiers fails."""
        item_data = {'id': self.external_id, 'description': 'Error test'}
        
        with patch('plexus.dashboard.api.models.item.Item.upsert_by_identifiers') as mock_upsert:
            mock_upsert.side_effect = Exception("Database connection failed")
            
            result = self.data_cache.upsert_item_for_dataset_row(
                dashboard_client=self.mock_client,
                account_id=self.account_id,
                item_data=item_data,
                identifiers_dict=self.identifiers_dict
            )
            
            item_id, was_created, error_msg = result
            assert item_id is None
            assert was_created is False
            assert "Failed to upsert item: Database connection failed" in error_msg

    def test_upsert_with_score_association(self):
        """Test that score_id is properly passed for score association."""
        item_data = {'id': self.external_id, 'description': 'Score association test'}
        
        with patch('plexus.dashboard.api.models.item.Item.upsert_by_identifiers') as mock_upsert:
            mock_upsert.return_value = (self.item_uuid, True, None)
            
            self.data_cache.upsert_item_for_dataset_row(
                dashboard_client=self.mock_client,
                account_id=self.account_id,
                item_data=item_data,
                identifiers_dict=self.identifiers_dict,
                score_id=self.score_id
            )
            
            call_args = mock_upsert.call_args[1]
            assert call_args['score_id'] == self.score_id
            assert call_args['is_evaluation'] is False  # Dataset items are not evaluation items

    def test_upsert_preserves_is_evaluation_false(self):
        """Test that is_evaluation is always False for dataset items."""
        item_data = {'id': self.external_id}
        
        with patch('plexus.dashboard.api.models.item.Item.upsert_by_identifiers') as mock_upsert:
            mock_upsert.return_value = (self.item_uuid, True, None)
            
            self.data_cache.upsert_item_for_dataset_row(
                dashboard_client=self.mock_client,
                account_id=self.account_id,
                item_data=item_data,
                identifiers_dict=self.identifiers_dict
            )
            
            call_args = mock_upsert.call_args[1]
            # Dataset items should never be marked as evaluation items
            assert call_args['is_evaluation'] is False

    def test_upsert_debug_flag_enabled(self):
        """Test that debug flag is always enabled."""
        item_data = {'id': self.external_id}
        
        with patch('plexus.dashboard.api.models.item.Item.upsert_by_identifiers') as mock_upsert:
            mock_upsert.return_value = (self.item_uuid, True, None)
            
            self.data_cache.upsert_item_for_dataset_row(
                dashboard_client=self.mock_client,
                account_id=self.account_id,
                item_data=item_data,
                identifiers_dict=self.identifiers_dict
            )
            
            call_args = mock_upsert.call_args[1]
            # Debug should always be enabled for dataset item creation
            assert call_args['debug'] is True

    def test_upsert_identifiers_dict_passed_correctly(self):
        """Test that identifiers_dict is passed correctly to Item.upsert_by_identifiers."""
        item_data = {'id': self.external_id}
        complex_identifiers = {
            'report_id': 'rpt_123456',
            'session_id': 'sess_abcdef',
            'form_id': 'form_999',
            'media_id': 'media_xyz789',
            'content_id': 'content_555'
        }
        
        with patch('plexus.dashboard.api.models.item.Item.upsert_by_identifiers') as mock_upsert:
            mock_upsert.return_value = (self.item_uuid, True, None)
            
            self.data_cache.upsert_item_for_dataset_row(
                dashboard_client=self.mock_client,
                account_id=self.account_id,
                item_data=item_data,
                identifiers_dict=complex_identifiers
            )
            
            call_args = mock_upsert.call_args[1]
            assert call_args['identifiers'] == complex_identifiers
            # Should be the exact same object reference
            assert call_args['identifiers'] is complex_identifiers


if __name__ == '__main__':
    pytest.main([__file__])
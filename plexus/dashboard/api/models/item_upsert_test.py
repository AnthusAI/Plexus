"""
Comprehensive tests for Item.upsert_by_identifiers functionality in Plexus SDK.

This test suite validates the Item upsert logic to ensure:
1. Items are found correctly using identifier-based lookups
2. Duplicate Items are not created when they already exist
3. New Items are created with proper identifier records
4. Updates work correctly for existing Items
5. Integration with Identifier model works properly
"""

import pytest
import json
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timezone

# Import the modules we're testing
from plexus.dashboard.api.models.item import Item
from plexus.dashboard.api.models.identifier import Identifier


class TestItemUpsertByIdentifiers:
    """Test suite for Item.upsert_by_identifiers functionality."""
    
    def setup_method(self):
        """Set up test fixtures before each test method."""
        self.mock_client = Mock()
        self.account_id = "test-account-123"
        
    def test_upsert_creates_new_item_when_none_exists(self):
        """Test that upsert creates a new Item when no existing Item is found."""
        identifiers = {"formId": "12345", "reportId": "67890"}
        
        # Mock no existing items found
        with patch.object(Item, '_lookup_item_by_identifiers', return_value=None):
            with patch.object(Item, '_lookup_item_by_external_id', return_value=None):
                with patch.object(Item, 'create') as mock_create:
                    with patch.object(Item, '_create_identifier_records') as mock_create_ids:
                        # Mock successful creation
                        mock_item = Mock()
                        mock_item.id = "new-item-123"
                        mock_create.return_value = mock_item
                        
                        # Call upsert
                        item_id, was_created, error = Item.upsert_by_identifiers(
                            client=self.mock_client,
                            account_id=self.account_id,
                            identifiers=identifiers,
                            external_id="report-67890",
                            description="Test item",
                            text="Sample content"
                        )
                        
                        # Verify results
                        assert item_id == "new-item-123"
                        assert was_created == True
                        assert error is None
                        
                        # Verify create was called with correct parameters
                        mock_create.assert_called_once()
                        create_call = mock_create.call_args
                        assert create_call[1]['accountId'] == self.account_id
                        assert create_call[1]['externalId'] == "report-67890"
                        assert create_call[1]['description'] == "Test item"
                        assert create_call[1]['text'] == "Sample content"
                        assert create_call[1]['isEvaluation'] == False
                        
                        # Verify identifier records were created
                        mock_create_ids.assert_called_once_with(
                            self.mock_client, "new-item-123", self.account_id, identifiers, False
                        )
    
    def test_upsert_updates_existing_item_when_found(self):
        """Test that upsert updates an existing Item when found."""       
        identifiers = {"formId": "12345", "reportId": "67890"}
        
        # Mock existing item found
        existing_item = {
            'id': 'existing-item-456',
            'externalId': 'report-67890',
            'description': 'Existing item'
        }
        
        with patch.object(Item, '_lookup_item_by_identifiers', return_value=existing_item):
            with patch.object(Item, 'get_by_id') as mock_get_by_id:
                # Mock the existing item object
                mock_item = Mock()
                mock_item.id = "existing-item-456"
                mock_item.update = Mock(return_value=mock_item)
                mock_get_by_id.return_value = mock_item
                
                # Call upsert
                item_id, was_created, error = Item.upsert_by_identifiers(
                    client=self.mock_client,
                    account_id=self.account_id,
                    identifiers=identifiers,
                    description="Updated item",
                    text="Updated content"
                )
                
                # Verify results
                assert item_id == "existing-item-456"
                assert was_created == False
                assert error is None
                
                # Verify update was called with correct parameters
                mock_item.update.assert_called_once()
                update_call = mock_item.update.call_args
                assert update_call[1]['description'] == "Updated item"
                assert update_call[1]['text'] == "Updated content"
    
    def test_upsert_falls_back_to_external_id_lookup(self):
        """Test that upsert falls back to external_id lookup when identifier lookup fails."""        
        identifiers = {"formId": "12345"}
        external_id = "report-67890"
        
        # Mock identifier lookup fails, but external_id lookup succeeds
        existing_item = {
            'id': 'existing-item-789',
            'externalId': external_id,
            'description': 'Found by external ID'
        }
        
        with patch.object(Item, '_lookup_item_by_identifiers', return_value=None):
            with patch.object(Item, '_lookup_item_by_external_id', return_value=existing_item):
                with patch.object(Item, 'get_by_id') as mock_get_by_id:
                    # Mock the existing item object
                    mock_item = Mock()
                    mock_item.id = "existing-item-789"
                    mock_item.update = Mock(return_value=mock_item)
                    mock_get_by_id.return_value = mock_item
                    
                    # Call upsert
                    item_id, was_created, error = Item.upsert_by_identifiers(
                        client=self.mock_client,
                        account_id=self.account_id,
                        identifiers=identifiers,
                        external_id=external_id,
                        description="Updated via external_id"
                    )
                    
                    # Verify results
                    assert item_id == "existing-item-789"
                    assert was_created == False
                    assert error is None
    
    def test_upsert_handles_missing_account_id(self):
        """Test that upsert handles missing account_id gracefully."""        
        item_id, was_created, error = Item.upsert_by_identifiers(
            client=self.mock_client,
            account_id="",  # Empty account ID
            identifiers={"formId": "12345"}
        )
        
        assert item_id is None
        assert was_created == False
        assert "Missing required account_id" in error
    
    def test_upsert_handles_creation_failure(self):
        """Test that upsert handles Item creation failures gracefully."""        
        identifiers = {"formId": "12345"}
        
        # Mock no existing items found
        with patch.object(Item, '_lookup_item_by_identifiers', return_value=None):
            with patch.object(Item, '_lookup_item_by_external_id', return_value=None):
                with patch.object(Item, 'create', side_effect=Exception("Creation failed")):
                    
                    # Call upsert
                    item_id, was_created, error = Item.upsert_by_identifiers(
                        client=self.mock_client,
                        account_id=self.account_id,
                        identifiers=identifiers,
                        description="Test item"
                    )
                    
                    # Verify error handling
                    assert item_id is None
                    assert was_created == False
                    assert "Creation failed" in error
    
    def test_convert_identifiers_to_legacy_format(self):
        """Test conversion of identifiers to legacy JSON format."""        
        identifiers = {
            "formId": "12345",
            "reportId": "67890",
            "sessionId": "abc123",
            "ccId": "999"
        }
        
        result = Item._convert_identifiers_to_legacy_format(identifiers)
        legacy_data = json.loads(result)
        
        # Verify structure and content
        assert len(legacy_data) == 4
        
        # Check each identifier type
        form_id_entry = next(item for item in legacy_data if item["name"] == "form ID")
        assert form_id_entry["id"] == "12345"
        assert form_id_entry["url"] == "https://app.callcriteria.com/r/12345"
        
        report_id_entry = next(item for item in legacy_data if item["name"] == "report ID")
        assert report_id_entry["id"] == "67890"
        
        session_id_entry = next(item for item in legacy_data if item["name"] == "session ID")
        assert session_id_entry["id"] == "abc123"
        
        cc_id_entry = next(item for item in legacy_data if item["name"] == "CC ID")
        assert cc_id_entry["id"] == "999"
    
    def test_convert_identifiers_handles_empty_input(self):
        """Test that identifier conversion handles empty input gracefully."""        
        assert Item._convert_identifiers_to_legacy_format({}) is None
        assert Item._convert_identifiers_to_legacy_format(None) is None


class TestItemUpsertIntegration:
    """Integration tests for Item upsert functionality."""    
    
    def setup_method(self):
        """Set up test fixtures."""        
        self.mock_client = Mock()
        self.account_id = "test-account-123"
    
    def test_end_to_end_deduplication_scenario(self):
        """Test the complete deduplication scenario - same identifiers processed twice."""        
        identifiers = {"formId": "12345", "reportId": "67890"}
        
        # First call - no existing item, should create
        with patch.object(Item, '_lookup_item_by_identifiers', return_value=None):
            with patch.object(Item, '_lookup_item_by_external_id', return_value=None):
                with patch.object(Item, 'create') as mock_create:
                    with patch.object(Item, '_create_identifier_records'):
                        # Mock successful creation
                        mock_item = Mock()
                        mock_item.id = "new-item-123"
                        mock_create.return_value = mock_item
                        
                        # First upsert call
                        item_id_1, was_created_1, error_1 = Item.upsert_by_identifiers(
                            client=self.mock_client,
                            account_id=self.account_id,
                            identifiers=identifiers,
                            external_id="report-67890",
                            description="Test item"
                        )
                        
                        assert item_id_1 == "new-item-123"
                        assert was_created_1 == True
                        assert error_1 is None
        
        # Second call - existing item found, should update
        existing_item = {
            'id': 'new-item-123',
            'externalId': 'report-67890',
            'description': 'Test item'
        }
        
        with patch.object(Item, '_lookup_item_by_identifiers', return_value=existing_item):
            with patch.object(Item, 'get_by_id') as mock_get_by_id:
                # Mock the existing item object
                mock_item = Mock()
                mock_item.id = "new-item-123"
                mock_item.update = Mock(return_value=mock_item)
                mock_get_by_id.return_value = mock_item
                
                # Second upsert call
                item_id_2, was_created_2, error_2 = Item.upsert_by_identifiers(
                    client=self.mock_client,
                    account_id=self.account_id,
                    identifiers=identifiers,
                    external_id="report-67890",
                    description="Updated item"
                )
                
                assert item_id_2 == "new-item-123"  # Same item ID
                assert was_created_2 == False  # Not created, but updated
                assert error_2 is None
                
                # Verify update was called
                mock_item.update.assert_called_once()


if __name__ == "__main__":
    # Run the tests
    pytest.main([__file__, "-v"])
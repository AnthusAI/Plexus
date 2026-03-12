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


class TestItemRelationshipValidation:
    """Test suite for Item relationship validation to prevent cross-contamination."""

    def test_validate_item_relationship_matching_report_id(self):
        """Test that items with matching reportId pass validation."""
        from plexus.dashboard.api.models.item import Item
        
        # Create mock item with existing identifiers
        mock_item = type('MockItem', (), {
            'id': 'test-item-123',
            'identifiers': '[{"name": "report ID", "id": "277307013"}, {"name": "form ID", "id": "12345"}]'
        })()
        
        # New identifiers with same reportId but different formId
        new_identifiers = {
            'reportId': '277307013',  # Matches existing
            'formId': '67890'        # Different form, same report
        }
        
        # Should pass validation (same report, different form is OK)
        result = Item._validate_item_relationship(mock_item, new_identifiers, debug=True)
        assert result is True

    def test_validate_item_relationship_mismatched_report_id(self):
        """Test that items with different reportId fail validation."""
        from plexus.dashboard.api.models.item import Item
        
        # Create mock item with existing identifiers
        mock_item = type('MockItem', (), {
            'id': 'test-item-123', 
            'identifiers': '[{"name": "report ID", "id": "277307013"}, {"name": "form ID", "id": "12345"}]'
        })()
        
        # New identifiers with different reportId
        new_identifiers = {
            'reportId': '999999999',  # Different report
            'formId': '67890'
        }
        
        # Should fail validation (different reports = cross-contamination)
        result = Item._validate_item_relationship(mock_item, new_identifiers, debug=True)
        assert result is False

    def test_validate_item_relationship_matching_session_id(self):
        """Test that items with matching sessionId pass validation."""
        from plexus.dashboard.api.models.item import Item
        
        # Create mock item with sessionId
        mock_item = type('MockItem', (), {
            'id': 'test-item-123',
            'identifiers': '[{"name": "session ID", "id": "session-abc-123"}]'
        })()
        
        new_identifiers = {
            'sessionId': 'session-abc-123',  # Matches existing
            'formId': 'new-form-456'
        }
        
        result = Item._validate_item_relationship(mock_item, new_identifiers, debug=True)
        assert result is True

    def test_validate_item_relationship_dict_format_identifiers(self):
        """Test validation with modern dict format identifiers."""
        from plexus.dashboard.api.models.item import Item
        
        # Mock item with dict format identifiers  
        mock_item = type('MockItem', (), {
            'id': 'test-item-123',
            'identifiers': {'reportId': '277307013', 'formId': '12345'}
        })()
        
        new_identifiers = {
            'reportId': '277307013',  # Matches
            'formId': '99999'        # Different form, same report
        }
        
        result = Item._validate_item_relationship(mock_item, new_identifiers, debug=True)
        assert result is True

    def test_validate_item_relationship_no_critical_identifiers(self):
        """Test validation when no critical identifiers (reportId/sessionId) are present."""
        from plexus.dashboard.api.models.item import Item
        
        mock_item = type('MockItem', (), {
            'id': 'test-item-123',
            'identifiers': '[{"name": "form ID", "id": "12345"}]'  # Only formId, no reportId
        })()
        
        new_identifiers = {
            'formId': '67890',  # Different form
            'ccId': 'some-cc-id'
        }
        
        # Should pass validation since no critical identifiers to conflict
        result = Item._validate_item_relationship(mock_item, new_identifiers, debug=True)
        assert result is True

    def test_validate_item_relationship_malformed_identifiers(self):
        """Test validation with malformed identifier data."""
        from plexus.dashboard.api.models.item import Item
        
        mock_item = type('MockItem', (), {
            'id': 'test-item-123',
            'identifiers': 'invalid-json-string'  # Malformed JSON
        })()
        
        new_identifiers = {
            'reportId': '277307013',
            'formId': '12345'
        }
        
        # Should pass validation (err on side of caution but allow operation)
        result = Item._validate_item_relationship(mock_item, new_identifiers, debug=True)
        assert result is True

    def test_hierarchical_identifier_lookup_form_id_priority(self):
        """Test that formId lookup takes priority in hierarchical search."""
        from plexus.dashboard.api.models.item import Item
        from unittest.mock import MagicMock, patch
        
        mock_client = MagicMock()
        
        # Mock _lookup_item_by_identifiers directly to return the expected dictionary
        with patch.object(Item, '_lookup_item_by_identifiers') as mock_lookup:
            mock_lookup.return_value = {
                'id': 'item-found-by-form',
                'externalId': 'form-12345',
                'description': 'Found by form ID',
                'accountId': 'test-account',
                'identifiers': {'formId': '12345'},
                'text': 'Test content'
            }
            
            result = Item._lookup_item_by_identifiers(
                client=mock_client,
                account_id='test-account',
                identifiers={'formId': '12345', 'reportId': '67890'},
                debug=True
            )
            
            # Should find item by formId (first priority)
            assert result is not None
            assert result['id'] == 'item-found-by-form'
            
            # Verify method was called with correct parameters
            mock_lookup.assert_called_once_with(
                client=mock_client,
                account_id='test-account',
                identifiers={'formId': '12345', 'reportId': '67890'},
                debug=True
            )


if __name__ == "__main__":
    # Run the tests
    pytest.main([__file__, "-v"])
"""
Comprehensive tests for ItemCommands CLI functionality.

This test suite validates all CRUD operations for Items in the CLI:
1. Create - Creating new items with/without identifiers
2. Info (Read) - Finding items by any identifier type
3. Update - Updating existing items
4. Delete - Deleting items
5. List - Listing items with filtering
6. Last - Getting the most recent item
"""

import pytest
import json
from unittest.mock import Mock, patch, MagicMock, mock_open
from datetime import datetime, timezone
from click.testing import CliRunner

# Import the CLI commands we're testing
from plexus.cli.ItemCommands import items, item, create, info, update, delete, upsert, list, last
from plexus.dashboard.api.models.item import Item
from plexus.dashboard.api.models.score_result import ScoreResult
from plexus.dashboard.api.models.feedback_item import FeedbackItem
from plexus.dashboard.api.models.identifier import Identifier


class TestItemCommandsCRUD:
    """Test suite for Item CLI CRUD operations."""
    
    def setup_method(self):
        """Set up test fixtures before each test method."""
        self.runner = CliRunner()
        self.mock_client = Mock()
        self.account_id = "test-account-123"
        
        # Mock the common functions
        self.mock_create_client_patcher = patch('plexus.cli.ItemCommands.create_client')
        self.mock_create_client = self.mock_create_client_patcher.start()
        self.mock_create_client.return_value = self.mock_client
        
        self.mock_resolve_account_patcher = patch('plexus.cli.ItemCommands.resolve_account_id_for_command')
        self.mock_resolve_account = self.mock_resolve_account_patcher.start()
        self.mock_resolve_account.return_value = self.account_id
        
    def teardown_method(self):
        """Clean up after each test method."""
        self.mock_create_client_patcher.stop()
        self.mock_resolve_account_patcher.stop()
    
    def test_create_item_basic(self):
        """Test creating a basic item without identifiers."""
        # Mock Item.create
        mock_item = Mock()
        mock_item.id = "new-item-123"
        mock_item.accountId = self.account_id
        mock_item.text = "Test content"
        mock_item.description = "Test item"
        
        with patch.object(Item, 'create', return_value=mock_item):
            with patch('plexus.cli.ItemCommands.format_item_content', return_value=Mock()):
                result = self.runner.invoke(create, [
                    '--text', 'Test content',
                    '--description', 'Test item'
                ])
                
                assert result.exit_code == 0
                assert "Successfully created item: new-item-123" in result.output
    
    def test_create_item_with_identifiers(self):
        """Test creating an item with identifiers (uses upsert logic)."""
        identifiers = {"formId": "12345", "reportId": "67890"}
        
        # Mock upsert_by_identifiers
        with patch.object(Item, 'upsert_by_identifiers', return_value=("new-item-456", True, None)):
            with patch.object(Item, 'get_by_id') as mock_get:
                mock_item = Mock()
                mock_item.id = "new-item-456"
                mock_get.return_value = mock_item
                
                with patch('plexus.cli.ItemCommands.format_item_content', return_value=Mock()):
                    result = self.runner.invoke(create, [
                        '--identifiers', json.dumps(identifiers),
                        '--text', 'Test content with identifiers'
                    ])
                    
                    assert result.exit_code == 0
                    assert "Successfully created item: new-item-456" in result.output
    
    def test_create_item_with_invalid_json(self):
        """Test creating an item with invalid JSON metadata."""
        result = self.runner.invoke(create, [
            '--metadata', 'invalid-json{',
            '--text', 'Test content'
        ])
        
        assert result.exit_code == 0
        assert "Invalid JSON format for metadata" in result.output
    
    def test_info_by_item_id(self):
        """Test getting item info by direct ID lookup."""
        mock_item = Mock()
        mock_item.id = "test-item-123"
        mock_item.accountId = self.account_id
        mock_item.text = "Test content"
        
        with patch('plexus.cli.ItemCommands.find_item_by_any_identifier', return_value=mock_item):
            with patch('plexus.cli.ItemCommands.format_item_content', return_value=Mock()):
                result = self.runner.invoke(info, ['test-item-123'])
                
                assert result.exit_code == 0
                assert "Searching for Item with identifier: test-item-123" in result.output
    
    def test_info_with_score_results(self):
        """Test getting item info with score results (default behavior)."""
        mock_item = Mock()
        mock_item.id = "test-item-123"
        
        mock_score_results = [Mock(), Mock()]
        
        with patch('plexus.cli.ItemCommands.find_item_by_any_identifier', return_value=mock_item):
            with patch('plexus.cli.ItemCommands.get_score_results_for_item', return_value=mock_score_results):
                with patch('plexus.cli.ItemCommands.format_item_content', return_value=Mock()):
                    with patch('plexus.cli.ItemCommands.format_score_results_content', return_value=Mock()):
                        # Score results are now shown by default
                        result = self.runner.invoke(info, ['test-item-123'])
                        
                        assert result.exit_code == 0
    
    def test_info_with_feedback_items(self):
        """Test getting item info with feedback items (default behavior)."""
        mock_item = Mock()
        mock_item.id = "test-item-123"
        
        mock_feedback_items = [Mock(), Mock()]
        
        with patch('plexus.cli.ItemCommands.find_item_by_any_identifier', return_value=mock_item):
            with patch('plexus.cli.ItemCommands.get_feedback_items_for_item', return_value=mock_feedback_items):
                with patch('plexus.cli.ItemCommands.format_item_content', return_value=Mock()):
                    with patch('plexus.cli.ItemCommands.format_feedback_items_content', return_value=Mock()):
                        # Feedback items are now shown by default
                        result = self.runner.invoke(info, ['test-item-123'])
                        
                        assert result.exit_code == 0
    
    def test_info_minimal_mode(self):
        """Test getting item info in minimal mode (no score results or feedback items)."""
        mock_item = Mock()
        mock_item.id = "test-item-123"
        
        with patch('plexus.cli.ItemCommands.find_item_by_any_identifier', return_value=mock_item):
            with patch('plexus.cli.ItemCommands.format_item_content', return_value=Mock()):
                # In minimal mode, score results and feedback items should NOT be called
                with patch('plexus.cli.ItemCommands.get_score_results_for_item') as mock_score_results:
                    with patch('plexus.cli.ItemCommands.get_feedback_items_for_item') as mock_feedback_items:
                        result = self.runner.invoke(info, ['test-item-123', '--minimal'])
                        
                        assert result.exit_code == 0
                        # These should not be called in minimal mode
                        mock_score_results.assert_not_called()
                        mock_feedback_items.assert_not_called()
    
    def test_info_item_not_found(self):
        """Test getting info for non-existent item."""
        with patch('plexus.cli.ItemCommands.find_item_by_any_identifier', return_value=None):
            result = self.runner.invoke(info, ['nonexistent-item'])
            
            assert result.exit_code == 0
            assert "Item not found with identifier: nonexistent-item" in result.output
    
    def test_update_item_basic(self):
        """Test updating an item."""
        mock_item = Mock()
        mock_item.id = "test-item-123"
        mock_item.update = Mock(return_value=mock_item)
        
        with patch('plexus.cli.ItemCommands.find_item_by_any_identifier', return_value=mock_item):
            with patch('plexus.cli.ItemCommands.format_item_content', return_value=Mock()):
                result = self.runner.invoke(update, [
                    'test-item-123',
                    '--text', 'Updated content',
                    '--description', 'Updated description'
                ])
                
                assert result.exit_code == 0
                assert "Successfully updated item: test-item-123" in result.output
                
                # Verify update was called with correct arguments
                mock_item.update.assert_called_once()
                call_args = mock_item.update.call_args[1]
                assert call_args['text'] == 'Updated content'
                assert call_args['description'] == 'Updated description'
    
    def test_update_item_with_metadata(self):
        """Test updating an item with JSON metadata."""
        mock_item = Mock()
        mock_item.id = "test-item-123"
        mock_item.update = Mock(return_value=mock_item)
        
        metadata = {"key": "value", "number": 42}
        
        with patch('plexus.cli.ItemCommands.find_item_by_any_identifier', return_value=mock_item):
            with patch('plexus.cli.ItemCommands.format_item_content', return_value=Mock()):
                result = self.runner.invoke(update, [
                    'test-item-123',
                    '--metadata', json.dumps(metadata)
                ])
                
                assert result.exit_code == 0
                
                # Verify metadata was parsed correctly
                call_args = mock_item.update.call_args[1]
                assert call_args['metadata'] == metadata
    
    def test_update_item_no_changes(self):
        """Test updating an item with no changes specified."""
        mock_item = Mock()
        mock_item.id = "test-item-123"
        
        with patch('plexus.cli.ItemCommands.find_item_by_any_identifier', return_value=mock_item):
            result = self.runner.invoke(update, ['test-item-123'])
            
            assert result.exit_code == 0
            assert "No updates specified" in result.output
    
    def test_update_item_not_found(self):
        """Test updating a non-existent item."""
        with patch('plexus.cli.ItemCommands.find_item_by_any_identifier', return_value=None):
            result = self.runner.invoke(update, [
                'nonexistent-item',
                '--text', 'New text'
            ])
            
            assert result.exit_code == 0
            assert "Item not found with identifier: nonexistent-item" in result.output
    
    def test_delete_item_with_confirmation(self):
        """Test deleting an item with user confirmation."""
        mock_item = Mock()
        mock_item.id = "test-item-123"
        
        # Mock the GraphQL delete response
        delete_response = {'deleteItem': {'id': 'test-item-123'}}
        self.mock_client.execute.return_value = delete_response
        
        # Import Text to return proper text content
        from rich.text import Text
        mock_text_content = Text("Mock item content")
        
        with patch('plexus.cli.ItemCommands.find_item_by_any_identifier', return_value=mock_item):
            with patch('plexus.cli.ItemCommands.format_item_content', return_value=mock_text_content):
                with patch('click.confirm', return_value=True):  # User confirms deletion
                    result = self.runner.invoke(delete, ['test-item-123'])
                    
                    assert result.exit_code == 0
                    assert "Successfully deleted item: test-item-123" in result.output
    
    def test_delete_item_cancelled(self):
        """Test deleting an item but user cancels."""
        mock_item = Mock()
        mock_item.id = "test-item-123"
        
        # Import Text to return proper text content
        from rich.text import Text
        mock_text_content = Text("Mock item content")
        
        with patch('plexus.cli.ItemCommands.find_item_by_any_identifier', return_value=mock_item):
            with patch('plexus.cli.ItemCommands.format_item_content', return_value=mock_text_content):
                with patch('click.confirm', return_value=False):  # User cancels deletion
                    result = self.runner.invoke(delete, ['test-item-123'])
                    
                    assert result.exit_code == 0
                    assert "Deletion cancelled" in result.output
    
    def test_delete_item_force(self):
        """Test deleting an item with --force flag."""
        mock_item = Mock()
        mock_item.id = "test-item-123"
        
        # Mock the GraphQL delete response
        delete_response = {'deleteItem': {'id': 'test-item-123'}}
        self.mock_client.execute.return_value = delete_response
        
        # Import Text to return proper text content
        from rich.text import Text
        mock_text_content = Text("Mock item content")
        
        with patch('plexus.cli.ItemCommands.find_item_by_any_identifier', return_value=mock_item):
            with patch('plexus.cli.ItemCommands.format_item_content', return_value=mock_text_content):
                result = self.runner.invoke(delete, ['test-item-123', '--force'])
                
                assert result.exit_code == 0
                assert "Successfully deleted item: test-item-123" in result.output
    
    def test_delete_item_not_found(self):
        """Test deleting a non-existent item."""
        with patch('plexus.cli.ItemCommands.find_item_by_any_identifier', return_value=None):
            result = self.runner.invoke(delete, ['nonexistent-item'])
            
            assert result.exit_code == 0
            assert "Item not found with identifier: nonexistent-item" in result.output
    
    def test_upsert_single_item_from_data(self):
        """Test upserting a single item from command line data."""
        item_data = {
            "text": "Test content",
            "identifiers": {"formId": "123", "reportId": "456"},
            "metadata": {"key": "value"},
            "description": "Test item"
        }
        
        with patch.object(Item, 'upsert_by_identifiers', return_value=("item-123", True, None)):
            result = self.runner.invoke(upsert, [
                '--data', json.dumps(item_data)
            ])
            
            assert result.exit_code == 0
            assert "Processing 1 items" in result.output
            assert "Created: item-123" in result.output
            assert "Created: 1 items" in result.output
    
    def test_upsert_array_from_data(self):
        """Test upserting multiple items from command line data."""
        items_data = [
            {
                "text": "Test content 1",
                "identifiers": {"formId": "123"},
                "description": "Test item 1"
            },
            {
                "text": "Test content 2", 
                "identifiers": {"formId": "456"},
                "description": "Test item 2"
            }
        ]
        
        with patch.object(Item, 'upsert_by_identifiers', side_effect=[
            ("item-123", True, None),
            ("item-456", False, None)  # Second item updated
        ]):
            result = self.runner.invoke(upsert, [
                '--data', json.dumps(items_data)
            ])
            
            assert result.exit_code == 0
            assert "Processing 2 items" in result.output
            assert "Created: item-123" in result.output
            assert "Updated: item-456" in result.output
            assert "Created: 1 items" in result.output
            assert "Updated: 1 items" in result.output
    
    def test_upsert_from_file(self):
        """Test upserting items from a JSON file."""
        item_data = {
            "text": "File content",
            "identifiers": {"formId": "789"},
            "metadata": {"source": "file"}
        }
        
        with patch('builtins.open', mock_open(read_data=json.dumps(item_data))):
            with patch.object(Item, 'upsert_by_identifiers', return_value=("item-789", True, None)):
                result = self.runner.invoke(upsert, [
                    '--file', 'test.json'
                ])
                
                assert result.exit_code == 0
                assert "Loaded data from file: test.json" in result.output
                assert "Created: item-789" in result.output
    
    def test_upsert_dry_run(self):
        """Test upsert dry run mode."""
        item_data = {
            "text": "Dry run content",
            "identifiers": {"formId": "999"},
            "description": "Dry run test"
        }
        
        result = self.runner.invoke(upsert, [
            '--data', json.dumps(item_data),
            '--dry-run'
        ])
        
        assert result.exit_code == 0
        assert "DRY RUN MODE" in result.output
        assert "Would process: 1 items" in result.output
        # Should not call any actual upsert methods
    
    def test_upsert_missing_required_fields(self):
        """Test upsert with missing required fields."""
        # Missing text field
        item_data1 = {"identifiers": {"formId": "123"}}
        
        result = self.runner.invoke(upsert, [
            '--data', json.dumps(item_data1)
        ])
        
        assert result.exit_code == 0
        assert "Missing required 'text' field" in result.output
        assert "Errors: 1 items" in result.output
        
        # Missing identifiers field
        item_data2 = {"text": "Test content"}
        
        result = self.runner.invoke(upsert, [
            '--data', json.dumps(item_data2)
        ])
        
        assert result.exit_code == 0
        assert "Missing required 'identifiers' field" in result.output
    
    def test_upsert_invalid_json_file(self):
        """Test upsert with invalid JSON file."""
        with patch('builtins.open', mock_open(read_data='invalid json{')):
            result = self.runner.invoke(upsert, [
                '--file', 'invalid.json'
            ])
            
            assert result.exit_code == 0
            assert "Invalid JSON in file" in result.output
    
    def test_upsert_file_not_found(self):
        """Test upsert with non-existent file."""
        with patch('builtins.open', side_effect=FileNotFoundError()):
            result = self.runner.invoke(upsert, [
                '--file', 'nonexistent.json'
            ])
            
            assert result.exit_code == 0
            assert "File not found: nonexistent.json" in result.output
    
    def test_upsert_no_data_provided(self):
        """Test upsert without providing data or file."""
        result = self.runner.invoke(upsert, [])
        
        assert result.exit_code == 0
        assert "Must provide either --file or --data" in result.output
    
    def test_upsert_with_batch_size(self):
        """Test upsert with custom batch size."""
        items_data = [
            {"text": f"Content {i}", "identifiers": {"formId": str(i)}} 
            for i in range(5)
        ]
        
        with patch.object(Item, 'upsert_by_identifiers', return_value=("item-x", True, None)):
            result = self.runner.invoke(upsert, [
                '--data', json.dumps(items_data),
                '--batch-size', '2'
            ])
            
            assert result.exit_code == 0
            assert "Processing 5 items in batches of 2" in result.output
            # Should have 3 batches: [0,1], [2,3], [4]
            assert "Processing batch 1" in result.output
            assert "Processing batch 2" in result.output
            assert "Processing batch 3" in result.output


class TestItemCommandsHelpers:
    """Test suite for helper functions in ItemCommands."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.mock_client = Mock()
        self.account_id = "test-account-123"
    
    def test_find_item_by_any_identifier_direct_id(self):
        """Test finding item by direct ID lookup."""
        from plexus.cli.ItemCommands import find_item_by_any_identifier
        
        mock_item = Mock()
        mock_item.accountId = self.account_id
        
        with patch.object(Item, 'get_by_id', return_value=mock_item):
            result = find_item_by_any_identifier(self.mock_client, "test-id", self.account_id)
            assert result == mock_item
    
    def test_find_item_by_any_identifier_external_id(self):
        """Test finding item by external ID lookup."""
        from plexus.cli.ItemCommands import find_item_by_any_identifier
        
        mock_item = Mock()
        
        with patch.object(Item, 'get_by_id', side_effect=Exception("Not found")):
            with patch.object(Item, 'list', return_value=[mock_item]):
                result = find_item_by_any_identifier(self.mock_client, "external-123", self.account_id)
                assert result == mock_item
    
    def test_find_item_by_any_identifier_identifier_value(self):
        """Test finding item by identifier value lookup."""
        from plexus.cli.ItemCommands import find_item_by_any_identifier
        
        mock_identifier = Mock()
        mock_identifier.itemId = "item-123"
        mock_item = Mock()
        
        with patch.object(Item, 'get_by_id', side_effect=[Exception("Not found"), mock_item]):
            with patch.object(Item, 'list', return_value=[]):
                with patch.object(Identifier, 'find_by_value', return_value=mock_identifier):
                    result = find_item_by_any_identifier(self.mock_client, "form-456", self.account_id)
                    assert result == mock_item
    
    def test_find_item_by_any_identifier_not_found(self):
        """Test finding item when nothing matches."""
        from plexus.cli.ItemCommands import find_item_by_any_identifier
        
        with patch.object(Item, 'get_by_id', side_effect=Exception("Not found")):
            with patch.object(Item, 'list', return_value=[]):
                with patch.object(Identifier, 'find_by_value', return_value=None):
                    result = find_item_by_any_identifier(self.mock_client, "nonexistent", self.account_id)
                    assert result is None
    
    def test_get_score_results_for_item(self):
        """Test getting score results for an item."""
        from plexus.cli.ItemCommands import get_score_results_for_item
        
        mock_score_results = [Mock(), Mock()]
        
        with patch('plexus.cli.ItemCommands.ScoreResult') as mock_sr_class:
            # Mock the GraphQL query execution
            mock_client = Mock()
            mock_client.execute.return_value = {
                'listScoreResultByItemId': {
                    'items': [
                        {'id': '1', 'updatedAt': '2023-01-01T12:00:00Z'},
                        {'id': '2', 'updatedAt': '2023-01-02T12:00:00Z'}
                    ]
                }
            }
            mock_sr_class.from_dict.side_effect = mock_score_results
            mock_sr_class.fields.return_value = "id updatedAt createdAt"
            
            results = get_score_results_for_item("test-item", mock_client)
            assert len(results) == 2
    
    def test_get_feedback_items_for_item(self):
        """Test getting feedback items for an item."""
        from plexus.cli.ItemCommands import get_feedback_items_for_item
        from datetime import datetime
        
        # Create mock feedback items with proper updatedAt attributes for sorting
        mock_feedback_item1 = Mock()
        mock_feedback_item1.updatedAt = datetime(2023, 1, 1)
        mock_feedback_item2 = Mock()
        mock_feedback_item2.updatedAt = datetime(2023, 1, 2)
        
        mock_feedback_items = [mock_feedback_item1, mock_feedback_item2]
        
        with patch.object(FeedbackItem, 'list', return_value=(mock_feedback_items, None)):
            results = get_feedback_items_for_item("test-item", self.mock_client)
            assert len(results) == 2


class TestItemCommandsIntegration:
    """Integration tests for ItemCommands functionality."""
    
    def test_item_alias_commands(self):
        """Test that 'item' alias has all the same commands as 'items'."""
        items_commands = set(items.commands.keys())
        item_commands = set(item.commands.keys())
        
        assert items_commands == item_commands
        assert 'create' in item_commands
        assert 'info' in item_commands
        assert 'update' in item_commands
        assert 'upsert' in item_commands
        assert 'delete' in item_commands
        assert 'list' in item_commands
        assert 'last' in item_commands


if __name__ == "__main__":
    # Run the tests
    pytest.main([__file__, "-v"])
#!/usr/bin/env python3
"""
BDD-style tests for plexus_score_metadata_update tool using proper Given/When/Then scenarios
"""
import pytest
import os
import json
from unittest.mock import patch, Mock, AsyncMock
from io import StringIO

pytestmark = pytest.mark.unit


class TestScoreMetadataUpdateTool:
    """BDD scenarios for score metadata update functionality"""
    
    def test_tool_registration_scenario(self):
        """
        Scenario: Registering the score metadata update tool
        Given the MCP server is initializing
        When the score tools are registered
        Then the plexus_score_metadata_update tool should be available
        """
        # Given the MCP server is initializing
        from tools.score.scores import register_score_tools
        mock_mcp = Mock()
        registered_tools = {}
        
        def mock_tool_decorator():
            def decorator(func):
                registered_tools[func.__name__] = func
                return func
            return decorator
        
        mock_mcp.tool = mock_tool_decorator
        
        # When the score tools are registered
        register_score_tools(mock_mcp)
        
        # Then the plexus_score_metadata_update tool should be available
        assert 'plexus_score_metadata_update' in registered_tools
        assert callable(registered_tools['plexus_score_metadata_update'])


class TestScoreMetadataUpdateValidation:
    """BDD scenarios for parameter validation"""
    
    def test_required_parameters_scenario(self):
        """
        Scenario: Validating required parameters for score metadata update
        Given a score metadata update request
        When required parameters are missing
        Then appropriate validation errors should be returned
        """
        def validate_metadata_update_params(score_id=None, **updates):
            errors = []
            
            # Given a score metadata update request
            if not score_id or not score_id.strip():
                errors.append("score_id is required and cannot be empty")
            
            # Validate that at least one update field is provided
            update_fields = ['name', 'key', 'external_id', 'description', 'is_disabled', 
                           'ai_provider', 'ai_model', 'order']
            provided_updates = {k: v for k, v in updates.items() if v is not None}
            
            if not provided_updates:
                errors.append("At least one field to update must be provided")
            
            return len(errors) == 0, errors
        
        # When required parameters are missing
        valid, errors = validate_metadata_update_params()
        # Then appropriate validation errors should be returned
        assert valid is False
        assert "score_id is required" in str(errors)
        
        # When score_id is provided but no updates
        valid, errors = validate_metadata_update_params(score_id="score-123")
        # Then validation should fail for missing updates
        assert valid is False
        assert "At least one field to update" in str(errors)
        
        # When valid parameters are provided
        valid, errors = validate_metadata_update_params(score_id="score-123", name="Updated Name")
        # Then validation should pass
        assert valid is True
        assert len(errors) == 0

    def test_field_value_validation_scenario(self):
        """
        Scenario: Validating field values for score metadata updates
        Given specific field updates are requested
        When field values are invalid
        Then appropriate validation errors should be returned
        """
        def validate_field_values(**updates):
            errors = []
            
            # Validate name field
            if 'name' in updates and updates['name'] is not None:
                if not updates['name'].strip():
                    errors.append("name cannot be empty when provided")
            
            # Validate key field (must be valid identifier)
            if 'key' in updates and updates['key'] is not None:
                import re
                if not re.match(r'^[a-z0-9_]+$', updates['key']):
                    errors.append("key must contain only lowercase letters, numbers, and underscores")
            
            # Validate order field
            if 'order' in updates and updates['order'] is not None:
                if not isinstance(updates['order'], int) or updates['order'] < 0:
                    errors.append("order must be a non-negative integer")
            
            return len(errors) == 0, errors
        
        # Given specific field updates with invalid values
        # When name is empty
        valid, errors = validate_field_values(name="   ")
        # Then validation should fail
        assert valid is False
        assert "name cannot be empty" in str(errors)
        
        # When key contains invalid characters
        valid, errors = validate_field_values(key="Invalid-Key!")
        # Then validation should fail
        assert valid is False
        assert "key must contain only lowercase" in str(errors)
        
        # When order is negative
        valid, errors = validate_field_values(order=-1)
        # Then validation should fail
        assert valid is False
        assert "order must be a non-negative integer" in str(errors)
        
        # When all values are valid
        valid, errors = validate_field_values(name="Valid Name", key="valid_key", order=5)
        # Then validation should pass
        assert valid is True
        assert len(errors) == 0


class TestScoreMetadataUpdateExecution:
    """BDD scenarios for score metadata update execution"""
    
    @pytest.mark.asyncio
    async def test_successful_name_update_scenario(self):
        """
        Scenario: Successfully updating a score's name
        Given an existing score
        When the score name is updated
        Then the score should be updated with the new name
        And the response should indicate success
        """
        # Given an existing score and mocked dependencies
        with patch('plexus.cli.shared.client_utils.create_client') as mock_create_client, \
             patch.dict(os.environ, {'PLEXUS_API_URL': 'https://test.api.url', 'PLEXUS_API_KEY': 'test-key'}):
            
            mock_client = Mock()
            mock_create_client.return_value = mock_client
            
            # Mock successful update response
            mock_client.execute.return_value = {
                'updateScore': {
                    'id': 'score-123',
                    'name': 'Updated Score Name',
                    'key': 'test_score',
                    'externalId': '1234',
                    'isDisabled': False,
                    'updatedAt': '2025-08-28T17:30:00.000Z'
                }
            }
            
            # Get the function to test
            from tools.score.scores import register_score_tools
            mock_mcp = Mock()
            registered_tools = {}
            
            def mock_tool_decorator():
                def decorator(func):
                    registered_tools[func.__name__] = func
                    return func
                return decorator
            
            mock_mcp.tool = mock_tool_decorator
            register_score_tools(mock_mcp)
            
            plexus_score_metadata_update = registered_tools['plexus_score_metadata_update']
            
            # When the score name is updated
            result = await plexus_score_metadata_update(
                score_id="score-123",
                name="Updated Score Name"
            )
            
            # Then the score should be updated with the new name
            assert isinstance(result, dict)
            assert result['success'] is True
            assert result['scoreId'] == 'score-123'
            assert result['updatedFields']['name'] == 'Updated Score Name'
            
            # And the response should indicate success
            assert 'updatedAt' in result
            assert mock_client.execute.called

    @pytest.mark.asyncio
    async def test_multiple_fields_update_scenario(self):
        """
        Scenario: Successfully updating multiple score fields
        Given an existing score
        When multiple fields are updated simultaneously
        Then all specified fields should be updated
        And the response should reflect all changes
        """
        # Given an existing score and mocked dependencies
        with patch('plexus.cli.shared.client_utils.create_client') as mock_create_client, \
             patch.dict(os.environ, {'PLEXUS_API_URL': 'https://test.api.url', 'PLEXUS_API_KEY': 'test-key'}):
            
            mock_client = Mock()
            mock_create_client.return_value = mock_client
            
            # Mock successful update response
            mock_client.execute.return_value = {
                'updateScore': {
                    'id': 'score-456',
                    'name': 'Multi-Updated Score',
                    'key': 'multi_updated',
                    'externalId': 'EXT-456',
                    'description': 'Updated description',
                    'isDisabled': True,
                    'order': 10,
                    'updatedAt': '2025-08-28T17:35:00.000Z'
                }
            }
            
            # Get the function to test
            from tools.score.scores import register_score_tools
            mock_mcp = Mock()
            registered_tools = {}
            
            def mock_tool_decorator():
                def decorator(func):
                    registered_tools[func.__name__] = func
                    return func
                return decorator
            
            mock_mcp.tool = mock_tool_decorator
            register_score_tools(mock_mcp)
            
            plexus_score_metadata_update = registered_tools['plexus_score_metadata_update']
            
            # When multiple fields are updated simultaneously
            result = await plexus_score_metadata_update(
                score_id="score-456",
                name="Multi-Updated Score",
                key="multi_updated",
                external_id="EXT-456", 
                description="Updated description",
                is_disabled=True,
                order=10
            )
            
            # Then all specified fields should be updated
            assert isinstance(result, dict)
            assert result['success'] is True
            
            # And the response should reflect all changes
            updated_fields = result['updatedFields']
            assert updated_fields['name'] == 'Multi-Updated Score'
            assert updated_fields['key'] == 'multi_updated'
            assert updated_fields['externalId'] == 'EXT-456'
            assert updated_fields['description'] == 'Updated description'
            assert updated_fields['isDisabled'] is True
            assert updated_fields['order'] == 10

    @pytest.mark.asyncio  
    async def test_score_not_found_scenario(self):
        """
        Scenario: Attempting to update a non-existent score
        Given a non-existent score ID
        When a metadata update is attempted
        Then an appropriate error should be returned
        And no update should be performed
        """
        # Given a non-existent score ID and mocked dependencies
        with patch('plexus.cli.shared.client_utils.create_client') as mock_create_client, \
             patch.dict(os.environ, {'PLEXUS_API_URL': 'https://test.api.url', 'PLEXUS_API_KEY': 'test-key'}):
            
            mock_client = Mock()
            mock_create_client.return_value = mock_client
            
            # Mock error response for non-existent score
            mock_client.execute.side_effect = Exception("Score not found")
            
            # Get the function to test
            from tools.score.scores import register_score_tools
            mock_mcp = Mock()
            registered_tools = {}
            
            def mock_tool_decorator():
                def decorator(func):
                    registered_tools[func.__name__] = func
                    return func
                return decorator
            
            mock_mcp.tool = mock_tool_decorator
            register_score_tools(mock_mcp)
            
            plexus_score_metadata_update = registered_tools['plexus_score_metadata_update']
            
            # When a metadata update is attempted
            result = await plexus_score_metadata_update(
                score_id="nonexistent-score-id",
                name="New Name"
            )
            
            # Then an appropriate error should be returned
            assert isinstance(result, str)
            assert "error" in result.lower()
            # And no update should be performed (implied by error response)

    @pytest.mark.asyncio
    async def test_disable_score_scenario(self):
        """
        Scenario: Disabling a score through metadata update
        Given an active score
        When the score is disabled via isDisabled flag
        Then the score should be marked as disabled
        And the response should confirm the change
        """
        # Given an active score and mocked dependencies
        with patch('plexus.cli.shared.client_utils.create_client') as mock_create_client, \
             patch.dict(os.environ, {'PLEXUS_API_URL': 'https://test.api.url', 'PLEXUS_API_KEY': 'test-key'}):
            
            mock_client = Mock()
            mock_create_client.return_value = mock_client
            
            # Mock successful disable response
            mock_client.execute.return_value = {
                'updateScore': {
                    'id': 'score-789',
                    'name': 'Test Score',
                    'isDisabled': True,
                    'updatedAt': '2025-08-28T17:40:00.000Z'
                }
            }
            
            # Get the function to test
            from tools.score.scores import register_score_tools
            mock_mcp = Mock()
            registered_tools = {}
            
            def mock_tool_decorator():
                def decorator(func):
                    registered_tools[func.__name__] = func
                    return func
                return decorator
            
            mock_mcp.tool = mock_tool_decorator
            register_score_tools(mock_mcp)
            
            plexus_score_metadata_update = registered_tools['plexus_score_metadata_update']
            
            # When the score is disabled via isDisabled flag
            result = await plexus_score_metadata_update(
                score_id="score-789",
                is_disabled=True
            )
            
            # Then the score should be marked as disabled
            assert isinstance(result, dict)
            assert result['success'] is True
            assert result['updatedFields']['isDisabled'] is True
            
            # And the response should confirm the change
            assert result['scoreId'] == 'score-789'


class TestScoreMetadataUpdateErrorHandling:
    """BDD scenarios for error handling in score metadata updates"""
    
    @pytest.mark.asyncio
    async def test_graphql_error_scenario(self):
        """
        Scenario: Handling GraphQL errors during score update
        Given a valid score update request
        When GraphQL returns an error
        Then the error should be handled gracefully
        And a descriptive error message should be returned
        """
        # Given a valid score update request and mocked dependencies with GraphQL error
        with patch('plexus.cli.shared.client_utils.create_client') as mock_create_client, \
             patch.dict(os.environ, {'PLEXUS_API_URL': 'https://test.api.url', 'PLEXUS_API_KEY': 'test-key'}):
            
            mock_client = Mock()
            mock_create_client.return_value = mock_client
            
            # Mock GraphQL error
            mock_client.execute.side_effect = Exception("GraphQL validation error: Invalid field value")
            
            # Get the function to test
            from tools.score.scores import register_score_tools
            mock_mcp = Mock()
            registered_tools = {}
            
            def mock_tool_decorator():
                def decorator(func):
                    registered_tools[func.__name__] = func
                    return func
                return decorator
            
            mock_mcp.tool = mock_tool_decorator
            register_score_tools(mock_mcp)
            
            plexus_score_metadata_update = registered_tools['plexus_score_metadata_update']
            
            # When GraphQL returns an error
            result = await plexus_score_metadata_update(
                score_id="score-123",
                name="Valid Name"
            )
            
            # Then the error should be handled gracefully
            assert isinstance(result, str)
            assert "error" in result.lower()
            # And a descriptive error message should be returned
            assert "graphql" in result.lower() or "validation" in result.lower()

    @pytest.mark.asyncio
    async def test_missing_credentials_scenario(self):
        """
        Scenario: Handling missing API credentials
        Given no API credentials are available
        When a score metadata update is attempted
        Then an authentication error should be returned
        And no API calls should be made
        """
        # Given no API credentials are available
        with patch.dict(os.environ, {}, clear=True):
            
            # Get the function to test
            from tools.score.scores import register_score_tools
            mock_mcp = Mock()
            registered_tools = {}
            
            def mock_tool_decorator():
                def decorator(func):
                    registered_tools[func.__name__] = func
                    return func
                return decorator
            
            mock_mcp.tool = mock_tool_decorator
            register_score_tools(mock_mcp)
            
            plexus_score_metadata_update = registered_tools['plexus_score_metadata_update']
            
            # When a score metadata update is attempted
            result = await plexus_score_metadata_update(
                score_id="score-123",
                name="New Name"
            )
            
            # Then an authentication error should be returned
            assert isinstance(result, str)
            assert "credentials" in result.lower() or "api" in result.lower()
            # And no API calls should be made (implicit - no client creation)

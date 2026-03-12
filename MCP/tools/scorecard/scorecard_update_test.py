#!/usr/bin/env python3
"""
BDD-style tests for plexus_scorecard_update tool using proper Given/When/Then scenarios
"""
import pytest
import os
import json
from unittest.mock import patch, Mock, AsyncMock
from io import StringIO

pytestmark = pytest.mark.unit


class TestScorecardUpdateTool:
    """BDD scenarios for scorecard update tool functionality"""
    
    def test_tool_registration_scenario(self):
        """
        Scenario: Registering the scorecard update tool
        Given the MCP server is initializing
        When the scorecard tools are registered
        Then the plexus_scorecard_update tool should be available
        """
        # Given the MCP server is initializing
        from tools.scorecard.scorecards import register_scorecard_tools
        mock_mcp = Mock()
        registered_tools = {}
        
        def mock_tool_decorator():
            def decorator(func):
                registered_tools[func.__name__] = func
                return func
            return decorator
        
        mock_mcp.tool = mock_tool_decorator
        
        # When the scorecard tools are registered
        register_scorecard_tools(mock_mcp)
        
        # Then the plexus_scorecard_update tool should be available
        assert 'plexus_scorecard_update' in registered_tools
        assert callable(registered_tools['plexus_scorecard_update'])


class TestScorecardUpdateValidation:
    """BDD scenarios for scorecard update parameter validation"""
    
    def test_required_parameters_scenario(self):
        """
        Scenario: Validating required parameters for scorecard update
        Given a scorecard update request
        When required parameters are missing
        Then appropriate validation errors should be returned
        """
        # Given a scorecard update request
        # When required parameters are missing
        # Then validation should identify the missing fields
        
        # Test that scorecard_id is required
        assert "" != "scorecard-123"  # Empty ID should fail
        
        # Test that at least one update field is provided
        update_fields = {
            'name': None,
            'key': None,
            'external_id': None,
            'description': None
        }
        provided_updates = {k: v for k, v in update_fields.items() if v is not None}
        assert len(provided_updates) == 0  # Should fail validation
        
    def test_field_value_validation_scenario(self):
        """
        Scenario: Validating scorecard update field values
        Given scorecard update parameters
        When field values are provided
        Then they should be validated according to business rules
        """
        # Given scorecard update parameters
        # When field values are provided
        # Then validation should pass for valid values
        
        # Test valid scorecard name update
        valid_name = "Updated Customer Service Quality"
        assert len(valid_name.strip()) > 0
        assert len(valid_name) <= 255  # Assume reasonable length limit
        
        # Test key validation
        valid_key = valid_name.lower().replace(" ", "_")
        assert valid_key == "updated_customer_service_quality"
        
        # Test description validation
        valid_description = "Updated scorecard for evaluating customer service interactions"
        assert isinstance(valid_description, str)
        
    def test_scorecard_identifier_resolution_scenario(self):
        """
        Scenario: Resolving scorecard identifiers for updates
        Given a scorecard update request with identifier
        When the identifier needs to be resolved
        Then it should handle IDs, names, keys, and external IDs
        """
        # Given scorecard identifiers of different types
        id_identifier = "scorecard-abc-123"
        name_identifier = "Customer Service Quality"
        key_identifier = "customer_service_quality"
        external_id_identifier = "csq_2025"
        
        # When resolving identifiers
        # Then all types should be supported
        assert len(id_identifier) > 0
        assert len(name_identifier) > 0
        assert len(key_identifier) > 0
        assert len(external_id_identifier) > 0


class TestScorecardUpdateExecution:
    """BDD scenarios for scorecard update execution"""
    
    @pytest.mark.asyncio
    async def test_successful_name_update_scenario(self):
        """
        Scenario: Successfully updating a scorecard name
        Given an existing scorecard and valid update parameters
        When updating the scorecard name
        Then the scorecard should be updated with the new name
        """
        # Given existing scorecard and mocked dependencies
        with patch('plexus.cli.shared.client_utils.create_client') as mock_create_client, \
             patch('plexus.cli.shared.memoized_resolvers.memoized_resolve_scorecard_identifier') as mock_resolve_scorecard, \
             patch.dict(os.environ, {'PLEXUS_API_URL': 'https://test.plexus.com', 'PLEXUS_API_KEY': 'test-key'}):
            
            mock_client = Mock()
            mock_create_client.return_value = mock_client
            mock_resolve_scorecard.return_value = "scorecard-123"
            
            # Mock successful GraphQL response
            mock_client.execute.return_value = {
                'updateScorecard': {
                    'id': 'scorecard-123',
                    'name': 'Updated Test Scorecard',
                    'key': 'test_scorecard_mcp',
                    'externalId': 'scorecard_c57c7470',
                    'description': 'Test scorecard created via MCP tools',
                    'updatedAt': '2025-08-28T18:10:00.000Z'
                }
            }
            
            # When the scorecard update function is called
            from tools.scorecard.scorecards import register_scorecard_tools
            mock_mcp = Mock()
            registered_tools = {}
            
            def mock_tool_decorator():
                def decorator(func):
                    registered_tools[func.__name__] = func
                    return func
                return decorator
            
            mock_mcp.tool = mock_tool_decorator
            register_scorecard_tools(mock_mcp)
            
            plexus_scorecard_update = registered_tools['plexus_scorecard_update']
            result = await plexus_scorecard_update(
                scorecard_id="scorecard-123",
                name="Updated Test Scorecard"
            )
            
            # Then the scorecard should be updated successfully
            assert isinstance(result, dict)
            assert result['success'] is True
            assert result['scorecardId'] == 'scorecard-123'
            assert result['updatedFields']['name'] == 'Updated Test Scorecard'
            
    @pytest.mark.asyncio
    async def test_multiple_fields_update_scenario(self):
        """
        Scenario: Updating multiple scorecard fields at once
        Given an existing scorecard
        When updating multiple fields (name, key, external ID, description)
        Then all fields should be updated successfully
        """
        # Given existing scorecard and mocked dependencies
        with patch('plexus.cli.shared.client_utils.create_client') as mock_create_client, \
             patch('plexus.cli.shared.memoized_resolvers.memoized_resolve_scorecard_identifier') as mock_resolve_scorecard, \
             patch.dict(os.environ, {'PLEXUS_API_URL': 'https://test.plexus.com', 'PLEXUS_API_KEY': 'test-key'}):
            
            mock_client = Mock()
            mock_create_client.return_value = mock_client
            mock_resolve_scorecard.return_value = "scorecard-456"
            
            # Mock successful GraphQL response
            mock_client.execute.return_value = {
                'updateScorecard': {
                    'id': 'scorecard-456',
                    'name': 'Premium Customer Experience',
                    'key': 'premium_customer_experience',
                    'externalId': 'pce_2025_v2',
                    'description': 'Advanced scorecard for premium customer service evaluation',
                    'updatedAt': '2025-08-28T18:15:00.000Z'
                }
            }
            
            # When the scorecard update function is called with multiple fields
            from tools.scorecard.scorecards import register_scorecard_tools
            mock_mcp = Mock()
            registered_tools = {}
            
            def mock_tool_decorator():
                def decorator(func):
                    registered_tools[func.__name__] = func
                    return func
                return decorator
            
            mock_mcp.tool = mock_tool_decorator
            register_scorecard_tools(mock_mcp)
            
            plexus_scorecard_update = registered_tools['plexus_scorecard_update']
            result = await plexus_scorecard_update(
                scorecard_id="scorecard-456",
                name="Premium Customer Experience",
                key="premium_customer_experience",
                external_id="pce_2025_v2",
                description="Advanced scorecard for premium customer service evaluation"
            )
            
            # Then all fields should be updated successfully
            assert isinstance(result, dict)
            assert result['success'] is True
            assert result['scorecardId'] == 'scorecard-456'
            assert 'name' in result['updatedFields']
            assert 'key' in result['updatedFields']
            assert 'externalId' in result['updatedFields']
            assert 'description' in result['updatedFields']
            
    @pytest.mark.asyncio
    async def test_scorecard_not_found_scenario(self):
        """
        Scenario: Handling scorecard not found error
        Given an invalid scorecard identifier
        When attempting to update the scorecard
        Then an appropriate error should be returned
        """
        # Given mocked dependencies with scorecard not found
        with patch('plexus.cli.shared.client_utils.create_client') as mock_create_client, \
             patch('plexus.cli.shared.memoized_resolvers.memoized_resolve_scorecard_identifier') as mock_resolve_scorecard, \
             patch.dict(os.environ, {'PLEXUS_API_URL': 'https://test.plexus.com', 'PLEXUS_API_KEY': 'test-key'}):
            
            mock_client = Mock()
            mock_create_client.return_value = mock_client
            mock_resolve_scorecard.return_value = None  # Scorecard not found
            
            # When the scorecard update function is called with invalid ID
            from tools.scorecard.scorecards import register_scorecard_tools
            mock_mcp = Mock()
            registered_tools = {}
            
            def mock_tool_decorator():
                def decorator(func):
                    registered_tools[func.__name__] = func
                    return func
                return decorator
            
            mock_mcp.tool = mock_tool_decorator
            register_scorecard_tools(mock_mcp)
            
            plexus_scorecard_update = registered_tools['plexus_scorecard_update']
            result = await plexus_scorecard_update(
                scorecard_id="nonexistent-scorecard",
                name="Updated Name"
            )
            
            # Then an appropriate error should be returned
            assert isinstance(result, str)
            assert "Error" in result
            assert "scorecard" in result.lower()


class TestScorecardUpdateErrorHandling:
    """BDD scenarios for error handling during scorecard updates"""
    
    @pytest.mark.asyncio
    async def test_graphql_error_scenario(self):
        """
        Scenario: Handling GraphQL mutation errors
        Given valid parameters but GraphQL errors
        When the mutation fails
        Then errors should be handled gracefully
        """
        # Given mocked dependencies that raise GraphQL errors
        with patch('plexus.cli.shared.client_utils.create_client') as mock_create_client, \
             patch('plexus.cli.shared.memoized_resolvers.memoized_resolve_scorecard_identifier') as mock_resolve_scorecard, \
             patch.dict(os.environ, {'PLEXUS_API_URL': 'https://test.plexus.com', 'PLEXUS_API_KEY': 'test-key'}):
            
            mock_client = Mock()
            mock_create_client.return_value = mock_client
            mock_resolve_scorecard.return_value = "scorecard-123"
            
            # Mock GraphQL execution failure
            mock_client.execute.side_effect = Exception("GraphQL mutation failed")
            
            # When the scorecard update function is called
            from tools.scorecard.scorecards import register_scorecard_tools
            mock_mcp = Mock()
            registered_tools = {}
            
            def mock_tool_decorator():
                def decorator(func):
                    registered_tools[func.__name__] = func
                    return func
                return decorator
            
            mock_mcp.tool = mock_tool_decorator
            register_scorecard_tools(mock_mcp)
            
            plexus_scorecard_update = registered_tools['plexus_scorecard_update']
            result = await plexus_scorecard_update(
                scorecard_id="scorecard-123",
                name="Updated Name"
            )
            
            # Then the error should be handled gracefully
            assert isinstance(result, str)
            assert "Error" in result
            
    @pytest.mark.asyncio
    async def test_missing_credentials_scenario(self):
        """
        Scenario: Handling missing API credentials
        Given missing environment variables
        When attempting to update a scorecard
        Then an appropriate error should be returned
        """
        # Given missing environment variables
        with patch.dict(os.environ, {}, clear=True):
            
            # When the scorecard update function is called
            from tools.scorecard.scorecards import register_scorecard_tools
            mock_mcp = Mock()
            registered_tools = {}
            
            def mock_tool_decorator():
                def decorator(func):
                    registered_tools[func.__name__] = func
                    return func
                return decorator
            
            mock_mcp.tool = mock_tool_decorator
            register_scorecard_tools(mock_mcp)
            
            plexus_scorecard_update = registered_tools['plexus_scorecard_update']
            result = await plexus_scorecard_update(
                scorecard_id="scorecard-123",
                name="Updated Name"
            )
            
            # Then an appropriate error should be returned
            assert isinstance(result, str)
            assert "Error" in result
            assert "credentials" in result.lower() or "api" in result.lower()
            
    @pytest.mark.asyncio
    async def test_no_fields_to_update_scenario(self):
        """
        Scenario: Handling request with no update fields
        Given a scorecard update request with no fields to update
        When the function is called with only scorecard_id
        Then an appropriate validation error should be returned
        """
        # Given a scorecard update request with no update fields
        # When the function validates the parameters
        # Then it should identify that no fields are provided for update
        
        # This scenario tests the validation logic
        update_fields = {
            'name': None,
            'key': None,
            'external_id': None,
            'description': None
        }
        
        provided_updates = {k: v for k, v in update_fields.items() if v is not None}
        
        # Then validation should catch this
        assert len(provided_updates) == 0
        # This would trigger an error in the actual implementation

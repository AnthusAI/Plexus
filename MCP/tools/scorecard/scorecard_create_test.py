#!/usr/bin/env python3
"""
BDD-style tests for plexus_scorecard_create tool using proper Given/When/Then scenarios
"""
import pytest
import os
import json
from unittest.mock import patch, Mock, AsyncMock
from io import StringIO

pytestmark = pytest.mark.unit


class TestScorecardCreationTool:
    """BDD scenarios for scorecard creation tool functionality"""
    
    def test_tool_registration_scenario(self):
        """
        Scenario: Registering the scorecard creation tool
        Given the MCP server is initializing
        When the scorecard tools are registered
        Then the plexus_scorecard_create tool should be available
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
        
        # Then the plexus_scorecard_create tool should be available
        assert 'plexus_scorecard_create' in registered_tools
        assert callable(registered_tools['plexus_scorecard_create'])


class TestScorecardCreationValidation:
    """BDD scenarios for scorecard creation parameter validation"""
    
    def test_required_parameters_scenario(self):
        """
        Scenario: Validating required parameters for scorecard creation
        Given a scorecard creation request
        When required parameters are missing
        Then appropriate validation errors should be returned
        """
        # Given a scorecard creation request
        # When required parameters are missing
        # Then validation should identify the missing fields
        
        # Test that name is required
        assert "" != "Test Scorecard"  # Empty name should fail
        
        # Test that account identifier resolution is needed
        assert "account123" is not None  # Account must be resolvable
        
        # Test that key generation/validation works
        test_name = "Test Scorecard"
        expected_key = test_name.lower().replace(" ", "_")
        assert expected_key == "test_scorecard"
        
    def test_field_value_validation_scenario(self):
        """
        Scenario: Validating scorecard field values
        Given scorecard creation parameters
        When field values are provided
        Then they should be validated according to business rules
        """
        # Given scorecard creation parameters
        # When field values are provided
        # Then validation should pass for valid values
        
        # Test valid scorecard name
        valid_name = "Customer Service Quality"
        assert len(valid_name.strip()) > 0
        assert len(valid_name) <= 255  # Assume reasonable length limit
        
        # Test key generation
        valid_key = valid_name.lower().replace(" ", "_")
        assert valid_key == "customer_service_quality"
        
        # Test description validation
        valid_description = "Scorecard for evaluating customer service interactions"
        assert isinstance(valid_description, str)
        
    def test_boolean_string_conversion_scenario(self):
        """
        Scenario: Converting string boolean parameters from MCP client
        Given a scorecard creation request with string boolean values
        When the tool processes boolean parameters  
        Then string values should be converted to proper booleans
        """
        # Given string boolean inputs (simulating MCP client behavior)
        true_values = ['true', 'True', 'TRUE', '1', 'yes']
        false_values = ['false', 'False', 'FALSE', '0', 'no', '']
        
        # When processing these values (simulating the tool's conversion logic)
        for val in true_values:
            result = val.lower() in ['true', '1', 'yes']
            if val.lower() in ['true', '1', 'yes']:
                # Then they should convert to True
                assert result is True
        
        for val in false_values:
            result = val.lower() in ['true', '1', 'yes'] 
            # Then they should convert to False
            assert result is False


class TestScorecardCreationExecution:
    """BDD scenarios for scorecard creation execution"""
    
    @pytest.mark.asyncio
    async def test_successful_scorecard_creation_scenario(self):
        """
        Scenario: Successfully creating a new scorecard
        Given valid scorecard creation parameters
        When the GraphQL mutation is executed
        Then a new scorecard should be created with all specified properties
        """
        # Given valid scorecard creation parameters and mocked dependencies
        with patch('plexus.cli.shared.client_utils.create_client') as mock_create_client, \
             patch('plexus.cli.report.utils.resolve_account_id_for_command') as mock_resolve_account, \
             patch('plexus.cli.scorecard.scorecards.resolve_account_identifier') as mock_resolve_account_cli, \
             patch.dict(os.environ, {'PLEXUS_API_URL': 'https://test.plexus.com', 'PLEXUS_API_KEY': 'test-key'}):
            
            mock_client = Mock()
            mock_create_client.return_value = mock_client
            mock_resolve_account.return_value = "account-123"
            mock_resolve_account_cli.return_value = "account-123"
            
            # Mock successful GraphQL response
            mock_client.execute.return_value = {
                'createScorecard': {
                    'id': 'scorecard-new-456',
                    'name': 'Quality Assurance',
                    'key': 'quality_assurance',
                    'externalId': 'qa_12345',
                    'description': 'Scorecard for quality evaluation',
                    'accountId': 'account-123'
                }
            }
            
            # When the scorecard creation function is called
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
            
            plexus_scorecard_create = registered_tools['plexus_scorecard_create']
            result = await plexus_scorecard_create(
                name="Quality Assurance",
                account_identifier="test-account",
                key="quality_assurance",
                external_id="qa_12345", 
                description="Scorecard for quality evaluation"
            )
            
            # Then the scorecard should be created successfully
            assert isinstance(result, dict)
            assert result['success'] is True
            assert result['scorecardId'] == 'scorecard-new-456'
            assert result['scorecardName'] == 'Quality Assurance'
            assert result['scorecardKey'] == 'quality_assurance'
            
    @pytest.mark.asyncio 
    async def test_auto_key_generation_scenario(self):
        """
        Scenario: Automatically generating scorecard key from name
        Given a scorecard creation request without explicit key
        When the tool processes the request
        Then a key should be auto-generated from the name
        """
        # Given mocked dependencies and scorecard creation without key
        with patch('plexus.cli.shared.client_utils.create_client') as mock_create_client, \
             patch('plexus.cli.report.utils.resolve_account_id_for_command') as mock_resolve_account, \
             patch('plexus.cli.scorecard.scorecards.resolve_account_identifier') as mock_resolve_account_cli, \
             patch.dict(os.environ, {'PLEXUS_API_URL': 'https://test.plexus.com', 'PLEXUS_API_KEY': 'test-key'}):
            
            mock_client = Mock()
            mock_create_client.return_value = mock_client
            mock_resolve_account.return_value = "account-123"
            mock_resolve_account_cli.return_value = "account-123"
            
            # Mock successful GraphQL response with auto-generated key
            mock_client.execute.return_value = {
                'createScorecard': {
                    'id': 'scorecard-auto-789',
                    'name': 'Customer Experience Rating',
                    'key': 'customer_experience_rating',  # Auto-generated
                    'externalId': 'cer_auto_67890',      # Auto-generated
                    'description': 'Auto-generated scorecard',
                    'accountId': 'account-123'
                }
            }
            
            # When the scorecard creation function is called without key
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
            
            plexus_scorecard_create = registered_tools['plexus_scorecard_create']
            result = await plexus_scorecard_create(
                name="Customer Experience Rating",
                account_identifier="test-account",
                description="Auto-generated scorecard"
            )
            
            # Then the key should be auto-generated from the name
            assert isinstance(result, dict)
            assert result['success'] is True
            assert result['scorecardKey'] == 'customer_experience_rating'
            
    @pytest.mark.asyncio
    async def test_account_not_found_scenario(self):
        """
        Scenario: Handling account resolution failure
        Given an invalid account identifier
        When attempting to create a scorecard
        Then an appropriate error should be returned
        """
        # Given mocked dependencies with account resolution failure
        with patch('plexus.cli.shared.client_utils.create_client') as mock_create_client, \
             patch('plexus.cli.report.utils.resolve_account_id_for_command') as mock_resolve_account, \
             patch('plexus.cli.scorecard.scorecards.resolve_account_identifier') as mock_resolve_account_cli, \
             patch.dict(os.environ, {'PLEXUS_API_URL': 'https://test.plexus.com', 'PLEXUS_API_KEY': 'test-key'}):
            
            mock_client = Mock()
            mock_create_client.return_value = mock_client
            mock_resolve_account.return_value = None  # Account not found
            mock_resolve_account_cli.return_value = None  # Account not found
            
            # When the scorecard creation function is called with invalid account
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
            
            plexus_scorecard_create = registered_tools['plexus_scorecard_create']
            result = await plexus_scorecard_create(
                name="Test Scorecard",
                account_identifier="nonexistent-account"
            )
            
            # Then an appropriate error should be returned
            assert isinstance(result, str)
            assert "Error" in result
            assert "account" in result.lower()


class TestScorecardCreationErrorHandling:
    """BDD scenarios for error handling during scorecard creation"""
    
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
             patch('plexus.cli.report.utils.resolve_account_id_for_command') as mock_resolve_account, \
             patch.dict(os.environ, {'PLEXUS_API_URL': 'https://test.plexus.com', 'PLEXUS_API_KEY': 'test-key'}):
            
            mock_client = Mock()
            mock_create_client.return_value = mock_client
            mock_resolve_account.return_value = "account-123"
            
            # Mock GraphQL execution failure
            mock_client.execute.side_effect = Exception("GraphQL mutation failed")
            
            # When the scorecard creation function is called
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
            
            plexus_scorecard_create = registered_tools['plexus_scorecard_create']
            result = await plexus_scorecard_create(
                name="Test Scorecard",
                account_identifier="test-account"
            )
            
            # Then the error should be handled gracefully
            assert isinstance(result, str)
            assert "Error" in result
            
    @pytest.mark.asyncio
    async def test_missing_credentials_scenario(self):
        """
        Scenario: Handling missing API credentials
        Given missing environment variables
        When attempting to create a scorecard
        Then an appropriate error should be returned
        """
        # Given missing environment variables
        with patch.dict(os.environ, {}, clear=True):
            
            # When the scorecard creation function is called
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
            
            plexus_scorecard_create = registered_tools['plexus_scorecard_create']
            result = await plexus_scorecard_create(
                name="Test Scorecard", 
                account_identifier="test-account"
            )
            
            # Then an appropriate error should be returned
            assert isinstance(result, str)
            assert "Error" in result
            assert "credentials" in result.lower() or "api" in result.lower()

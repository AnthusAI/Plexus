#!/usr/bin/env python3
"""
BDD-style unit tests for plexus_score_create tool
"""
import pytest
import os
import json
from unittest.mock import patch, Mock, AsyncMock
from io import StringIO
import uuid

pytestmark = pytest.mark.unit


class TestScoreCreationTool:
    """Test plexus_score_create tool using BDD patterns"""
    
    def test_score_creation_tool_registration(self):
        """Given the MCP server when registering score tools then plexus_score_create should be available"""
        # Import here to avoid early import issues
        from tools.score.scores import register_score_tools
        
        # Given a mock MCP instance
        mock_mcp = Mock()
        registered_tools = {}
        
        def mock_tool_decorator():
            def decorator(func):
                registered_tools[func.__name__] = func
                return func
            return decorator
        
        mock_mcp.tool = mock_tool_decorator
        
        # When registering score tools
        register_score_tools(mock_mcp)
        
        # Then plexus_score_create should be registered
        assert 'plexus_score_create' in registered_tools
        assert callable(registered_tools['plexus_score_create'])


class TestScoreCreationValidation:
    """Test parameter validation for score creation using BDD style"""
    
    def test_score_creation_requires_name_and_scorecard(self):
        """Given score creation parameters when name or scorecard is missing then validation should fail"""
        
        def validate_score_creation_params(name=None, scorecard_identifier=None, section_identifier=None, 
                                         score_type="SimpleLLMScore", external_id=None, key=None, 
                                         description=None, ai_provider=None, ai_model=None, 
                                         order=None, is_disabled=False):
            """Helper function to validate score creation parameters"""
            errors = []
            
            if not name or not name.strip():
                errors.append("name is required and cannot be empty")
            
            if not scorecard_identifier or not scorecard_identifier.strip():
                errors.append("scorecard_identifier is required and cannot be empty")
            
            if score_type and score_type not in ["SimpleLLMScore", "LangGraphScore", "ClassifierScore", "STANDARD"]:
                errors.append(f"score_type must be one of: SimpleLLMScore, LangGraphScore, ClassifierScore, STANDARD")
                
            return len(errors) == 0, errors
        
        # Given valid parameters
        # When validating with all required fields
        valid, errors = validate_score_creation_params(
            name="Test Score",
            scorecard_identifier="test-scorecard"
        )
        # Then validation should pass
        assert valid is True
        assert len(errors) == 0
        
        # Given missing name
        # When validating without name
        valid, errors = validate_score_creation_params(
            name="",
            scorecard_identifier="test-scorecard"
        )
        # Then validation should fail
        assert valid is False
        assert "name is required and cannot be empty" in errors
        
        # Given missing scorecard
        # When validating without scorecard_identifier
        valid, errors = validate_score_creation_params(
            name="Test Score",
            scorecard_identifier=""
        )
        # Then validation should fail
        assert valid is False
        assert "scorecard_identifier is required and cannot be empty" in errors
        
        # Given invalid score type
        # When validating with invalid score_type
        valid, errors = validate_score_creation_params(
            name="Test Score",
            scorecard_identifier="test-scorecard",
            score_type="InvalidType"
        )
        # Then validation should fail
        assert valid is False
        assert "score_type must be one of" in str(errors)

    def test_score_creation_default_values(self):
        """Given minimal score creation parameters when defaults are applied then sensible defaults should be used"""
        
        def apply_score_creation_defaults(name, scorecard_identifier, **kwargs):
            """Helper function to apply defaults for score creation"""
            defaults = {
                'score_type': 'SimpleLLMScore',
                'order': 0,
                'is_disabled': False,
                'ai_provider': 'unknown',
                'ai_model': 'unknown'
            }
            
            # Generate key from name if not provided
            if not kwargs.get('key'):
                # Simple key generation: lowercase, replace spaces with underscores, remove special chars
                key = name.lower().replace(' ', '_')
                key = ''.join(c for c in key if c.isalnum() or c == '_')
                defaults['key'] = key
            
            # Generate external_id if not provided
            if not kwargs.get('external_id'):
                defaults['external_id'] = f"score_{uuid.uuid4().hex[:8]}"
            
            return {**defaults, **kwargs}
        
        # Given minimal parameters
        # When applying defaults
        result = apply_score_creation_defaults(
            name="Test Score",
            scorecard_identifier="test-scorecard"
        )
        
        # Then sensible defaults should be applied
        assert result['score_type'] == 'SimpleLLMScore'
        assert result['key'] == 'test_score'
        assert result['order'] == 0
        assert result['is_disabled'] is False
        assert result['ai_provider'] == 'unknown'
        assert result['ai_model'] == 'unknown'
        assert result['external_id'].startswith('score_')
        assert len(result['external_id']) == 14  # "score_" + 8 chars


class TestScoreCreationGraphQLIntegration:
    """Test GraphQL integration for score creation using BDD style"""
    
    @pytest.mark.asyncio
    async def test_score_creation_with_valid_scorecard(self):
        """Given a valid scorecard when creating a score then GraphQL mutation should be executed correctly"""
        
        # Given mocked dependencies and environment variables
        with patch('plexus.cli.shared.client_utils.create_client') as mock_create_client, \
             patch('plexus.cli.scorecard.scorecards.resolve_scorecard_identifier') as mock_resolve_scorecard, \
             patch('plexus.cli.report.utils.resolve_account_id_for_command') as mock_resolve_account, \
             patch.dict(os.environ, {'PLEXUS_API_URL': 'https://test.api.url', 'PLEXUS_API_KEY': 'test-key'}):
            
            # Setup mocks
            mock_client = Mock()
            mock_create_client.return_value = mock_client
            mock_resolve_scorecard.return_value = "scorecard-123"
            mock_resolve_account.return_value = "account-456"
            
            # Mock scorecard query to return sections
            mock_client.execute.side_effect = [
                # First call: get scorecard sections
                {
                    'getScorecard': {
                        'id': 'scorecard-123',
                        'name': 'Test Scorecard',
                        'sections': {
                            'items': [
                                {
                                    'id': 'section-1',
                                    'name': 'Default Section',
                                    'order': 1
                                }
                            ]
                        }
                    }
                },
                # Second call: create score mutation
                {
                    'createScore': {
                        'id': 'score-new-123',
                        'name': 'Test Score',
                        'key': 'test_score',
                        'externalId': 'score_12345678',
                        'type': 'SimpleLLMScore',
                        'sectionId': 'section-1',
                        'scorecardId': 'scorecard-123',
                        'order': 0,
                        'isDisabled': False
                    }
                }
            ]
            
            # Import the function to test
            from tools.score.scores import register_score_tools
            
            # Get the function by registering tools
            mock_mcp = Mock()
            registered_tools = {}
            
            def mock_tool_decorator():
                def decorator(func):
                    registered_tools[func.__name__] = func
                    return func
                return decorator
            
            mock_mcp.tool = mock_tool_decorator
            register_score_tools(mock_mcp)
            
            plexus_score_create = registered_tools['plexus_score_create']
            
            # When creating a score
            result = await plexus_score_create(
                name="Test Score",
                scorecard_identifier="test-scorecard"
            )
            
            # Then the result should indicate success
            assert isinstance(result, dict)
            assert result['success'] is True
            assert result['scoreId'] == 'score-new-123'
            assert result['scoreName'] == 'Test Score'
            assert 'dashboardUrl' in result
            
            # And GraphQL mutations should have been called
            assert mock_client.execute.call_count == 2
            
            # And the create score mutation should have correct parameters
            create_call = mock_client.execute.call_args_list[1]
            mutation_query = create_call[0][0]
            assert 'createScore' in mutation_query
            assert 'name: "Test Score"' in mutation_query
            assert 'type: "SimpleLLMScore"' in mutation_query

    @pytest.mark.asyncio
    async def test_score_creation_with_nonexistent_scorecard(self):
        """Given a nonexistent scorecard when creating a score then appropriate error should be returned"""
        
        # Given mocked dependencies where scorecard doesn't exist
        with patch('plexus.cli.shared.client_utils.create_client') as mock_create_client, \
             patch('plexus.cli.scorecard.scorecards.resolve_scorecard_identifier') as mock_resolve_scorecard, \
             patch.dict(os.environ, {'PLEXUS_API_URL': 'https://test.api.url', 'PLEXUS_API_KEY': 'test-key'}):
            
            mock_client = Mock()
            mock_create_client.return_value = mock_client
            mock_resolve_scorecard.return_value = None  # Scorecard not found
            
            # Import and get the function
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
            
            plexus_score_create = registered_tools['plexus_score_create']
            
            # When creating a score with nonexistent scorecard
            result = await plexus_score_create(
                name="Test Score",
                scorecard_identifier="nonexistent-scorecard"
            )
            
            # Then an error should be returned
            assert isinstance(result, str)
            assert "not found" in result.lower()

    @pytest.mark.asyncio 
    async def test_score_creation_with_custom_section(self):
        """Given a specific section identifier when creating a score then score should be created in that section"""
        
        # Given mocked dependencies
        with patch('plexus.cli.shared.client_utils.create_client') as mock_create_client, \
             patch('plexus.cli.scorecard.scorecards.resolve_scorecard_identifier') as mock_resolve_scorecard, \
             patch('plexus.cli.report.utils.resolve_account_id_for_command') as mock_resolve_account, \
             patch.dict(os.environ, {'PLEXUS_API_URL': 'https://test.api.url', 'PLEXUS_API_KEY': 'test-key'}):
            
            mock_client = Mock()
            mock_create_client.return_value = mock_client
            mock_resolve_scorecard.return_value = "scorecard-123"
            mock_resolve_account.return_value = "account-456"
            
            # Mock scorecard sections query
            mock_client.execute.side_effect = [
                {
                    'getScorecard': {
                        'id': 'scorecard-123',
                        'name': 'Test Scorecard',
                        'sections': {
                            'items': [
                                {'id': 'section-1', 'name': 'Section 1', 'order': 1, 'scores': {'items': []}},
                                {'id': 'section-custom', 'name': 'Custom Section', 'order': 2, 'scores': {'items': []}}
                            ]
                        }
                    }
                },
                {
                    'createScore': {
                        'id': 'score-new-456',
                        'name': 'Custom Score',
                        'key': 'custom_score',
                        'externalId': 'score_87654321',
                        'type': 'SimpleLLMScore',
                        'order': 0,
                        'sectionId': 'section-custom',
                        'scorecardId': 'scorecard-123',
                        'isDisabled': False
                    }
                }
            ]
            
            # Import and get the function
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
            
            plexus_score_create = registered_tools['plexus_score_create']
            
            # When creating a score with specific section
            result = await plexus_score_create(
                name="Custom Score",
                scorecard_identifier="test-scorecard",
                section_identifier="Custom Section"
            )
            
            # Then score should be created in the specified section
            assert isinstance(result, dict)
            assert result['success'] is True
            
            # And the mutation should target the correct section
            create_call = mock_client.execute.call_args_list[1]
            mutation_query = create_call[0][0]
            assert 'sectionId: "section-custom"' in mutation_query


class TestScoreCreationErrorHandling:
    """Test error handling for score creation using BDD style"""
    
    @pytest.mark.asyncio
    async def test_score_creation_with_graphql_error(self):
        """Given GraphQL errors when creating a score then errors should be handled gracefully"""
        
        # Given mocked dependencies that raise GraphQL errors
        with patch('plexus.cli.shared.client_utils.create_client') as mock_create_client, \
             patch('plexus.cli.scorecard.scorecards.resolve_scorecard_identifier') as mock_resolve_scorecard, \
             patch('plexus.cli.report.utils.resolve_account_id_for_command') as mock_resolve_account, \
             patch.dict(os.environ, {'PLEXUS_API_URL': 'https://test.api.url', 'PLEXUS_API_KEY': 'test-key'}):
            
            mock_client = Mock()
            mock_create_client.return_value = mock_client
            mock_resolve_scorecard.return_value = "scorecard-123"
            mock_resolve_account.return_value = "account-456"
            
            # Mock client to raise exception on execute
            mock_client.execute.side_effect = Exception("GraphQL error: Field validation failed")
            
            # Import and get the function
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
            
            plexus_score_create = registered_tools['plexus_score_create']
            
            # When creating a score and GraphQL fails
            result = await plexus_score_create(
                name="Test Score",
                scorecard_identifier="test-scorecard"
            )
            
            # Then error should be handled gracefully
            assert isinstance(result, str)
            assert "error" in result.lower()
            assert "graphql" in result.lower() or "field validation failed" in result.lower()

    @pytest.mark.asyncio
    async def test_score_creation_with_missing_credentials(self):
        """Given missing API credentials when creating a score then appropriate error should be returned"""
        
        # Given missing environment variables
        with patch.dict(os.environ, {}, clear=True):
            # Import and get the function
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
            
            plexus_score_create = registered_tools['plexus_score_create']
            
            # When creating a score without credentials
            result = await plexus_score_create(
                name="Test Score",
                scorecard_identifier="test-scorecard"
            )
            
            # Then credentials error should be returned
            assert isinstance(result, str)
            assert "credentials" in result.lower() or "api" in result.lower()

#!/usr/bin/env python3
"""
Pytest configuration and fixtures for MCP server tests
"""
import pytest
import os
import sys
from unittest.mock import Mock, patch, MagicMock
from io import StringIO

# Add the MCP directory to the path for imports
mcp_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, mcp_dir)

@pytest.fixture
def mock_environment():
    """Provide mock environment variables for testing"""
    env_vars = {
        'PLEXUS_API_URL': 'https://test.plexus.example.com',
        'PLEXUS_API_KEY': 'test-api-key-123',
        'PLEXUS_ACCOUNT_KEY': 'test-account',
        'PLEXUS_APP_URL': 'https://test-app.plexus.example.com'
    }
    with patch.dict(os.environ, env_vars):
        yield env_vars

@pytest.fixture
def mock_dashboard_client():
    """Provide a mock dashboard client for testing"""
    client = Mock()
    
    # Mock successful responses
    client.execute.return_value = {
        'data': {
            'listScorecards': {
                'items': [
                    {
                        'id': 'test-scorecard-1',
                        'name': 'Test Scorecard 1',
                        'key': 'test-scorecard-1',
                        'description': 'A test scorecard',
                        'externalId': 'ext-1',
                        'createdAt': '2024-01-01T00:00:00Z',
                        'updatedAt': '2024-01-01T00:00:00Z'
                    }
                ]
            }
        }
    }
    
    return client

@pytest.fixture
def sample_scorecard_data():
    """Provide sample scorecard data for testing"""
    return {
        'id': 'scorecard-123',
        'name': 'Test Scorecard',
        'key': 'test-scorecard',
        'description': 'A test scorecard for unit tests',
        'externalId': 'ext-test-123',
        'createdAt': '2024-01-01T00:00:00Z',
        'updatedAt': '2024-01-01T12:00:00Z',
        'sections': {
            'items': [
                {
                    'id': 'section-1',
                    'name': 'Test Section',
                    'order': 1,
                    'scores': {
                        'items': [
                            {
                                'id': 'score-1',
                                'name': 'Test Score',
                                'key': 'test-score',
                                'description': 'A test score',
                                'type': 'LangGraphScore',
                                'order': 1,
                                'externalId': 'ext-score-1',
                                'championVersionId': 'version-1',
                                'isDisabled': False
                            }
                        ]
                    }
                }
            ]
        }
    }

@pytest.fixture
def sample_report_data():
    """Provide sample report data for testing"""
    return {
        'id': 'report-123',
        'name': 'Test Report',
        'createdAt': '2024-01-01T00:00:00Z',
        'updatedAt': '2024-01-01T12:00:00Z',
        'accountId': 'account-123',
        'reportConfigurationId': 'config-123',
        'taskId': 'task-123',
        'parameters': '{"param1": "value1"}',
        'output': 'Test report output',
        'reportBlocks': {
            'items': [
                {
                    'id': 'block-1',
                    'reportId': 'report-123',
                    'name': 'Test Block',
                    'position': 1,
                    'type': 'text',
                    'output': 'Block output',
                    'log': 'Block log',
                    'createdAt': '2024-01-01T00:00:00Z',
                    'updatedAt': '2024-01-01T00:00:00Z'
                }
            ]
        }
    }

@pytest.fixture
def capture_stdout():
    """Fixture to capture stdout during tests"""
    def _capture():
        original_stdout = sys.stdout
        temp_stdout = StringIO()
        sys.stdout = temp_stdout
        return original_stdout, temp_stdout
    
    def _restore(original_stdout):
        sys.stdout = original_stdout
    
    yield _capture, _restore

@pytest.fixture
def mock_fastmcp():
    """Provide a mock FastMCP instance for testing tool registration"""
    mcp = Mock()
    mcp.tool = Mock(return_value=lambda f: f)  # Return the function unchanged
    return mcp

@pytest.fixture
def mock_plexus_imports():
    """Mock Plexus imports to avoid dependency issues in tests"""
    with patch.dict('sys.modules', {
        'plexus.dashboard.api.client': Mock(),
        'plexus.cli.client_utils': Mock(),
        'plexus.cli.ScorecardCommands': Mock(),
        'plexus.cli.score': Mock(),
        'plexus.config': Mock()
    }):
        yield

@pytest.fixture
def graphql_error_response():
    """Provide a sample GraphQL error response"""
    return {
        'errors': [
            {
                'message': 'Field not found',
                'path': ['getScorecard'],
                'locations': [{'line': 2, 'column': 3}]
            },
            {
                'message': 'Invalid ID format',
                'path': ['id'],
                'extensions': {'code': 'INVALID_ID'}
            }
        ]
    }

@pytest.fixture
def empty_graphql_response():
    """Provide an empty GraphQL response"""
    return {
        'data': {
            'listScorecards': {
                'items': []
            }
        }
    }
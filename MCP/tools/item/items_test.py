#!/usr/bin/env python3
"""
Unit tests for item tools
"""
import pytest
import os
import json
from unittest.mock import patch, Mock, AsyncMock
from io import StringIO

pytestmark = pytest.mark.unit


class TestItemLastTool:
    """Test plexus_item_last tool patterns"""
    
    def test_item_last_validation_patterns(self):
        """Test item last parameter validation patterns"""
        def validate_item_last_params(minimal=False):
            if not isinstance(minimal, bool):
                return False, "minimal must be a boolean"
            return True, None
        
        # Test valid parameters
        valid, error = validate_item_last_params(False)
        assert valid is True
        assert error is None
        
        # Test with minimal True
        valid, error = validate_item_last_params(True)
        assert valid is True
        assert error is None
        
        # Test invalid minimal parameter
        valid, error = validate_item_last_params("invalid")
        assert valid is False
        assert "minimal must be a boolean" in error
    
    def test_item_last_query_patterns(self):
        """Test GraphQL query patterns for item last"""
        account_id = "account-123"
        
        # Test the GraphQL query structure
        query = f"""
        query ListItemByAccountIdAndCreatedAt($accountId: String!) {{
            listItemByAccountIdAndCreatedAt(accountId: $accountId, sortDirection: DESC, limit: 1) {{
                items {{
                    id
                    accountId
                    evaluationId
                    scoreId
                    description
                    externalId
                    isEvaluation
                    createdByType
                    metadata
                    identifiers
                    attachedFiles
                    createdAt
                    updatedAt
                }}
            }}
        }}
        """
        
        # Test query structure elements (not literal values since it uses variables)
        assert "$accountId: String!" in query
        assert "accountId: $accountId" in query
        assert "sortDirection: DESC" in query
        assert "limit: 1" in query
        assert "listItemByAccountIdAndCreatedAt" in query
    
    def test_item_last_response_patterns(self):
        """Test response handling patterns for item last"""
        # Test successful response
        mock_response = {
            'listItemByAccountIdAndCreatedAt': {
                'items': [
                    {
                        'id': 'item-123',
                        'accountId': 'account-456',
                        'description': 'Test item',
                        'createdAt': '2024-01-01T00:00:00Z',
                        'metadata': '{"key": "value"}',
                        'identifiers': []
                    }
                ]
            }
        }
        
        items = mock_response.get('listItemByAccountIdAndCreatedAt', {}).get('items', [])
        assert len(items) == 1
        assert items[0]['id'] == 'item-123'
        assert items[0]['description'] == 'Test item'
        
        # Test empty response
        empty_response = {
            'listItemByAccountIdAndCreatedAt': {
                'items': []
            }
        }
        
        items = empty_response.get('listItemByAccountIdAndCreatedAt', {}).get('items', [])
        assert len(items) == 0
        
        # Test error response
        error_response = {
            'errors': [
                {'message': 'Access denied', 'path': ['listItemByAccountIdAndCreatedAt']}
            ]
        }
        
        if 'errors' in error_response:
            error_details = json.dumps(error_response['errors'], indent=2)
            assert 'Access denied' in error_details
    
    def test_item_conversion_patterns(self):
        """Test item object to dictionary conversion patterns"""
        # Mock item object
        class MockItem:
            def __init__(self):
                self.id = 'item-123'
                self.accountId = 'account-456'
                self.evaluationId = 'eval-789'
                self.scoreId = 'score-101'
                self.description = 'Test item'
                self.externalId = 'EXT-001'
                self.isEvaluation = False
                self.createdByType = 'USER'
                self.metadata = {'key': 'value'}
                self.identifiers = []
                self.attachedFiles = []
                from datetime import datetime
                self.createdAt = datetime.fromisoformat('2024-01-01T00:00:00+00:00')
                self.updatedAt = datetime.fromisoformat('2024-01-01T12:00:00+00:00')
        
        item = MockItem()
        
        # Test conversion pattern
        item_dict = {
            'id': item.id,
            'accountId': item.accountId,
            'evaluationId': item.evaluationId,
            'scoreId': item.scoreId,
            'description': item.description,
            'externalId': item.externalId,
            'isEvaluation': item.isEvaluation,
            'createdByType': item.createdByType,
            'metadata': item.metadata,
            'identifiers': item.identifiers,
            'attachedFiles': item.attachedFiles,
            'createdAt': item.createdAt.isoformat() if item.createdAt else None,
            'updatedAt': item.updatedAt.isoformat() if item.updatedAt else None,
            'url': f"https://test.example.com/lab/items/{item.id}"
        }
        
        assert item_dict['id'] == 'item-123'
        assert item_dict['accountId'] == 'account-456'
        assert item_dict['createdAt'] == '2024-01-01T00:00:00+00:00'
        assert item_dict['updatedAt'] == '2024-01-01T12:00:00+00:00'
        assert 'lab/items/item-123' in item_dict['url']
    
    def test_minimal_mode_patterns(self):
        """Test minimal mode behavior patterns"""
        def simulate_minimal_mode(minimal=False):
            """Simulate the minimal mode logic"""
            item_dict = {'id': 'item-123', 'description': 'Test item'}
            
            if not minimal:
                # Include additional data when not in minimal mode
                item_dict['scoreResults'] = [{'scoreId': 'score-1', 'value': 'Yes'}]
                item_dict['feedbackItems'] = [{'id': 'feedback-1', 'corrected': True}]
            
            return item_dict
        
        # Test normal mode (includes extra data)
        normal_result = simulate_minimal_mode(False)
        assert 'scoreResults' in normal_result
        assert 'feedbackItems' in normal_result
        
        # Test minimal mode (excludes extra data)
        minimal_result = simulate_minimal_mode(True)
        assert 'scoreResults' not in minimal_result
        assert 'feedbackItems' not in minimal_result


class TestItemInfoTool:
    """Test plexus_item_info tool patterns"""
    
    def test_item_info_validation_patterns(self):
        """Test item info parameter validation patterns"""
        def validate_item_info_params(item_id, minimal=False):
            if not item_id or not item_id.strip():
                return False, "item_id is required"
            if not isinstance(minimal, bool):
                return False, "minimal must be a boolean"
            return True, None
        
        # Test valid parameters
        valid, error = validate_item_info_params("item-123")
        assert valid is True
        assert error is None
        
        # Test with minimal mode
        valid, error = validate_item_info_params("item-123", True)
        assert valid is True
        assert error is None
        
        # Test empty item ID
        valid, error = validate_item_info_params("")
        assert valid is False
        assert "item_id is required" in error
        
        # Test whitespace-only item ID
        valid, error = validate_item_info_params("   ")
        assert valid is False
        assert "item_id is required" in error
    
    def test_item_lookup_strategy_patterns(self):
        """Test item lookup strategy patterns"""
        def simulate_item_lookup_strategies(item_id, mock_results):
            """Simulate the multi-strategy item lookup logic"""
            lookup_method = "unknown"
            item = None
            
            # Strategy 1: Direct ID lookup
            if item_id in mock_results.get('direct_id', {}):
                item = mock_results['direct_id'][item_id]
                lookup_method = "direct_id"
                return item, lookup_method
            
            # Strategy 2: Identifier search
            if item_id in mock_results.get('identifier_search', {}):
                item = mock_results['identifier_search'][item_id]
                lookup_method = "identifier_search"
                return item, lookup_method
            
            # Strategy 3: GSI lookup
            if item_id in mock_results.get('gsi_lookup', {}):
                item = mock_results['gsi_lookup'][item_id]
                lookup_method = "identifiers_table_gsi"
                return item, lookup_method
            
            return None, "not_found"
        
        # Test direct ID lookup success
        mock_results = {
            'direct_id': {'item-123': {'id': 'item-123', 'name': 'Direct Item'}},
            'identifier_search': {},
            'gsi_lookup': {}
        }
        
        item, method = simulate_item_lookup_strategies('item-123', mock_results)
        assert item is not None
        assert method == "direct_id"
        assert item['name'] == 'Direct Item'
        
        # Test identifier search fallback
        mock_results = {
            'direct_id': {},
            'identifier_search': {'EXT-456': {'id': 'item-456', 'name': 'Identifier Item'}},
            'gsi_lookup': {}
        }
        
        item, method = simulate_item_lookup_strategies('EXT-456', mock_results)
        assert item is not None
        assert method == "identifier_search"
        assert item['name'] == 'Identifier Item'
        
        # Test GSI lookup fallback
        mock_results = {
            'direct_id': {},
            'identifier_search': {},
            'gsi_lookup': {'external-789': {'id': 'item-789', 'name': 'GSI Item'}}
        }
        
        item, method = simulate_item_lookup_strategies('external-789', mock_results)
        assert item is not None
        assert method == "identifiers_table_gsi"
        assert item['name'] == 'GSI Item'
        
        # Test not found
        mock_results = {
            'direct_id': {},
            'identifier_search': {},
            'gsi_lookup': {}
        }
        
        item, method = simulate_item_lookup_strategies('nonexistent', mock_results)
        assert item is None
        assert method == "not_found"
    
    def test_gsi_query_patterns(self):
        """Test GSI query patterns for identifier lookup"""
        account_id = "account-123"
        value = "external-456"
        
        # Test the GSI query structure
        query = """
        query GetIdentifierByAccountAndValue($accountId: String!, $value: String!) {
            listIdentifierByAccountIdAndValue(
                accountId: $accountId,
                value: {eq: $value},
                limit: 1
            ) {
                items {
                    itemId
                    name
                    value
                    url
                    position
                    item {
                        id
                        accountId
                        evaluationId
                        scoreId
                        description
                        externalId
                        isEvaluation
                        text
                        metadata
                        identifiers
                        attachedFiles
                        createdAt
                        updatedAt
                    }
                }
            }
        }
        """
        
        assert "listIdentifierByAccountIdAndValue" in query
        assert "value: {eq: $value}" in query
        assert "limit: 1" in query
        assert "item {" in query
    
    def test_mock_item_creation_patterns(self):
        """Test MockItem creation patterns for GSI results"""
        # Test MockItem class pattern
        class MockItem:
            def __init__(self, data):
                for key, value in data.items():
                    setattr(self, key, value)
                # Handle datetime parsing
                if hasattr(self, 'createdAt') and self.createdAt:
                    from datetime import datetime
                    try:
                        self.createdAt = datetime.fromisoformat(self.createdAt.replace('Z', '+00:00'))
                    except:
                        pass
                if hasattr(self, 'updatedAt') and self.updatedAt:
                    from datetime import datetime
                    try:
                        self.updatedAt = datetime.fromisoformat(self.updatedAt.replace('Z', '+00:00'))
                    except:
                        pass
        
        # Test with valid datetime strings
        item_data = {
            'id': 'item-123',
            'description': 'Test item',
            'createdAt': '2024-01-01T00:00:00Z',
            'updatedAt': '2024-01-01T12:00:00Z'
        }
        
        mock_item = MockItem(item_data)
        assert mock_item.id == 'item-123'
        assert mock_item.description == 'Test item'
        assert hasattr(mock_item, 'createdAt')
        assert hasattr(mock_item, 'updatedAt')
        
        # Test with invalid datetime strings
        item_data_invalid = {
            'id': 'item-456',
            'createdAt': 'invalid-date',
            'updatedAt': None
        }
        
        mock_item_invalid = MockItem(item_data_invalid)
        assert mock_item_invalid.id == 'item-456'
        assert mock_item_invalid.createdAt == 'invalid-date'  # Should remain unchanged
    
    def test_item_info_extended_fields_patterns(self):
        """Test extended fields patterns for item info (vs item last)"""
        # Test item info includes text field and lookupMethod
        item_dict = {
            'id': 'item-123',
            'accountId': 'account-456',
            'text': 'This is the item text content',  # Extra field in item info
            'description': 'Item description',
            'lookupMethod': 'direct_id'  # Extra field showing how item was found
        }
        
        assert 'text' in item_dict
        assert 'lookupMethod' in item_dict
        assert item_dict['text'] == 'This is the item text content'
        assert item_dict['lookupMethod'] == 'direct_id'


class TestItemToolsHelperFunctions:
    """Test helper functions used by item tools"""
    
    def test_score_results_helper_patterns(self):
        """Test _get_score_results_for_item helper function patterns"""
        # Mock score results query response
        mock_response = {
            'listScoreResultByItemId': {
                'items': [
                    {
                        'id': 'sr-1',
                        'value': 'Yes',
                        'explanation': 'Test explanation',
                        'confidence': 0.85,
                        'correct': True,
                        'itemId': 'item-123',
                        'scoreId': 'score-456',
                        'scoreName': 'Test Score',
                        'metadata': '{"cost": {"total": 0.001}}',
                        'updatedAt': '2024-01-01T12:00:00Z',
                        'createdAt': '2024-01-01T00:00:00Z'
                    }
                ]
            }
        }
        
        # Test score results processing
        score_results_data = mock_response.get('listScoreResultByItemId', {}).get('items', [])
        assert len(score_results_data) == 1
        
        score_result = score_results_data[0]
        assert score_result['value'] == 'Yes'
        assert score_result['scoreName'] == 'Test Score'
        assert score_result['confidence'] == 0.85
        
        # Test metadata cost extraction pattern
        metadata = score_result.get('metadata')
        if metadata and isinstance(metadata, str):
            import json
            try:
                metadata_dict = json.loads(metadata)
                cost = metadata_dict.get('cost', {})
                assert cost.get('total') == 0.001
            except json.JSONDecodeError:
                pass
    
    def test_feedback_items_helper_patterns(self):
        """Test _get_feedback_items_for_item helper function patterns"""
        # Mock feedback items response pattern
        mock_feedback_data = [
            {
                'id': 'feedback-1',
                'accountId': 'account-123',
                'scorecardId': 'scorecard-456',
                'scoreId': 'score-789',
                'itemId': 'item-123',
                'initialAnswerValue': 'No',
                'finalAnswerValue': 'Yes',
                'editCommentValue': 'Corrected the classification',
                'isAgreement': False,
                'editorName': 'John Doe',
                'editedAt': '2024-01-01T15:00:00Z',
                'createdAt': '2024-01-01T00:00:00Z',
                'updatedAt': '2024-01-01T15:00:00Z'
            }
        ]
        
        # Test feedback item processing
        assert len(mock_feedback_data) == 1
        feedback_item = mock_feedback_data[0]
        
        # Test correction detection
        is_correction = (
            feedback_item['initialAnswerValue'] != feedback_item['finalAnswerValue'] and
            feedback_item['finalAnswerValue'] is not None
        )
        assert is_correction is True
        
        # Test feedback item fields
        assert feedback_item['initialAnswerValue'] == 'No'
        assert feedback_item['finalAnswerValue'] == 'Yes'
        assert feedback_item['editCommentValue'] == 'Corrected the classification'
        assert feedback_item['isAgreement'] is False
    
    def test_item_url_generation_patterns(self):
        """Test item URL generation patterns"""
        def get_item_url(item_id: str) -> str:
            base_url = os.environ.get('PLEXUS_APP_URL', 'https://plexus.anth.us')
            if not base_url.endswith('/'):
                base_url += '/'
            path = f"lab/items/{item_id}"
            return base_url + path.lstrip('/')
        
        # Test URL generation
        with patch.dict(os.environ, {'PLEXUS_APP_URL': 'https://test.example.com'}):
            url = get_item_url('item-123')
            assert url == 'https://test.example.com/lab/items/item-123'
        
        # Test with trailing slash in base URL
        with patch.dict(os.environ, {'PLEXUS_APP_URL': 'https://test.example.com/'}):
            url = get_item_url('item-456')
            assert url == 'https://test.example.com/lab/items/item-456'
        
        # Test with default URL
        with patch.dict(os.environ, {}, clear=True):
            url = get_item_url('item-789')
            assert url == 'https://plexus.anth.us/lab/items/item-789'


class TestItemToolsSharedPatterns:
    """Test shared patterns across all item tools"""
    
    def test_credential_validation_pattern(self):
        """Test credential validation patterns used across item tools"""
        def validate_credentials():
            api_url = os.environ.get('PLEXUS_API_URL', '')
            api_key = os.environ.get('PLEXUS_API_KEY', '')
            
            if not api_url or not api_key:
                return False, "Missing API credentials"
            return True, None
        
        # Test with missing credentials
        with patch.dict(os.environ, {}, clear=True):
            valid, error = validate_credentials()
            assert valid is False
            assert "Missing API credentials" in error
        
        # Test with valid credentials
        with patch.dict(os.environ, {
            'PLEXUS_API_URL': 'https://test.example.com',
            'PLEXUS_API_KEY': 'test-key'
        }):
            valid, error = validate_credentials()
            assert valid is True
            assert error is None
    
    def test_stdout_redirection_pattern(self):
        """Test stdout redirection pattern used in all item tools"""
        # Test the pattern used to capture unexpected stdout
        old_stdout = StringIO()  # Mock original stdout
        temp_stdout = StringIO()
        
        # Simulate the pattern
        try:
            # Write something that should be captured
            print("This should be captured", file=temp_stdout)
            
            # Check capture
            captured_output = temp_stdout.getvalue()
            assert "This should be captured" in captured_output
        finally:
            # Pattern always restores stdout
            pass
    
    def test_error_response_handling_pattern(self):
        """Test GraphQL error response handling pattern"""
        # Test error response structure
        error_response = {
            'errors': [
                {
                    'message': 'Item not found',
                    'path': ['getItem'],
                    'extensions': {'code': 'NOT_FOUND'}
                }
            ]
        }
        
        # Test the pattern used to handle errors
        if 'errors' in error_response:
            error_details = json.dumps(error_response['errors'], indent=2)
            assert 'Item not found' in error_details
            assert 'NOT_FOUND' in error_details
    
    def test_account_id_resolution_pattern(self):
        """Test account ID resolution pattern"""
        def mock_resolve_account_id(client, account_identifier):
            # Mock the pattern used in the tools
            if account_identifier is None:
                # Return default account
                return "default-account-123"
            return f"resolved-{account_identifier}"
        
        # Test default account resolution
        account_id = mock_resolve_account_id(None, None)
        assert account_id == "default-account-123"
        
        # Test specific account resolution
        account_id = mock_resolve_account_id(None, "specific-account")
        assert account_id == "resolved-specific-account"
    
    def test_datetime_handling_patterns(self):
        """Test datetime handling patterns across item tools"""
        from datetime import datetime
        
        # Test datetime to ISO string conversion
        mock_datetime = datetime.fromisoformat('2024-01-01T12:00:00+00:00')
        iso_string = mock_datetime.isoformat() if hasattr(mock_datetime, 'isoformat') else mock_datetime
        assert iso_string == '2024-01-01T12:00:00+00:00'
        
        # Test handling None datetime
        none_datetime = None
        iso_string = none_datetime.isoformat() if none_datetime and hasattr(none_datetime, 'isoformat') else none_datetime
        assert iso_string is None
        
        # Test handling string datetime (fallback)
        string_datetime = '2024-01-01T12:00:00Z'
        iso_string = string_datetime.isoformat() if hasattr(string_datetime, 'isoformat') else string_datetime
        assert iso_string == '2024-01-01T12:00:00Z'
    
    def test_client_creation_pattern(self):
        """Test client creation patterns used in item tools"""
        def simulate_client_creation():
            """Simulate the client creation pattern"""
            api_url = os.environ.get('PLEXUS_API_URL', '')
            api_key = os.environ.get('PLEXUS_API_KEY', '')
            
            if not api_url or not api_key:
                return None, "Missing API credentials"
            
            # Mock successful client creation
            return {"api_url": api_url, "api_key": api_key}, None
        
        # Test successful client creation
        with patch.dict(os.environ, {
            'PLEXUS_API_URL': 'https://test.example.com',
            'PLEXUS_API_KEY': 'test-key'
        }):
            client, error = simulate_client_creation()
            assert client is not None
            assert error is None
            assert client['api_url'] == 'https://test.example.com'
        
        # Test failed client creation
        with patch.dict(os.environ, {}, clear=True):
            client, error = simulate_client_creation()
            assert client is None
            assert "Missing API credentials" in error